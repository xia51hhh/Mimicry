use rusqlite::Connection;
use tauri::State;
use tokio::sync::Mutex;
use crate::ipc::sidecar::Sidecar;
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
    conn: State<'_, Mutex<Connection>>,
    profile_id: Option<String>,
) -> Result<serde_json::Value, AppError> {
    let mut params = serde_json::json!({});

    if let Some(pid) = profile_id {
        let db = conn.lock().await;
        if let Some(profile) = crate::db::profiles::get(&db, &pid)? {
            params = serde_json::json!({
                "profile": {
                    "user_data_dir": profile.user_data_dir,
                    "fingerprint": profile.fingerprint,
                    "proxy": profile.proxy,
                    "os_target": profile.os_target,
                }
            });
        }
    }

    sidecar_call(sidecar, "browser.launch", Some(params)).await
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
