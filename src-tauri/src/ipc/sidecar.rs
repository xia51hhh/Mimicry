use std::path::PathBuf;
use std::process::Stdio;
use std::sync::Arc;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::{Child, Command};
use tokio::sync::Mutex;
use tracing::info;

use super::jsonrpc::{RpcRequest, RpcResponse};
use crate::AppError;

/// Cloneable IO handles extracted from a running sidecar process.
/// These can be held independently of the main Sidecar Mutex.
#[derive(Clone)]
pub struct SidecarIo {
    stdin: Arc<Mutex<tokio::process::ChildStdin>>,
    reader: Arc<Mutex<BufReader<tokio::process::ChildStdout>>>,
    app_handle: Option<tauri::AppHandle>,
}

pub struct Sidecar {
    #[allow(dead_code)]
    child: Option<Child>,
    io: Option<SidecarIo>,
    sidecar_dir: PathBuf,
    venv_dir: PathBuf,
    app_handle: Option<tauri::AppHandle>,
}

impl Sidecar {
    pub fn new(sidecar_dir: PathBuf, venv_dir: PathBuf) -> Self {
        Self {
            child: None,
            io: None,
            sidecar_dir,
            venv_dir,
            app_handle: None,
        }
    }

    pub fn set_app_handle(&mut self, handle: tauri::AppHandle) {
        self.app_handle = Some(handle);
    }

    pub fn sidecar_dir(&self) -> &PathBuf {
        &self.sidecar_dir
    }

    pub fn venv_dir(&self) -> &PathBuf {
        &self.venv_dir
    }

    /// Get cloneable IO handles for making RPC calls without holding the Sidecar Mutex.
    pub fn io(&self) -> Result<SidecarIo, AppError> {
        self.io.clone().ok_or_else(|| AppError::Sidecar("Sidecar not running".into()))
    }

    /// Get the venv python path if it exists
    fn venv_python(&self) -> Option<PathBuf> {
        let p = self.venv_dir.join("bin/python");
        if p.exists() { Some(p) } else { None }
    }

    pub async fn start(&mut self, python_path: &str) -> Result<(), AppError> {
        if self.child.is_some() {
            info!("Sidecar already running");
            return Ok(());
        }

        info!("Starting sidecar: {} (dir: {:?})", python_path, self.sidecar_dir);
        let mut child = Command::new(python_path)
            .arg("-u")
            .arg("main.py")
            .current_dir(&self.sidecar_dir)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| AppError::Sidecar(format!("Failed to spawn sidecar: {}", e)))?;

        let stdin = child.stdin.take().ok_or_else(|| AppError::Sidecar("No stdin".into()))?;
        let stdout = child.stdout.take().ok_or_else(|| AppError::Sidecar("No stdout".into()))?;
        let stderr = child.stderr.take();

        let io = SidecarIo {
            stdin: Arc::new(Mutex::new(stdin)),
            reader: Arc::new(Mutex::new(BufReader::new(stdout))),
            app_handle: self.app_handle.clone(),
        };
        self.io = Some(io.clone());
        self.child = Some(child);

        // Verify with ping
        let resp = match SidecarIo::call(&io, "ping", None).await {
            Ok(resp) => resp,
            Err(err) => {
                // Collect stderr for better error messages (e.g. ModuleNotFoundError)
                let stderr_msg = if let Some(mut se) = stderr {
                    let mut buf = String::new();
                    let _ = tokio::io::AsyncReadExt::read_to_string(&mut se, &mut buf).await;
                    buf
                } else {
                    String::new()
                };
                self.stop().await;
                if !stderr_msg.is_empty() {
                    return Err(AppError::Sidecar(stderr_msg.trim().to_string()));
                }
                return Err(err);
            }
        };
        info!("Sidecar ready: {:?}", resp);
        Ok(())
    }

    pub async fn ensure_started(&mut self) -> Result<(), AppError> {
        if self.child.is_some() {
            return Ok(());
        }

        // Build candidate list: venv python first, then system pythons
        let mut candidates: Vec<String> = Vec::new();
        if let Some(venv_py) = self.venv_python() {
            candidates.push(venv_py.to_string_lossy().into_owned());
        }
        candidates.push("python3".into());
        candidates.push("python".into());

        let mut errors: Vec<String> = Vec::new();
        for python in &candidates {
            match self.start(python).await {
                Ok(_) => return Ok(()),
                Err(err) => {
                    errors.push(err.to_string());
                }
            }
        }

        // Return the most meaningful error (longest, likely has Python traceback)
        let best_error = errors.iter()
            .max_by_key(|e| e.len())
            .cloned()
            .unwrap_or_default();

        Err(AppError::Sidecar(best_error))
    }

    pub async fn stop(&mut self) {
        // Try graceful shutdown first
        if let Some(ref io) = self.io {
            match tokio::time::timeout(
                std::time::Duration::from_secs(3),
                io.call("shutdown", None),
            ).await {
                Ok(Ok(_)) => info!("Sidecar shutdown gracefully"),
                Ok(Err(e)) => tracing::debug!("Sidecar shutdown RPC failed: {}", e),
                Err(_) => tracing::debug!("Sidecar shutdown timed out"),
            }
        }
        // Force kill if still running
        if let Some(mut child) = self.child.take() {
            let _ = child.kill().await;
            info!("Sidecar process killed");
        }
        self.io = None;
    }

    pub async fn is_alive(&mut self) -> bool {
        match &mut self.child {
            Some(child) => {
                // Check if process is still running without blocking
                match child.try_wait() {
                    Ok(None) => true,   // still running
                    Ok(Some(_)) => false, // exited
                    Err(_) => false,
                }
            }
            None => false,
        }
    }

    pub async fn ensure_alive(&mut self) -> Result<(), AppError> {
        if self.child.is_some() && !self.is_alive().await {
            tracing::warn!("Sidecar heartbeat failed, restarting...");
            self.stop().await;
        }
        self.ensure_started().await
    }
}

