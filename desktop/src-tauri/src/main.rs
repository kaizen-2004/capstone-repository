#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Child, Command};
use std::sync::Mutex;

use tauri::Manager;

struct BackendState {
    child: Mutex<Option<Child>>,
}

fn launch_backend() -> Option<Child> {
    let mut candidates: Vec<(String, Vec<String>)> = Vec::new();

    candidates.push((
        "backend/backend.exe".to_string(),
        vec![],
    ));
    candidates.push((
        "python".to_string(),
        vec!["backend/run_backend.py".to_string()],
    ));
    candidates.push((
        "python3".to_string(),
        vec!["backend/run_backend.py".to_string()],
    ));

    for (program, args) in candidates {
        let mut cmd = Command::new(program);
        cmd.args(args)
            .env("BACKEND_HOST", "127.0.0.1")
            .env("BACKEND_PORT", "8765");

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
                if let Ok(mut slot) = state.child.lock() {
                    *slot = Some(child);
                }
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
                let state = event.window().app_handle().state::<BackendState>();
                if let Ok(mut slot) = state.child.lock() {
                    if let Some(mut child) = slot.take() {
                        let _ = child.kill();
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
