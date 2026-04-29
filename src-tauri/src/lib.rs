mod db;
mod ipc;
mod commands;
mod logger;
mod error;
pub mod workflow_validator;
pub mod transform;

pub use error::{AppError, AppResult};
use ipc::sidecar::Sidecar;
use std::path::PathBuf;
use tauri::Manager;
use tokio::sync::Mutex;

fn resolve_sidecar_dir() -> PathBuf {
    let dev_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .map(|p| p.join("sidecar"));
    if let Some(ref dir) = dev_dir {
        if dir.exists() {
            return dir.clone();
        }
    }
    PathBuf::from("sidecar")
}

fn resolve_app_data_dir() -> PathBuf {
    dirs::data_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join("com.mimicry.app")
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    logger::init();

    let db_dir = resolve_app_data_dir();
    std::fs::create_dir_all(&db_dir).expect("failed to create app data directory");
    let db_path = db_dir.join("mimicry.db");
    let conn = rusqlite::Connection::open(&db_path).expect("failed to open database");
    db::schema::init(&conn).expect("failed to init database schema");

    let sidecar = Sidecar::new(resolve_sidecar_dir(), db_dir.join("venv"));

    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_dialog::init())
        .manage(Mutex::new(conn))
        .manage(Mutex::new(sidecar))
        .setup(|app| {
            // Fit window to monitor: 70% of logical screen, clamped
            if let Some(window) = app.get_webview_window("main") {
                if let Ok(Some(monitor)) = window.primary_monitor() {
                    let phy = monitor.size();
                    let scale = monitor.scale_factor();
                    let logical_w = phy.width as f64 / scale;
                    let logical_h = phy.height as f64 / scale;

                    let target_w = (logical_w * 0.7).clamp(800.0, 1400.0);
                    let target_h = (logical_h * 0.7).clamp(600.0, 900.0);

                    tracing::info!(
                        "Monitor: {}x{} @ {:.1}x, logical: {:.0}x{:.0}, window: {:.0}x{:.0}",
                        phy.width, phy.height, scale, logical_w, logical_h, target_w, target_h
                    );

                    let _ = window.set_size(tauri::LogicalSize::new(target_w, target_h));
                    let _ = window.center();
                }
            }

            let handle = app.handle().clone();
            let sidecar = app.state::<Mutex<Sidecar>>();
            tauri::async_runtime::block_on(async {
                sidecar.lock().await.set_app_handle(handle);
            });

            // Heartbeat timer: detect dead sidecar every 30s
            let handle_for_heartbeat = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                loop {
                    tokio::time::sleep(std::time::Duration::from_secs(30)).await;
                    let sidecar = handle_for_heartbeat.state::<Mutex<Sidecar>>();
                    let mut sc = sidecar.lock().await;
                    if sc.is_alive().await {
                        continue;
                    }
                    tracing::warn!("Sidecar heartbeat missed, stopping dead process");
                    sc.stop().await;
                    // Will be restarted on next call via ensure_alive
                }
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::browser::browser_launch,
            commands::browser::browser_detect_screens,
            commands::browser::browser_install,
            commands::browser::browser_list_sessions,
            commands::browser::install_system_pkg,
            commands::browser::check_environment,
            commands::browser::browser_close,
            commands::browser::browser_navigate,
            commands::browser::browser_status,
            commands::browser::recording_start,
            commands::browser::recording_stop,
            commands::browser::recording_poll,
            commands::browser::workflow_execute,
            commands::browser::workflow_stop_execution,
            commands::browser::workflow_execution_status,
            commands::browser::camoufox_check,
            commands::browser::camoufox_install,
            commands::browser::workflow_validate,
            commands::workflow::workflow_list,
            commands::workflow::workflow_get,
            commands::workflow::workflow_create,
            commands::workflow::workflow_save,
            commands::workflow::workflow_delete,
            commands::workflow::workflow_export,
            commands::workflow::workflow_import,
            commands::workflow::workflow_transform_import,
            commands::workflow::workflow_export_compact,
            commands::workflow::workflow_detect_format,
            commands::file_ops::file_read,
            commands::file_ops::file_write,
            commands::file_ops::file_import,
            commands::file_ops::file_export_compact,
            commands::file_ops::recent_files_add,
            commands::file_ops::recent_files_list,
            commands::file_ops::recent_files_remove,
            commands::file_ops::recent_files_clear,
            commands::file_ops::file_write_text,
            commands::system::system_info,
            commands::profiles::profile_list,
            commands::profiles::profile_get,
            commands::profiles::profile_create,
            commands::profiles::profile_update,
            commands::profiles::profile_delete,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