impl SidecarIo {
    fn timeout_for_method(method: &str) -> std::time::Duration {
        match method {
            "ping" | "browser.status" | "recording.poll" | "workflow.execution_status"
                => std::time::Duration::from_secs(5),
            "browser.close" | "browser.navigate" | "recording.start" | "recording.stop"
            | "workflow.stop"
                => std::time::Duration::from_secs(30),
            "browser.launch" | "camoufox.check"
                => std::time::Duration::from_secs(60),
            // workflow.execute, camoufox.install, and anything else
            _ => std::time::Duration::from_secs(600),
        }
    }

    pub async fn call(&self, method: &str, params: Option<serde_json::Value>) -> Result<serde_json::Value, AppError> {
        let req = RpcRequest::new(method, params);
        let req_id = req.id;
        let line = req.to_line();
        tracing::debug!("RPC [{}] >> {}", req_id, line.trim());

        // Write request — brief lock on stdin
        {
            let mut stdin = self.stdin.lock().await;
            stdin.write_all(line.as_bytes()).await.map_err(|e| AppError::Sidecar(format!("Write failed: {}", e)))?;
            stdin.flush().await.map_err(|e| AppError::Sidecar(format!("Flush failed: {}", e)))?;
        }

        // Read response — holds reader lock until we get a matching response
        let mut reader = self.reader.lock().await;
        let timeout_dur = Self::timeout_for_method(method);
        loop {
            let mut response_line = String::new();
            let bytes = tokio::time::timeout(timeout_dur, reader.read_line(&mut response_line))
                .await
                .map_err(|_| AppError::Sidecar("Sidecar call timed out".into()))?
                .map_err(|e| AppError::Sidecar(format!("Read failed: {}", e)))?;

            if bytes == 0 {
                tracing::error!("RPC [{}]: sidecar process exited (EOF on stdout)", req_id);
                return Err(AppError::Sidecar("Sidecar process exited unexpectedly".into()));
            }

            tracing::debug!("RPC [{}] << {}", req_id, response_line.trim());

            // Parse as generic JSON to check if it's a notification or response
            let val: serde_json::Value = serde_json::from_str(&response_line)?;

            if val.get("id").is_some() && !val["id"].is_null() {
                // It's a response — verify id matches our request
                let resp: RpcResponse = serde_json::from_value(val)?;
                if resp.id != req_id {
                    tracing::warn!("RPC id mismatch: expected {}, got {} — skipping", req_id, resp.id);
                    continue;
                }
                if let Some(err) = resp.error {
                    let error_type = err.data
                        .as_ref()
                        .and_then(|d| d.error_type.as_deref())
                        .unwrap_or("Unknown");
                    return Err(AppError::Sidecar(format!("[{}:{}] {}", err.code, error_type, err.message)));
                }
                return Ok(resp.result.unwrap_or(serde_json::Value::Null));
            } else if let Some(method) = val.get("method").and_then(|m| m.as_str()) {
                // It's a notification — forward as Tauri event
                if let Some(handle) = &self.app_handle {
                    use tauri::Emitter;
                    let event_name = format!("sidecar:{}", method.replace('.', "/"));
                    let params = val.get("params").cloned().unwrap_or(serde_json::Value::Null);
                    let _ = handle.emit(&event_name, params);
                }
                // Continue reading next line
            } else {
                // Unknown format, skip
                continue;
            }
        }
    }
}
