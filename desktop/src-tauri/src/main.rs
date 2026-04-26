#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::env;
use std::fs;
use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;

use tauri::{AppHandle, Manager};

struct BackendState {
    child: Mutex<Option<Child>>,
}

struct RuntimePaths {
    runtime_root: PathBuf,
    env_file: PathBuf,
    db_path: PathBuf,
    snapshots_root: PathBuf,
    logs_root: PathBuf,
    face_samples_root: PathBuf,
    models_root: PathBuf,
    face_detector_path: PathBuf,
    face_recognizer_path: PathBuf,
    fire_model_path: PathBuf,
    dashboard_dist_dir: PathBuf,
}

fn ensure_dir(path: &PathBuf) -> bool {
    fs::create_dir_all(path).is_ok()
}

fn copy_if_missing(source: &PathBuf, target: &PathBuf) -> bool {
    if target.exists() {
        return true;
    }
    if let Some(parent) = target.parent() {
        if fs::create_dir_all(parent).is_err() {
            return false;
        }
    }
    fs::copy(source, target).is_ok()
}

fn resolve_repo_root() -> Option<PathBuf> {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let repo_root = manifest_dir
        .parent()
        .and_then(|path| path.parent())
        .map(|path| path.to_path_buf())?;
    if repo_root.exists() {
        Some(repo_root)
    } else {
        None
    }
}

fn resolve_first_resource(app: &AppHandle, candidates: &[&str]) -> Option<PathBuf> {
    for relative in candidates {
        if let Some(path) = app.path_resolver().resolve_resource(relative) {
            if path.exists() {
                return Some(path);
            }
        }
    }
    None
}

fn build_runtime_paths(app: &AppHandle, repo_root: Option<&PathBuf>) -> Option<RuntimePaths> {
    let runtime_root = app
        .path_resolver()
        .app_local_data_dir()
        .or_else(|| app.path_resolver().app_data_dir())
        .unwrap_or_else(|| env::temp_dir().join("IntruFlare"))
        .join("backend_runtime");

    let storage_root = runtime_root.join("storage");
    let snapshots_root = storage_root.join("snapshots");
    let logs_root = storage_root.join("logs");
    let face_samples_root = storage_root.join("face_samples");
    let models_root = storage_root.join("models");
    let face_models_root = models_root.join("face");
    let fire_models_root = models_root.join("fire");

    for path in [
        &runtime_root,
        &storage_root,
        &snapshots_root,
        &logs_root,
        &face_samples_root,
        &models_root,
        &face_models_root,
        &fire_models_root,
    ] {
        if !ensure_dir(path) {
            return None;
        }
    }

    let env_file = runtime_root.join(".env");
    if !env_file.exists() {
        let env_example = resolve_first_resource(app, &[".env.example", "resources/.env.example"])
            .or_else(|| repo_root.map(|root| root.join(".env.example")));
        if let Some(source) = env_example {
            let _ = copy_if_missing(&source, &env_file);
        } else {
            let _ = fs::write(&env_file, "");
        }
    }

    let dashboard_dist_dir = resolve_first_resource(app, &["web_dist", "resources/web_dist"])
        .or_else(|| {
            repo_root
                .map(|root| root.join("web_dashboard_ui").join("dist"))
                .filter(|path| path.exists())
        })?;

    let face_detector_source = resolve_first_resource(
        app,
        &[
            "models/face/face_detection_yunet_2023mar.onnx",
            "resources/models/face/face_detection_yunet_2023mar.onnx",
        ],
    )
    .or_else(|| {
        repo_root
            .map(|root| {
                root.join("backend")
                    .join("storage")
                    .join("models")
                    .join("face")
                    .join("face_detection_yunet_2023mar.onnx")
            })
            .filter(|path| path.exists())
    });

    let face_recognizer_source = resolve_first_resource(
        app,
        &[
            "models/face/face_recognition_sface_2021dec.onnx",
            "resources/models/face/face_recognition_sface_2021dec.onnx",
        ],
    )
    .or_else(|| {
        repo_root
            .map(|root| {
                root.join("backend")
                    .join("storage")
                    .join("models")
                    .join("face")
                    .join("face_recognition_sface_2021dec.onnx")
            })
            .filter(|path| path.exists())
    });

    let fire_model_source = resolve_first_resource(
        app,
        &["models/fire/firenet.pb", "resources/models/fire/firenet.pb"],
    )
    .or_else(|| {
        repo_root
            .map(|root| {
                root.join("backend")
                    .join("storage")
                    .join("models")
                    .join("fire")
                    .join("firenet.pb")
            })
            .filter(|path| path.exists())
    });

    let face_detector_path = face_models_root.join("face_detection_yunet_2023mar.onnx");
    let face_recognizer_path = face_models_root.join("face_recognition_sface_2021dec.onnx");
    let fire_model_path = fire_models_root.join("firenet.pb");

    if let Some(source) = face_detector_source {
        if !copy_if_missing(&source, &face_detector_path) {
            return None;
        }
    }
    if let Some(source) = face_recognizer_source {
        if !copy_if_missing(&source, &face_recognizer_path) {
            return None;
        }
    }
    if let Some(source) = fire_model_source {
        if !copy_if_missing(&source, &fire_model_path) {
            return None;
        }
    }

    if !(face_detector_path.exists() && face_recognizer_path.exists() && fire_model_path.exists()) {
        return None;
    }

    Some(RuntimePaths {
        runtime_root,
        env_file,
        db_path: storage_root.join("system.db"),
        snapshots_root,
        logs_root,
        face_samples_root,
        models_root,
        face_detector_path,
        face_recognizer_path,
        fire_model_path,
        dashboard_dist_dir,
    })
}

