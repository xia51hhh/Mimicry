use rusqlite::Connection;
use tauri::State;
use tokio::sync::Mutex;
use crate::db;
use crate::AppError;

#[derive(serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct WorkspaceFile {
    pub name: String,
    pub nodes: serde_json::Value,
    pub edges: serde_json::Value,
}

/// Read a .mimicry.json workspace file from disk
#[tauri::command]
pub async fn file_read(path: String) -> Result<WorkspaceFile, AppError> {
    let content = tokio::fs::read_to_string(&path)
        .await
        .map_err(|e| AppError::Sidecar(format!("Failed to read file: {e}")))?;
    let wf: WorkspaceFile = serde_json::from_str(&content)
        .map_err(|e| AppError::Sidecar(format!("Invalid JSON: {e}")))?;
    Ok(wf)
}

/// Read any workflow file, auto-detect format, and return Canonical.
/// Supports Canonical, Compact, Recording, Legacy formats.
#[tauri::command]
pub async fn file_import(path: String) -> Result<serde_json::Value, AppError> {
    use crate::transform::*;

    let content = tokio::fs::read_to_string(&path)
        .await
        .map_err(|e| AppError::Sidecar(format!("Failed to read file: {e}")))?;
    let raw: serde_json::Value = serde_json::from_str(&content)
        .map_err(|e| AppError::Sidecar(format!("Invalid JSON: {e}")))?;

    let fmt = detect_format(&raw);
    let canonical = match fmt {
        WorkflowFormat::Canonical => serde_json::from_value::<CanonicalWorkflow>(raw)?,
        WorkflowFormat::Compact | WorkflowFormat::Recording => {
            let compact: CompactWorkflow = serde_json::from_value(raw)?;
            compact_to_canonical(&compact)?
        }
        WorkflowFormat::Legacy => legacy_to_canonical(&raw)?,
        WorkflowFormat::Unknown => {
            return Err(AppError::Transform(
                "Unknown workflow format. Expected Canonical, Compact, Recording, or Legacy.".into(),
            ));
        }
    };

    Ok(serde_json::to_value(&canonical)?)
}

/// Export a Canonical workflow to Compact format and write to disk.
#[tauri::command]
pub async fn file_export_compact(path: String, workflow: serde_json::Value) -> Result<(), AppError> {
    use crate::transform::*;

    let canonical: CanonicalWorkflow = serde_json::from_value(workflow)?;
    let compact = canonical_to_compact(&canonical)?;
    let json = serde_json::to_string_pretty(&compact)
        .map_err(|e| AppError::Sidecar(format!("Serialize error: {e}")))?;
    tokio::fs::write(&path, json)
        .await
        .map_err(|e| AppError::Sidecar(format!("Failed to write file: {e}")))?;
    Ok(())
}

/// Write a .mimicry.json workspace file to disk
#[tauri::command]
pub async fn file_write(path: String, workspace: WorkspaceFile) -> Result<(), AppError> {
    let json = serde_json::to_string_pretty(&workspace)
        .map_err(|e| AppError::Sidecar(format!("Serialize error: {e}")))?;
    tokio::fs::write(&path, json)
        .await
        .map_err(|e| AppError::Sidecar(format!("Failed to write file: {e}")))?;
    Ok(())
}

/// Add a file to recent files list
#[tauri::command]
pub async fn recent_files_add(
    db_conn: State<'_, Mutex<Connection>>,
    path: String,
    name: String,
) -> Result<(), AppError> {
    let conn = db_conn.lock().await;
    let now = chrono::Utc::now().to_rfc3339();
    db::recent_files::upsert(&conn, &db::recent_files::RecentFile {
        path,
        name,
        opened_at: now,
    })?;
    Ok(())
}

/// List recent files (max 20)
#[tauri::command]
pub async fn recent_files_list(
    db_conn: State<'_, Mutex<Connection>>,
) -> Result<Vec<db::recent_files::RecentFile>, AppError> {
    let conn = db_conn.lock().await;
    Ok(db::recent_files::list(&conn, 20)?)
}

/// Remove a file from recent list
#[tauri::command]
pub async fn recent_files_remove(
    db_conn: State<'_, Mutex<Connection>>,
    path: String,
) -> Result<(), AppError> {
    let conn = db_conn.lock().await;
    Ok(db::recent_files::remove(&conn, &path)?)
}

/// Clear all recent files
#[tauri::command]
pub async fn recent_files_clear(
    db_conn: State<'_, Mutex<Connection>>,
) -> Result<(), AppError> {
    let conn = db_conn.lock().await;
    Ok(db::recent_files::clear(&conn)?)
}

/// Write plain text to a file (for log export etc.)
#[tauri::command]
pub async fn file_write_text(path: String, content: String) -> Result<(), AppError> {
    tokio::fs::write(&path, content)
        .await
        .map_err(|e| AppError::Sidecar(format!("Failed to write file: {e}")))?;
    Ok(())
}
