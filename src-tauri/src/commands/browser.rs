use rusqlite::Connection;
use tauri::{AppHandle, Emitter, State};
use tokio::sync::Mutex;
use crate::ipc::sidecar::Sidecar;
use crate::AppError;

/// Acquire IO handles (briefly locking Sidecar), then release the lock and perform the RPC call.
async fn sidecar_call(
    sidecar: State<'_, Mutex<Sidecar>>,
    method: &str,
    params: Option<serde_json::Value>,
) -> Result<serde_json::Value, AppError> {
    let io = {
        let mut sc = sidecar.lock().await;
        sc.ensure_alive().await?;
        sc.io()?
        // Sidecar Mutex released here
    };
    io.call(method, params).await
}

fn find_python() -> Result<String, AppError> {
    for cmd in ["python3", "python"] {
        if std::process::Command::new(cmd).arg("--version").output().is_ok() {
            return Ok(cmd.to_string());
        }
    }
    Err(AppError::Sidecar("Python not found. Please install Python 3.10+".into()))
}

fn check_cmd(output: &std::process::Output, context: &str) -> Result<(), AppError> {
    if output.status.success() {
        return Ok(());
    }
    let stderr = String::from_utf8_lossy(&output.stderr);
    let stdout = String::from_utf8_lossy(&output.stdout);
    let msg = if !stderr.is_empty() { stderr } else { stdout };
    Err(AppError::Sidecar(format!("{}: {}", context, msg.trim())))
}

/// Emit install progress event to frontend
fn emit_progress(app: &AppHandle, step: &str, progress: u8, detail: &str) {
    let _ = app.emit("install-progress", serde_json::json!({
        "step": step,
        "progress": progress,
        "detail": detail,
    }));
}

#[tauri::command]
pub async fn browser_launch(
    sidecar: State<'_, Mutex<Sidecar>>,
    conn: State<'_, Mutex<Connection>>,
    profile_id: Option<String>,
    session_id: Option<String>,
) -> Result<serde_json::Value, AppError> {
    let sid = session_id.or_else(|| profile_id.clone()).unwrap_or_else(|| "default".into());
    tracing::info!("browser_launch called: session_id={}, profile_id={:?}", sid, profile_id);

    let mut params = serde_json::json!({"session_id": sid});

    if let Some(pid) = profile_id {
        let db = conn.lock().await;
        if let Some(profile) = crate::db::profiles::get(&db, &pid)? {
            tracing::info!("Profile loaded: id={}, user_data_dir={:?}", pid, profile.user_data_dir);
            params["profile"] = serde_json::json!({
                "user_data_dir": profile.user_data_dir,
                "fingerprint": profile.fingerprint,
                "proxy": profile.proxy,
                "os_target": profile.os_target,
                "browser_config": profile.browser_config,
            });
        } else {
            tracing::warn!("Profile not found: {}", pid);
        }
    }

    tracing::info!("Calling sidecar browser.launch with params: {}", params);
    let result = sidecar_call(sidecar, "browser.launch", Some(params)).await;
    match &result {
        Ok(v) => tracing::info!("browser.launch success: {}", v),
        Err(e) => tracing::error!("browser.launch failed: {}", e),
    }
    result
}

#[tauri::command]
pub async fn browser_detect_screens(
    sidecar: State<'_, Mutex<Sidecar>>,
) -> Result<serde_json::Value, AppError> {
    sidecar_call(sidecar, "browser.detect_screens", None).await
}

