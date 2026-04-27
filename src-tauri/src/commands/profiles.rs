use rusqlite::Connection;
use tauri::State;
use tokio::sync::Mutex;

use crate::db::profiles::{self, Profile};
use crate::AppError;

#[tauri::command]
pub async fn profile_list(conn: State<'_, Mutex<Connection>>) -> Result<Vec<Profile>, AppError> {
    let conn = conn.lock().await;
    Ok(profiles::list(&conn)?)
}

#[tauri::command]
pub async fn profile_get(
    conn: State<'_, Mutex<Connection>>,
    id: String,
) -> Result<Option<Profile>, AppError> {
    let conn = conn.lock().await;
    Ok(profiles::get(&conn, &id)?)
}

#[tauri::command]
pub async fn profile_create(
    conn: State<'_, Mutex<Connection>>,
    mut profile: Profile,
) -> Result<Profile, AppError> {
    // Auto-assign user_data_dir if empty
    if profile.user_data_dir.is_empty() {
        let profiles_dir = dirs::data_dir()
            .unwrap_or_else(|| std::path::PathBuf::from("."))
            .join("com.mimicry.app")
            .join("profiles")
            .join(&profile.id);
        std::fs::create_dir_all(&profiles_dir)
            .map_err(|e| AppError::Io(e))?;
        profile.user_data_dir = profiles_dir.to_string_lossy().to_string();
    }
    let conn = conn.lock().await;
    profiles::create(&conn, &profile)?;
    Ok(profile)
}

#[tauri::command]
pub async fn profile_update(
    conn: State<'_, Mutex<Connection>>,
    profile: Profile,
) -> Result<Profile, AppError> {
    let conn = conn.lock().await;
    profiles::update(&conn, &profile)?;
    Ok(profile)
}

#[tauri::command]
pub async fn profile_delete(
    conn: State<'_, Mutex<Connection>>,
    id: String,
) -> Result<(), AppError> {
    let conn = conn.lock().await;
    // Clean up user_data_dir if it exists under our managed path
    if let Some(profile) = profiles::get(&conn, &id)? {
        if !profile.user_data_dir.is_empty() {
            let path = std::path::Path::new(&profile.user_data_dir);
            if path.exists() && profile.user_data_dir.contains("com.mimicry.app") {
                let _ = std::fs::remove_dir_all(path);
            }
        }
    }
    profiles::delete(&conn, &id)?;
    Ok(())
}
