use crate::db;
use crate::AppError;
use rusqlite::Connection;
use tauri::State;
use tokio::sync::Mutex;

#[tauri::command]
pub async fn workflow_list(
    db_conn: State<'_, Mutex<Connection>>,
) -> Result<Vec<db::workflow::Workflow>, AppError> {
    let conn = db_conn.lock().await;
    Ok(db::workflow::list(&conn)?)
}

#[tauri::command]
pub async fn workflow_get(
    db_conn: State<'_, Mutex<Connection>>,
    id: String,
) -> Result<Option<db::workflow::Workflow>, AppError> {
    let conn = db_conn.lock().await;
    Ok(db::workflow::get(&conn, &id)?)
}

#[tauri::command]
pub async fn workflow_create(
    db_conn: State<'_, Mutex<Connection>>,
    name: String,
) -> Result<db::workflow::Workflow, AppError> {
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
pub async fn workflow_save(
    db_conn: State<'_, Mutex<Connection>>,
    workflow: db::workflow::Workflow,
) -> Result<(), AppError> {
    let conn = db_conn.lock().await;
    let mut wf = workflow;
    wf.updated_at = chrono::Utc::now().to_rfc3339();
    Ok(db::workflow::update(&conn, &wf)?)
}

#[tauri::command]
pub async fn workflow_delete(
    db_conn: State<'_, Mutex<Connection>>,
    id: String,
) -> Result<(), AppError> {
    let conn = db_conn.lock().await;
    Ok(db::workflow::delete(&conn, &id)?)
}

#[tauri::command]
pub async fn workflow_export(db_conn: State<'_, Mutex<Connection>>) -> Result<String, AppError> {
    let conn = db_conn.lock().await;
    Ok(db::workflow::export_json(&conn)?)
}

#[tauri::command]
pub async fn workflow_import(
    db_conn: State<'_, Mutex<Connection>>,
    json: String,
) -> Result<usize, AppError> {
    let conn = db_conn.lock().await;
    db::workflow::import_json(&conn, &json).map_err(|e| AppError::Sidecar(e.to_string()))
}

/// Auto-detect format and transform any workflow JSON to Canonical format.
/// Supports: Canonical (passthrough), Compact, Recording, Legacy.
#[tauri::command]
pub fn workflow_transform_import(json: serde_json::Value) -> Result<serde_json::Value, AppError> {
    use crate::transform::*;

    let fmt = detect_format(&json);
    let canonical = match fmt {
        WorkflowFormat::Canonical => serde_json::from_value::<CanonicalWorkflow>(json)?,
        WorkflowFormat::Compact | WorkflowFormat::Recording => {
            let compact: CompactWorkflow = serde_json::from_value(json)?;
            compact_to_canonical(&compact)?
        }
        WorkflowFormat::Legacy => legacy_to_canonical(&json)?,
        WorkflowFormat::Unknown => {
            return Err(AppError::Transform(
                "Unknown workflow format. Expected Canonical, Compact, Recording, or Legacy."
                    .into(),
            ));
        }
    };

    Ok(serde_json::to_value(&canonical)?)
}

/// Export a Canonical workflow to Compact format (LLM-friendly).
#[tauri::command]
pub fn workflow_export_compact(workflow: serde_json::Value) -> Result<serde_json::Value, AppError> {
    use crate::transform::*;

    let canonical: CanonicalWorkflow = serde_json::from_value(workflow)?;
    let compact = canonical_to_compact(&canonical)?;
    Ok(serde_json::to_value(&compact)?)
}

/// Detect the format of a workflow JSON.
#[tauri::command]
pub fn workflow_detect_format(json: serde_json::Value) -> Result<String, AppError> {
    let fmt = crate::transform::detect_format(&json);
    Ok(fmt.to_string())
}
