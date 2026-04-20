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
    profile: Profile,
) -> Result<Profile, AppError> {
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
    profiles::delete(&conn, &id)?;
    Ok(())
}
