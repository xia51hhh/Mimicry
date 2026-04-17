use rusqlite::Connection;
use tauri::State;
use tokio::sync::Mutex;
use crate::db;
use crate::AppError;

#[tauri::command]
pub async fn workflow_list(db_conn: State<'_, Mutex<Connection>>) -> Result<Vec<db::workflow::Workflow>, AppError> {
    let conn = db_conn.lock().await;
    Ok(db::workflow::list(&conn)?)
}

#[tauri::command]
pub async fn workflow_get(db_conn: State<'_, Mutex<Connection>>, id: String) -> Result<Option<db::workflow::Workflow>, AppError> {
    let conn = db_conn.lock().await;
    Ok(db::workflow::get(&conn, &id)?)
}

#[tauri::command]
pub async fn workflow_create(db_conn: State<'_, Mutex<Connection>>, name: String) -> Result<db::workflow::Workflow, AppError> {
    let conn = db_conn.lock().await;
    let now = chrono::Utc::now().to_rfc3339();
    let wf = db::workflow::Workflow {
        id: uuid::Uuid::new_v4().to_string(),
        name,
        nodes: serde_json::json!([]),
        edges: serde_json::json!([]),
        created_at: now.clone(),
        updated_at: now,
    };
    db::workflow::create(&conn, &wf)?;
    Ok(wf)
}

#[tauri::command]
pub async fn workflow_save(db_conn: State<'_, Mutex<Connection>>, workflow: db::workflow::Workflow) -> Result<(), AppError> {
    let conn = db_conn.lock().await;
    let mut wf = workflow;
    wf.updated_at = chrono::Utc::now().to_rfc3339();
    Ok(db::workflow::update(&conn, &wf)?)
}

#[tauri::command]
pub async fn workflow_delete(db_conn: State<'_, Mutex<Connection>>, id: String) -> Result<(), AppError> {
    let conn = db_conn.lock().await;
    Ok(db::workflow::delete(&conn, &id)?)
}

#[tauri::command]
pub async fn workflow_export(db_conn: State<'_, Mutex<Connection>>) -> Result<String, AppError> {
    let conn = db_conn.lock().await;
    Ok(db::workflow::export_json(&conn)?)
}

#[tauri::command]
pub async fn workflow_import(db_conn: State<'_, Mutex<Connection>>, json: String) -> Result<usize, AppError> {
    let conn = db_conn.lock().await;
    db::workflow::import_json(&conn, &json).map_err(|e| AppError::Sidecar(e.to_string()))
}
