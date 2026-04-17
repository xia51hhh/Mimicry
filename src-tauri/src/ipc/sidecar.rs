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
}

impl Sidecar {
    pub fn new() -> Self {
        Self {
            child: None,
            stdin: None,
            reader: None,
        }
    }

    pub async fn start(&mut self, python_path: &str) -> Result<(), AppError> {
        if self.child.is_some() {
            info!("Sidecar already running");
            return Ok(());
        }

        info!("Starting sidecar: {}", python_path);
        let mut child = Command::new(python_path)
            .arg("-u")
            .arg("main.py")
            .current_dir("sidecar")
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
        let mut response_line = String::new();
        reader.read_line(&mut response_line).await.map_err(|e| AppError::Sidecar(format!("Read failed: {}", e)))?;

        let resp: RpcResponse = serde_json::from_str(&response_line)?;

        if let Some(err) = resp.error {
            return Err(AppError::Sidecar(format!("[{}] {}", err.code, err.message)));
        }

        Ok(resp.result.unwrap_or(serde_json::Value::Null))
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
