mod db;
mod ipc;
mod commands;
mod logger;
mod error;

pub use error::{AppError, AppResult};
use ipc::sidecar::Sidecar;
use tokio::sync::Mutex;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    logger::init();

    let conn = rusqlite::Connection::open("mimicry.db").expect("failed to open database");
    db::schema::init(&conn).expect("failed to init database schema");

    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .manage(Mutex::new(conn))
        .manage(Mutex::new(Sidecar::new()))
        .invoke_handler(tauri::generate_handler![
            commands::browser::browser_launch,
            commands::browser::browser_close,
            commands::browser::browser_navigate,
            commands::browser::browser_status,
            commands::browser::recording_start,
            commands::browser::recording_stop,
            commands::browser::recording_poll,
            commands::browser::workflow_execute,
            commands::browser::workflow_stop_execution,
            commands::browser::workflow_execution_status,
            commands::workflow::workflow_list,
            commands::workflow::workflow_get,
            commands::workflow::workflow_create,
            commands::workflow::workflow_save,
            commands::workflow::workflow_delete,
            commands::workflow::workflow_export,
            commands::workflow::workflow_import,
            commands::system::system_info,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
