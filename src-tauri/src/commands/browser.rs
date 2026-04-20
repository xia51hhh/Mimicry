use tauri::State;
use tokio::sync::Mutex;
use crate::ipc::sidecar::Sidecar;
use crate::ipc::types::LaunchParams;
use crate::AppError;

async fn sidecar_call(
    sidecar: State<'_, Mutex<Sidecar>>,
    method: &str,
    params: Option<serde_json::Value>,
) -> Result<serde_json::Value, AppError> {
    let mut sc = sidecar.lock().await;
    sc.ensure_alive().await?;
    sc.call(method, params).await
}

#[tauri::command]
pub async fn browser_launch(
    sidecar: State<'_, Mutex<Sidecar>>,
    headless: Option<bool>,
    profile: Option<serde_json::Value>,
) -> Result<serde_json::Value, AppError> {
    let params = LaunchParams {
        headless,
        proxy: None,
        profile: profile.and_then(|v| serde_json::from_value(v).ok()),
    };
    sidecar_call(sidecar, "browser.launch", Some(serde_json::to_value(params)?)).await
}

#[tauri::command]
pub async fn browser_close(sidecar: State<'_, Mutex<Sidecar>>) -> Result<serde_json::Value, AppError> {
    sidecar_call(sidecar, "browser.close", None).await
}

#[tauri::command]
pub async fn browser_navigate(sidecar: State<'_, Mutex<Sidecar>>, url: String) -> Result<serde_json::Value, AppError> {
    sidecar_call(sidecar, "browser.navigate", Some(serde_json::json!({"url": url}))).await
}

#[tauri::command]
pub async fn browser_status(sidecar: State<'_, Mutex<Sidecar>>) -> Result<serde_json::Value, AppError> {
    sidecar_call(sidecar, "browser.status", None).await
}

#[tauri::command]
pub async fn recording_start(sidecar: State<'_, Mutex<Sidecar>>) -> Result<serde_json::Value, AppError> {
    sidecar_call(sidecar, "recording.start", None).await
}

#[tauri::command]
pub async fn recording_stop(sidecar: State<'_, Mutex<Sidecar>>) -> Result<serde_json::Value, AppError> {
    sidecar_call(sidecar, "recording.stop", None).await
}

#[tauri::command]
pub async fn recording_poll(sidecar: State<'_, Mutex<Sidecar>>) -> Result<serde_json::Value, AppError> {
    sidecar_call(sidecar, "recording.poll", None).await
}

#[tauri::command]
pub async fn workflow_execute(sidecar: State<'_, Mutex<Sidecar>>, workflow: serde_json::Value) -> Result<serde_json::Value, AppError> {
    sidecar_call(sidecar, "workflow.execute", Some(serde_json::json!({"workflow": workflow}))).await
}

#[tauri::command]
pub async fn workflow_stop_execution(sidecar: State<'_, Mutex<Sidecar>>) -> Result<serde_json::Value, AppError> {
    sidecar_call(sidecar, "workflow.stop", None).await
}

#[tauri::command]
pub async fn workflow_execution_status(sidecar: State<'_, Mutex<Sidecar>>) -> Result<serde_json::Value, AppError> {
    sidecar_call(sidecar, "workflow.execution_status", None).await
}

#[tauri::command]
pub async fn camoufox_check(sidecar: State<'_, Mutex<Sidecar>>) -> Result<serde_json::Value, AppError> {
    sidecar_call(sidecar, "camoufox.check", None).await
}

#[tauri::command]
pub async fn camoufox_install(sidecar: State<'_, Mutex<Sidecar>>) -> Result<serde_json::Value, AppError> {
    sidecar_call(sidecar, "camoufox.install", None).await
}
