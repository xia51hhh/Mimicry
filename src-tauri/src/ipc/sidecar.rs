use std::process::Stdio;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::{Child, Command};
use tokio::sync::Mutex;
use tracing::info;

use super::jsonrpc::{RpcRequest, RpcResponse};
use crate::AppError;

pub struct Sidecar {
    #[allow(dead_code)]
    child: Option<Child>,
    stdin: Option<tokio::process::ChildStdin>,
    reader: Option<Mutex<BufReader<tokio::process::ChildStdout>>>,
    app_handle: Option<tauri::AppHandle>,
}

impl Sidecar {
    pub fn new() -> Self {
        Self {
            child: None,
            stdin: None,
            reader: None,
            app_handle: None,
        }
    }

    pub fn set_app_handle(&mut self, handle: tauri::AppHandle) {
        self.app_handle = Some(handle);
    }

    pub async fn start(&mut self, python_path: &str) -> Result<(), AppError> {
        if self.child.is_some() {
            info!("Sidecar already running");
            return Ok(());
        }

        let sidecar_dir = if std::path::Path::new("../sidecar/main.py").exists() {
            "../sidecar"
        } else if std::path::Path::new("sidecar/main.py").exists() {
            "sidecar"
        } else {
            return Err(AppError::Sidecar("Cannot find sidecar directory".into()));
        };

        info!("Starting sidecar: {} in {}", python_path, sidecar_dir);
        let mut child = Command::new(python_path)
            .arg("-u")
            .arg("main.py")
            .current_dir(sidecar_dir)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .spawn()
            .map_err(|e| AppError::Sidecar(format!("Failed to spawn sidecar: {}", e)))?;

        let stdin = child.stdin.take().ok_or_else(|| AppError::Sidecar("No stdin".into()))?;
        let stdout = child.stdout.take().ok_or_else(|| AppError::Sidecar("No stdout".into()))?;

        self.stdin = Some(stdin);
        self.reader = Some(Mutex::new(BufReader::new(stdout)));
        self.child = Some(child);

        // Verify with ping
        let resp = match self.call("ping", None).await {
            Ok(resp) => resp,
            Err(err) => {
                self.stop().await;
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

        let mut last_error = String::new();
        for python in ["python", "python3"] {
            match self.start(python).await {
                Ok(_) => return Ok(()),
                Err(err) => {
                    last_error = err.to_string();
                }
            }
        }

        Err(AppError::Sidecar(format!(
            "Failed to start sidecar with python/python3: {}",
            last_error
        )))
    }

    pub async fn call(&mut self, method: &str, params: Option<serde_json::Value>) -> Result<serde_json::Value, AppError> {
        let stdin = self.stdin.as_mut().ok_or_else(|| AppError::Sidecar("Sidecar not running".into()))?;
        let reader = self.reader.as_ref().ok_or_else(|| AppError::Sidecar("Sidecar not running".into()))?;

        let req = RpcRequest::new(method, params);
        let line = req.to_line();

        stdin.write_all(line.as_bytes()).await.map_err(|e| AppError::Sidecar(format!("Write failed: {}", e)))?;
        stdin.flush().await.map_err(|e| AppError::Sidecar(format!("Flush failed: {}", e)))?;

        let mut reader = reader.lock().await;
        let timeout_dur = std::time::Duration::from_secs(600);
        loop {
            let mut response_line = String::new();
            let bytes = tokio::time::timeout(timeout_dur, reader.read_line(&mut response_line))
                .await
                .map_err(|_| AppError::Sidecar("Sidecar call timed out".into()))?
                .map_err(|e| AppError::Sidecar(format!("Read failed: {}", e)))?;

            if bytes == 0 {
                return Err(AppError::Sidecar("Sidecar process exited unexpectedly".into()));
            }

            // Parse as generic JSON to check if it's a notification or response
            let val: serde_json::Value = serde_json::from_str(&response_line)?;

            if val.get("id").is_some() && !val["id"].is_null() {
                // It's a response
                let resp: RpcResponse = serde_json::from_value(val)?;
                if let Some(err) = resp.error {
                    return Err(AppError::Sidecar(format!("[{}] {}", err.code, err.message)));
                }
                return Ok(resp.result.unwrap_or(serde_json::Value::Null));
            } else if let Some(method) = val.get("method").and_then(|m| m.as_str()) {
                // It's a notification — forward as Tauri event
                if let Some(handle) = &self.app_handle {
                    use tauri::Emitter;
                    let event_name = format!("sidecar:{}", method);
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

    pub async fn stop(&mut self) {
        if let Some(mut child) = self.child.take() {
            let _ = child.kill().await;
            info!("Sidecar stopped");
        }
        self.stdin = None;
        self.reader = None;
    }
}