fn apply_backend_env(cmd: &mut Command, runtime: &RuntimePaths, host: &str, port: &str) {
    cmd.current_dir(&runtime.runtime_root)
        .env("BACKEND_HOST", host)
        .env("BACKEND_PORT", port)
        .env("THESIS_ENV_FILE", runtime.env_file.to_string_lossy().to_string())
        .env("BACKEND_DB_PATH", runtime.db_path.to_string_lossy().to_string())
        .env(
            "SNAPSHOT_ROOT",
            runtime.snapshots_root.to_string_lossy().to_string(),
        )
        .env("LOGS_ROOT", runtime.logs_root.to_string_lossy().to_string())
        .env(
            "FACE_SAMPLES_ROOT",
            runtime.face_samples_root.to_string_lossy().to_string(),
        )
        .env("MODELS_ROOT", runtime.models_root.to_string_lossy().to_string())
        .env(
            "FACE_DETECTOR_MODEL_PATH",
            runtime.face_detector_path.to_string_lossy().to_string(),
        )
        .env(
            "FACE_RECOGNIZER_MODEL_PATH",
            runtime.face_recognizer_path.to_string_lossy().to_string(),
        )
        .env(
            "FIRE_MODEL_PATH",
            runtime.fire_model_path.to_string_lossy().to_string(),
        )
        .env(
            "DASHBOARD_DIST_DIR",
            runtime.dashboard_dist_dir.to_string_lossy().to_string(),
        );
}

fn launch_backend(app: &AppHandle) -> Option<Child> {
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

    let repo_root = resolve_repo_root();
    let runtime = build_runtime_paths(app, repo_root.as_ref());

    let backend_exe_candidates = vec![
        resolve_first_resource(app, &["backend/backend.exe", "resources/backend/backend.exe"]),
        repo_root
            .as_ref()
            .map(|root| root.join("backend").join("dist").join("backend").join("backend.exe")),
        repo_root
            .as_ref()
            .map(|root| root.join("backend").join("backend.exe")),
    ];

    for exe_path in backend_exe_candidates.into_iter().flatten() {
        if !exe_path.exists() {
            continue;
        }
        let mut cmd = Command::new(&exe_path);
        if let Some(runtime_paths) = runtime.as_ref() {
            apply_backend_env(&mut cmd, runtime_paths, &backend_host, &backend_port);
        } else {
            cmd.env("BACKEND_HOST", backend_host.clone())
                .env("BACKEND_PORT", backend_port.clone());
        }
        if let Ok(child) = cmd.spawn() {
            return Some(child);
        }
    }

    let backend_script_path = repo_root
        .as_ref()
        .map(|root| root.join("backend").join("run_backend.py"))
        .filter(|path| path.exists());

    if let Some(script) = backend_script_path {
        for interpreter in ["python", "python3"] {
            let mut cmd = Command::new(interpreter);
            cmd.arg(script.to_string_lossy().to_string());
            if let Some(runtime_paths) = runtime.as_ref() {
                apply_backend_env(&mut cmd, runtime_paths, &backend_host, &backend_port);
            } else {
                cmd.env("BACKEND_HOST", backend_host.clone())
                    .env("BACKEND_PORT", backend_port.clone());
            }
            if let Ok(child) = cmd.spawn() {
                return Some(child);
            }
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
            if let Some(child) = launch_backend(&app.handle()) {
                let state = app.state::<BackendState>();
                match state.child.lock() {
                    Ok(mut slot) => {
                        *slot = Some(child);
                    }
                    Err(_) => {}
                };
            }

            if let Some(main_window) = app.get_window("main") {
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
                let dashboard_url = format!("http://{}:{}/dashboard", backend_host, backend_port);
                let script = format!(
                    "setTimeout(() => {{ if (location.href !== '{0}') {{ location.href = '{0}'; }} }}, 1200);",
                    dashboard_url
                );
                let _ = main_window.eval(&script);
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