#[tauri::command]
pub async fn browser_install(app: AppHandle, sidecar: State<'_, Mutex<Sidecar>>) -> Result<serde_json::Value, AppError> {
    let python = find_python()?;
    let (sidecar_dir, venv_dir) = {
        let sc = sidecar.lock().await;
        (sc.sidecar_dir().to_path_buf(), sc.venv_dir().to_path_buf())
    };
    let req_file = sidecar_dir.join("requirements.txt");

    tracing::info!("Installing: python={}, venv={:?}, sidecar={:?}", python, venv_dir, sidecar_dir);

    let venv_python = venv_dir.join("bin/python");

    // Check what's already done (resilient to interrupted installs)
    let has_venv = venv_python.exists();
    let has_deps = if has_venv {
        tokio::process::Command::new(&venv_python)
            .args(["-c", "import camoufox, loguru, playwright"])
            .output().await
            .map(|o| o.status.success()).unwrap_or(false)
    } else { false };

    // Step 1: Create venv (skip if already exists)
    emit_progress(&app, "venv", 0, "");
    if !has_venv {
        let output = tokio::process::Command::new(&python)
            .args(["-m", "venv", venv_dir.to_string_lossy().as_ref()])
            .output()
            .await
            .map_err(|e| AppError::Sidecar(format!("Failed to run venv: {}", e)))?;
        
        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr).to_string();
            if stderr.contains("ensurepip") || stderr.contains("python3-venv") || stderr.contains("python3.") {
                emit_progress(&app, "venv", 0, "need_system_pkg");
                return Err(AppError::Sidecar("NEED_SYSTEM_PKG:python3-venv".into()));
            }
            return Err(AppError::Sidecar(format!("创建虚拟环境失败: {}", stderr.trim())));
        }
    }
    emit_progress(&app, "venv", 100, "");

    // Step 2: pip install (skip if deps already importable; pip is idempotent so safe to re-run)
    emit_progress(&app, "pip", 0, "");
    if !has_deps {
        let output = tokio::process::Command::new(&venv_python)
            .args(["-m", "pip", "install", "-r"])
            .arg(&req_file)
            .output()
            .await
            .map_err(|e| AppError::Sidecar(format!("Failed to run pip: {}", e)))?;
        check_cmd(&output, "pip install 失败")?;
    }
    emit_progress(&app, "pip", 100, "");

    // Step 3: Download camoufox browser with real-time progress
    emit_progress(&app, "browser", 0, "");
    let fetch_script = sidecar_dir.join("fetch_browser.py");
    let mut cmd = tokio::process::Command::new(&venv_python);
    cmd.arg(&fetch_script)
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped());
    // Try to get GitHub token: env var first, then gh CLI
    let token = std::env::var("GITHUB_TOKEN").ok().or_else(|| {
        std::process::Command::new("gh")
            .args(["auth", "token"])
            .output()
            .ok()
            .filter(|o| o.status.success())
            .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string())
    });
    if let Some(token) = token {
        cmd.env("GITHUB_TOKEN", &token);
    }

    let mut child = cmd.spawn()
        .map_err(|e| AppError::Sidecar(format!("Failed to start fetch: {}", e)))?;

    // Read stdout for progress JSON lines
    if let Some(stdout) = child.stdout.take() {
        use tokio::io::{AsyncBufReadExt, BufReader};
        let mut reader = BufReader::new(stdout).lines();
        while let Ok(Some(line)) = reader.next_line().await {
            if let Ok(obj) = serde_json::from_str::<serde_json::Value>(&line) {
                let step = obj.get("step").and_then(|v| v.as_str()).unwrap_or("browser");
                let progress = obj.get("progress").and_then(|v| v.as_u64()).unwrap_or(0) as u8;
                let detail = obj.get("detail").and_then(|v| v.as_str()).unwrap_or("");
                emit_progress(&app, step, progress, detail);
            }
        }
    }

    let output = child.wait_with_output().await
        .map_err(|e| AppError::Sidecar(format!("Failed to fetch camoufox: {}", e)))?;
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr).to_string();
        if stderr.contains("rate limit") || stderr.contains("403") {
            return Err(AppError::Sidecar(format!(
                "GitHub API 请求频率超限 (403)。请稍后重试，或设置 GITHUB_TOKEN 环境变量后重试。\n\n{}", 
                stderr.trim()
            )));
        }
        return Err(AppError::Sidecar(format!("camoufox 浏览器下载失败: {}", stderr.trim())));
    }
    emit_progress(&app, "browser", 100, "");

    tracing::info!("Installation complete!");
    Ok(serde_json::json!({"success": true}))
}

/// Install system packages using pkexec (shows native password dialog)
#[tauri::command]
pub async fn install_system_pkg(package: String) -> Result<serde_json::Value, AppError> {
    // Validate package name to prevent command injection
    if !package.chars().all(|c| c.is_alphanumeric() || c == '-' || c == '.') {
        return Err(AppError::Sidecar("Invalid package name".into()));
    }

    let output = tokio::process::Command::new("pkexec")
        .args(["apt", "install", "-y", &package])
        .output()
        .await
        .map_err(|e| AppError::Sidecar(format!("Failed to run pkexec: {}", e)))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        if stderr.contains("dismiss") || stderr.contains("Not authorized") {
            return Err(AppError::Sidecar("用户取消了授权".into()));
        }
        return Err(AppError::Sidecar(format!("安装系统包失败: {}", stderr.trim())));
    }

    Ok(serde_json::json!({"success": true}))
}

/// Check if environment is ready (venv exists + deps installed)
#[tauri::command]
pub async fn check_environment(sidecar: State<'_, Mutex<Sidecar>>) -> Result<serde_json::Value, AppError> {
    let venv_dir = {
        let sc = sidecar.lock().await;
        sc.venv_dir().to_path_buf()
    };
    let venv_python = venv_dir.join("bin/python");
    
    let has_venv = venv_python.exists();
    let mut has_deps = false;
    let mut has_browser = false;

    if has_venv {
        // Check if camoufox is importable
        let output = tokio::process::Command::new(&venv_python)
            .args(["-c", "import camoufox, loguru, playwright"])
            .output()
            .await;
        has_deps = output.map(|o| o.status.success()).unwrap_or(false);

        // Check if camoufox browser binary exists (without triggering auto-download)
        if has_deps {
            let output = tokio::process::Command::new(&venv_python)
                .args(["-c", "from camoufox.pkgman import INSTALL_DIR, LAUNCH_FILE, OS_NAME; exit(0 if (INSTALL_DIR / LAUNCH_FILE[OS_NAME]).exists() else 1)"])
                .output()
                .await;
            has_browser = output.map(|o| o.status.success()).unwrap_or(false);
        }
    }

    Ok(serde_json::json!({
        "ready": has_venv && has_deps && has_browser,
        "hasVenv": has_venv,
        "hasDeps": has_deps,
        "hasBrowser": has_browser,
    }))
}

