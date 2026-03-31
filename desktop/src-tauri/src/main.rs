#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::env;
use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;

use tauri::Manager;

struct BackendState {
    child: Mutex<Option<Child>>,
}

fn launch_backend() -> Option<Child> {
    let backend_host = env::var("DESKTOP_BACKEND_HOST")
        .ok()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
        .unwrap_or_else(|| "127.0.0.1".to_string());
    let backend_port = env::var("DESKTOP_BACKEND_PORT")
        .ok()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
        .unwrap_or_else(|| "8765".to_string());

    // Resolve paths from the repo root so launch works from tauri's src-tauri cwd.
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let repo_root = manifest_dir
        .parent()
        .and_then(|path| path.parent())
        .map(|path| path.to_path_buf())
        .unwrap_or_else(|| manifest_dir.clone());
    let backend_exe_path = repo_root.join("backend").join("backend.exe");
    let backend_script_path = repo_root.join("backend").join("run_backend.py");

    let mut candidates: Vec<(String, Vec<String>)> = Vec::new();

    candidates.push((
        backend_exe_path.to_string_lossy().to_string(),
        vec![],
    ));
    candidates.push((
        "python".to_string(),
        vec![backend_script_path.to_string_lossy().to_string()],
    ));
    candidates.push((
        "python3".to_string(),
        vec![backend_script_path.to_string_lossy().to_string()],
    ));

    for (program, args) in candidates {
        let mut cmd = Command::new(program);
        cmd.args(args)
            .env("BACKEND_HOST", backend_host.clone())
            .env("BACKEND_PORT", backend_port.clone());

        if let Ok(child) = cmd.spawn() {
            return Some(child);
        }
    }

    None
}

fn main() {
    tauri::Builder::default()
        .manage(BackendState {
            child: Mutex::new(None),
        })
        .setup(|app| {
            if let Some(child) = launch_backend() {
                let state = app.state::<BackendState>();
                match state.child.lock() {
                    Ok(mut slot) => {
                        *slot = Some(child);
                    }
                    Err(_) => {}
                };
            }

            if let Some(main_window) = app.get_window("main") {
                let _ = main_window.eval(
                    "setTimeout(() => { if (location.href !== 'http://127.0.0.1:8765/dashboard') { location.href = 'http://127.0.0.1:8765/dashboard'; } }, 1200);",
                );
            }

            Ok(())
        })
        .on_window_event(|event| {
            if let tauri::WindowEvent::Destroyed = event.event() {
                let app_handle = event.window().app_handle();
                let state = app_handle.state::<BackendState>();
                match state.child.lock() {
                    Ok(mut slot) => {
                        if let Some(mut child) = slot.take() {
                            let _ = child.kill();
                        }
                    }
                    Err(_) => {}
                };
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
