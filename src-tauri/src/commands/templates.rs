use crate::db;
use crate::AppError;
use rusqlite::Connection;
use tauri::State;
use tokio::sync::Mutex;

#[tauri::command]
pub async fn template_list(
    db_conn: State<'_, Mutex<Connection>>,
) -> Result<Vec<db::templates::Template>, AppError> {
    let conn = db_conn.lock().await;
    Ok(db::templates::list(&conn)?)
}

#[tauri::command]
pub async fn template_get(
    db_conn: State<'_, Mutex<Connection>>,
    id: String,
) -> Result<Option<db::templates::Template>, AppError> {
    let conn = db_conn.lock().await;
    Ok(db::templates::get(&conn, &id)?)
}

#[tauri::command]
pub async fn template_create(
    db_conn: State<'_, Mutex<Connection>>,
    name: String,
    description: String,
    category: String,
    nodes: serde_json::Value,
    edges: serde_json::Value,
    tags: serde_json::Value,
) -> Result<db::templates::Template, AppError> {
    let conn = db_conn.lock().await;
    let now = chrono::Utc::now().to_rfc3339();
    let t = db::templates::Template {
        id: format!("tmpl_{}", uuid::Uuid::new_v4()),
        name,
        description,
        category,
        nodes,
        edges,
        tags,
        created_at: now.clone(),
        updated_at: now,
    };
    db::templates::create(&conn, &t)?;
    Ok(t)
}

#[tauri::command]
pub async fn template_delete(
    db_conn: State<'_, Mutex<Connection>>,
    id: String,
) -> Result<(), AppError> {
    let conn = db_conn.lock().await;
    db::templates::delete(&conn, &id)?;
    Ok(())
}

#[tauri::command]
pub async fn template_save_from_workflow(
    db_conn: State<'_, Mutex<Connection>>,
    name: String,
    description: String,
    category: String,
    nodes: serde_json::Value,
    edges: serde_json::Value,
) -> Result<db::templates::Template, AppError> {
    let conn = db_conn.lock().await;
    let now = chrono::Utc::now().to_rfc3339();
    let t = db::templates::Template {
        id: format!("tmpl_{}", uuid::Uuid::new_v4()),
        name,
        description,
        category,
        nodes,
        edges,
        tags: serde_json::json!([]),
        created_at: now.clone(),
        updated_at: now,
    };
    db::templates::create(&conn, &t)?;
    Ok(t)
}