#[tauri::command]
pub async fn browser_close(sidecar: State<'_, Mutex<Sidecar>>, session_id: Option<String>) -> Result<serde_json::Value, AppError> {
    let sid = session_id.unwrap_or_else(|| "default".into());
    sidecar_call(sidecar, "browser.close", Some(serde_json::json!({"session_id": sid}))).await
}

#[tauri::command]
pub async fn browser_navigate(sidecar: State<'_, Mutex<Sidecar>>, url: String, session_id: Option<String>) -> Result<serde_json::Value, AppError> {
    let sid = session_id.unwrap_or_else(|| "default".into());
    sidecar_call(sidecar, "browser.navigate", Some(serde_json::json!({"url": url, "session_id": sid}))).await
}

#[tauri::command]
pub async fn browser_status(sidecar: State<'_, Mutex<Sidecar>>, session_id: Option<String>) -> Result<serde_json::Value, AppError> {
    let sid = session_id.unwrap_or_else(|| "default".into());
    sidecar_call(sidecar, "browser.status", Some(serde_json::json!({"session_id": sid}))).await
}

#[tauri::command]
pub async fn browser_list_sessions(sidecar: State<'_, Mutex<Sidecar>>) -> Result<serde_json::Value, AppError> {
    sidecar_call(sidecar, "browser.list_sessions", None).await
}

#[tauri::command]
pub async fn recording_start(sidecar: State<'_, Mutex<Sidecar>>, session_id: Option<String>) -> Result<serde_json::Value, AppError> {
    let sid = session_id.unwrap_or_else(|| "default".into());
    sidecar_call(sidecar, "recording.start", Some(serde_json::json!({"session_id": sid}))).await
}

#[tauri::command]
pub async fn recording_stop(sidecar: State<'_, Mutex<Sidecar>>, session_id: Option<String>) -> Result<serde_json::Value, AppError> {
    let sid = session_id.unwrap_or_else(|| "default".into());
    sidecar_call(sidecar, "recording.stop", Some(serde_json::json!({"session_id": sid}))).await
}

#[tauri::command]
pub async fn recording_poll(sidecar: State<'_, Mutex<Sidecar>>, session_id: Option<String>) -> Result<serde_json::Value, AppError> {
    let sid = session_id.unwrap_or_else(|| "default".into());
    sidecar_call(sidecar, "recording.poll", Some(serde_json::json!({"session_id": sid}))).await
}

#[tauri::command]
pub async fn workflow_execute(sidecar: State<'_, Mutex<Sidecar>>, workflow: serde_json::Value, session_id: Option<String>, humanize: Option<bool>, delay_multiplier: Option<f64>) -> Result<serde_json::Value, AppError> {
    let sid = session_id.unwrap_or_else(|| "default".into());
    let h = humanize.unwrap_or(true);
    let dm = delay_multiplier.unwrap_or(1.0);
    sidecar_call(sidecar, "workflow.execute", Some(serde_json::json!({"workflow": workflow, "session_id": sid, "humanize": h, "delay_multiplier": dm}))).await
}

#[tauri::command]
pub async fn workflow_stop_execution(sidecar: State<'_, Mutex<Sidecar>>, session_id: Option<String>) -> Result<serde_json::Value, AppError> {
    let sid = session_id.unwrap_or_else(|| "default".into());
    sidecar_call(sidecar, "workflow.stop", Some(serde_json::json!({"session_id": sid}))).await
}

#[tauri::command]
pub async fn workflow_execution_status(sidecar: State<'_, Mutex<Sidecar>>, session_id: Option<String>) -> Result<serde_json::Value, AppError> {
    let sid = session_id.unwrap_or_else(|| "default".into());
    sidecar_call(sidecar, "workflow.execution_status", Some(serde_json::json!({"session_id": sid}))).await
}

#[tauri::command]
pub async fn camoufox_check(sidecar: State<'_, Mutex<Sidecar>>) -> Result<serde_json::Value, AppError> {
    sidecar_call(sidecar, "camoufox.check", None).await
}

#[tauri::command]
pub async fn camoufox_install(sidecar: State<'_, Mutex<Sidecar>>) -> Result<serde_json::Value, AppError> {
    sidecar_call(sidecar, "camoufox.install", None).await
}
