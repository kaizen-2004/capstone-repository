from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import auth, devices, faces, integrations, ui
from .core.config import load_env_file, load_settings
from .db import store
from .modules.event_engine import EventEngine
from .modules.face_service import FaceService
from .modules.fire_service import FireService
from .services.camera_manager import CameraConfig, CameraManager
from .services.camera_http_control import CameraHttpController
from .services.notification_dispatcher import NotificationDispatcher
from .services.remote_access import LinkResolver, MdnsPublisher
from .services.supervisor import Supervisor


APP_NAME = "CondoGuardian"


def is_packaged_runtime() -> bool:
    return bool(getattr(sys, "frozen", False) or hasattr(sys, "_MEIPASS"))


def resource_path(relative_path: str) -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_path
    return Path(__file__).resolve().parents[2] / relative_path


def get_app_data_dir() -> Path:
    base = os.getenv("LOCALAPPDATA", "").strip()
    if base:
        app_dir = Path(base) / APP_NAME
    else:
        app_dir = Path.cwd() / f"{APP_NAME}Data"
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def configure_packaged_db_path() -> None:
    if not is_packaged_runtime():
        return
    if os.getenv("BACKEND_DB_PATH", "").strip():
        return
    db_path = get_app_data_dir() / "system.db"
    os.environ["BACKEND_DB_PATH"] = str(db_path)


def _seed_default_settings(settings) -> None:
    def _seed_once(key: str, value: str) -> None:
        if store.get_setting(key) is not None:
            return
        store.upsert_setting(key, value)

    _seed_once("transport_mode", "http")
    _seed_once("deployment_host", "windows_pc")
    _seed_once("camera_processing_strategy", "event_triggered")
    _seed_once("mobile_push_enabled", "true")
    _seed_once(
        "AUTHORIZED_PRESENCE_LOGGING_ENABLED",
        "true" if settings.authorized_presence_logging_enabled else "false",
    )
    _seed_once(
        "UNKNOWN_PRESENCE_LOGGING_ENABLED",
        "true" if settings.unknown_presence_logging_enabled else "false",
    )


def _camera_stream_setting_key(node_id: str) -> str | None:
    normalized = node_id.strip().lower()
    if normalized == "cam_door":
        return "CAMERA_DOOR_STREAM_URL"
    if normalized == "cam_indoor":
        return "CAMERA_INDOOR_STREAM_URL"
    return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_packaged_db_path()
    settings = load_settings()
    app.state.settings = settings

    store.configure(
        path=settings.db_path, session_ttl_seconds=settings.session_ttl_seconds
    )
    store.init_db()
    store.ensure_admin_user(settings.admin_username, settings.admin_password)
    store.ensure_single_admin_identity(settings.admin_username)
    forced_password = os.environ.get("ADMIN_FORCE_PASSWORD", "").strip()
    if forced_password:
        admin_user = store.get_single_admin_user()
        if admin_user is not None:
            store.update_admin_password(int(admin_user["id"]), forced_password)
            store.delete_sessions_for_user(int(admin_user["id"]))
            store.log(
                "WARNING",
                "ADMIN_FORCE_PASSWORD applied at startup; existing sessions invalidated.",
            )
    _seed_default_settings(settings)
    cleanup_counts = store.purge_dashboard_noise_data()
    if any(cleanup_counts.values()):
        store.log(
            "INFO",
            "startup noise cleanup "
            f"devices={cleanup_counts['devices']} "
            f"events={cleanup_counts['events']} "
            f"alerts={cleanup_counts['alerts']}",
        )

    def _setting_raw(key: str) -> str | None:
        value = store.get_setting(key)
        if value is None:
            return None
        return str(value).strip()

    def _setting_bool(key: str, fallback: bool) -> bool:
        raw = _setting_raw(key)
        if raw is None:
            return bool(fallback)
        return raw.lower() in {"1", "true", "yes", "on", "enabled"}

    def _setting_int(key: str, fallback: int, low: int, high: int) -> int:
        raw = _setting_raw(key)
        try:
            parsed = int(raw) if raw is not None else int(fallback)
        except ValueError:
            parsed = int(fallback)
        return max(low, min(high, parsed))

    def _setting_float(key: str, fallback: float, low: float, high: float) -> float:
        raw = _setting_raw(key)
        try:
            parsed = float(raw) if raw is not None else float(fallback)
        except ValueError:
            parsed = float(fallback)
        return max(low, min(high, parsed))

    camera_source_mode = settings.camera_source_mode
    camera_labels = {
        "cam_indoor": "Indoor RTSP Camera",
        "cam_door": "Door RTSP Camera",
    }
    camera_locations = {
        "cam_indoor": "Living Room",
        "cam_door": "Door Entrance Area",
    }

    def resolve_camera_stream(node_id: str, default_url: str) -> str:
        setting_key = _camera_stream_setting_key(node_id)
        override = (store.get_setting(setting_key) if setting_key else "") or ""
        override = override.strip()
        return override if override else default_url

    def resolve_camera_fps_target(node_id: str, source_url: str) -> int:
        _ = node_id
        target = settings.camera_processing_fps
        normalized_source = source_url.strip().lower()
        if normalized_source.startswith(
            ("http://", "https://")
        ) and normalized_source.endswith("/stream"):
            return max(target, 18)
        return target

    def build_rtsp_camera_sources() -> dict[str, str]:
        return {
            "cam_indoor": resolve_camera_stream(
                "cam_indoor", settings.camera_indoor_rtsp
            ),
            "cam_door": resolve_camera_stream("cam_door", settings.camera_door_rtsp),
        }

    def build_rtsp_camera_configs(
        sources: dict[str, str],
    ) -> list[CameraConfig]:
        return [
            CameraConfig(
                node_id="cam_indoor",
                label=camera_labels["cam_indoor"],
                location=camera_locations["cam_indoor"],
                rtsp_url=sources["cam_indoor"],
                fps_target=resolve_camera_fps_target(
                    "cam_indoor", sources["cam_indoor"]
                ),
                source_mode="rtsp",
            ),
            CameraConfig(
                node_id="cam_door",
                label=camera_labels["cam_door"],
                location=camera_locations["cam_door"],
                rtsp_url=sources["cam_door"],
                fps_target=resolve_camera_fps_target("cam_door", sources["cam_door"]),
                source_mode="rtsp",
            ),
        ]

    mirrored_camera_node: str | None = None
    camera_configs: list[CameraConfig] = []

    if camera_source_mode == "webcam":
        webcam_indices = {
            "cam_indoor": settings.camera_indoor_webcam_index,
            "cam_door": settings.camera_door_webcam_index,
        }
        door_webcam_fallback_index = (
            0 if settings.camera_door_webcam_index != 0 else None
        )
        single_webcam_node = settings.camera_webcam_single_node
        camera_sources = {
            "cam_indoor": f"webcam://{webcam_indices['cam_indoor']}",
            "cam_door": f"webcam://{webcam_indices['cam_door']}",
        }

        if single_webcam_node in {"cam_indoor", "cam_door"}:
            mirrored_camera_node = (
                "cam_indoor" if single_webcam_node == "cam_door" else "cam_door"
            )
            camera_sources[mirrored_camera_node] = f"mirror://{single_webcam_node}"
            camera_configs.append(
                CameraConfig(
                    node_id=single_webcam_node,
                    label=camera_labels[single_webcam_node],
                    location=camera_locations[single_webcam_node],
                    rtsp_url="",
                    fps_target=settings.camera_processing_fps,
                    source_mode="webcam",
                    webcam_index=webcam_indices[single_webcam_node],
                    webcam_fallback_index=(
                        door_webcam_fallback_index
                        if single_webcam_node == "cam_door"
                        else None
                    ),
                )
            )
        else:
            camera_configs.extend(
                [
                    CameraConfig(
                        node_id="cam_indoor",
                        label=camera_labels["cam_indoor"],
                        location=camera_locations["cam_indoor"],
                        rtsp_url="",
                        fps_target=settings.camera_processing_fps,
                        source_mode="webcam",
                        webcam_index=webcam_indices["cam_indoor"],
                    ),
                    CameraConfig(
                        node_id="cam_door",
                        label=camera_labels["cam_door"],
                        location=camera_locations["cam_door"],
                        rtsp_url="",
                        fps_target=settings.camera_processing_fps,
                        source_mode="webcam",
                        webcam_index=webcam_indices["cam_door"],
                        webcam_fallback_index=door_webcam_fallback_index,
                    ),
                ]
            )
    else:
        camera_sources = build_rtsp_camera_sources()
        camera_configs.extend(build_rtsp_camera_configs(camera_sources))

    for node_id in ("cam_indoor", "cam_door"):
        store.upsert_camera(
            node_id,
            camera_labels[node_id],
            camera_locations[node_id],
            camera_sources[node_id],
            resolve_camera_fps_target(node_id, camera_sources[node_id]),
        )

    if mirrored_camera_node is not None:
        mirror_target = (
            "cam_door" if mirrored_camera_node == "cam_indoor" else "cam_indoor"
        )
        store.set_camera_runtime(
            mirrored_camera_node,
            "offline",
            f"mirror source active: {mirror_target}",
        )

    camera_manager = CameraManager(storage_snapshot_root=settings.snapshot_root)
    camera_manager.configure(camera_configs)
    camera_http_controller = CameraHttpController(settings=settings)

    def apply_camera_stream_override(node_id: str, stream_url: str) -> dict[str, str]:
        normalized_node = node_id.strip().lower()
        if normalized_node not in {"cam_door", "cam_indoor"}:
            raise ValueError("unsupported camera node")
        if camera_source_mode == "webcam":
            raise RuntimeError("camera stream override unavailable in webcam mode")

        clean_url = stream_url.strip()
        if not clean_url:
            raise ValueError("stream_url is required")

        setting_key = _camera_stream_setting_key(normalized_node)
        if not setting_key:
            raise ValueError("unsupported camera node")

        store.upsert_setting(setting_key, clean_url)

        updated_sources = build_rtsp_camera_sources()
        camera_manager.configure(build_rtsp_camera_configs(updated_sources))
        camera_manager.start()

        for runtime_node in ("cam_indoor", "cam_door"):
            store.upsert_camera(
                runtime_node,
                camera_labels[runtime_node],
                camera_locations[runtime_node],
                updated_sources[runtime_node],
                resolve_camera_fps_target(runtime_node, updated_sources[runtime_node]),
            )

        return {
            "node_id": normalized_node,
            "active_stream_url": updated_sources[normalized_node],
        }

    face_service = FaceService(
        sample_root=settings.face_samples_root,
        model_root=settings.models_root,
        cosine_threshold=_setting_float(
            "FACE_COSINE_THRESHOLD", settings.face_cosine_threshold, 0.30, 0.95
        ),
        detector_model_path=settings.face_detector_model_path,
        recognizer_model_path=settings.face_recognizer_model_path,
        detect_score_threshold=settings.face_detect_score_threshold,
        detect_nms_threshold=settings.face_detect_nms_threshold,
        detect_top_k=settings.face_detect_top_k,
    )
    fire_service = FireService(
        enabled=_setting_bool("FIRE_MODEL_ENABLED", settings.fire_model_enabled),
        model_path=settings.fire_model_path,
        threshold=_setting_float(
            "FIRE_MODEL_THRESHOLD", settings.fire_model_threshold, 0.05, 0.99
        ),
        input_size=settings.fire_model_input_size,
        fire_class_index=settings.fire_model_fire_class_index,
    )
    link_resolver = LinkResolver(settings=settings)
    mdns_publisher = MdnsPublisher(settings=settings, resolver=link_resolver)
    notification_dispatcher = NotificationDispatcher(
        settings=settings,
        link_resolver=link_resolver,
    )
    event_engine = EventEngine(
        camera_manager=camera_manager,
        camera_http_controller=camera_http_controller,
        face_service=face_service,
        fire_service=fire_service,
        notification_dispatcher=notification_dispatcher,
        intruder_event_cooldown_seconds=_setting_int(
            "INTRUDER_EVENT_COOLDOWN_SECONDS",
            settings.intruder_event_cooldown_seconds,
            0,
            600,
        ),
    )
    app.state.camera_http_controller = camera_http_controller
    app.state.apply_camera_stream_override = apply_camera_stream_override

    supervisor = Supervisor(
        node_offline_seconds=_setting_int(
            "NODE_OFFLINE_SECONDS", settings.node_offline_seconds, 20, 3600
        ),
        camera_offline_seconds=_setting_int(
            "CAMERA_OFFLINE_SECONDS", settings.camera_offline_seconds, 10, 600
        ),
        event_retention_days=_setting_int(
            "EVENT_RETENTION_DAYS", settings.event_retention_days, 1, 365
        ),
        log_retention_days=_setting_int(
            "LOG_RETENTION_DAYS", settings.log_retention_days, 1, 365
        ),
        snapshot_root=settings.snapshot_root,
        regular_snapshot_retention_days=_setting_int(
            "REGULAR_SNAPSHOT_RETENTION_DAYS",
            settings.regular_snapshot_retention_days,
            1,
            365,
        ),
        critical_snapshot_retention_days=_setting_int(
            "CRITICAL_SNAPSHOT_RETENTION_DAYS",
            settings.critical_snapshot_retention_days,
            1,
            365,
        ),
        notification_dispatcher=notification_dispatcher,
        camera_manager=camera_manager,
        face_service=face_service,
        fire_service=fire_service,
        fire_continuous_detection_enabled=_setting_bool(
            "FIRE_MODEL_ENABLED", settings.fire_model_enabled
        ),
        fire_scan_seconds=_setting_int("FIRE_SCAN_SECONDS", 2, 1, 60),
        fire_alert_cooldown_seconds=45,
        authorized_presence_logging_enabled=_setting_bool(
            "AUTHORIZED_PRESENCE_LOGGING_ENABLED",
            settings.authorized_presence_logging_enabled,
        ),
        authorized_presence_scan_seconds=_setting_int(
            "AUTHORIZED_PRESENCE_SCAN_SECONDS",
            settings.authorized_presence_scan_seconds,
            1,
            30,
        ),
        authorized_presence_cooldown_seconds=_setting_int(
            "AUTHORIZED_PRESENCE_COOLDOWN_SECONDS",
            settings.authorized_presence_cooldown_seconds,
            5,
            600,
        ),
        unknown_presence_logging_enabled=_setting_bool(
            "UNKNOWN_PRESENCE_LOGGING_ENABLED",
            settings.unknown_presence_logging_enabled,
        ),
        unknown_presence_cooldown_seconds=_setting_int(
            "UNKNOWN_PRESENCE_COOLDOWN_SECONDS",
            settings.unknown_presence_cooldown_seconds,
            5,
            600,
        ),
    )

    for secret_key in (
        "WEBPUSH_VAPID_PUBLIC_KEY",
        "WEBPUSH_VAPID_PRIVATE_KEY",
        "WEBPUSH_VAPID_SUBJECT",
    ):
        override = _setting_raw(secret_key)
        if override is None:
            continue
        notification_dispatcher.apply_runtime_setting(secret_key, override)

    app.state.camera_manager = camera_manager
    app.state.face_service = face_service
    app.state.fire_service = fire_service
    app.state.event_engine = event_engine
    app.state.supervisor = supervisor
    app.state.notification_dispatcher = notification_dispatcher
    app.state.link_resolver = link_resolver
    app.state.mdns_publisher = mdns_publisher

    mdns_publisher.start()
    camera_manager.start()
    supervisor.start()
    face_model_status = face_service.model_status()
    fire_model_status = fire_service.model_status()
    store.log(
        "INFO",
        "model status "
        f"face_loaded={face_model_status.get('loaded')} "
        f"face_error={face_model_status.get('error') or 'none'} "
        f"fire_loaded={fire_model_status.get('loaded')} "
        f"fire_error={fire_model_status.get('error') or 'none'}",
    )
    store.log("INFO", "Backend startup complete")

    try:
        yield
    finally:
        supervisor.stop()
        camera_manager.stop()
        mdns_publisher.stop()
        store.log("INFO", "Backend shutdown complete")


app = FastAPI(
    title="IntruFlare Backend",
    version="2.0.0",
    description="Windows local-first event-driven intruder and fire monitoring backend",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1",
        "http://127.0.0.1:5173",
        "http://localhost",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(devices.router)
app.include_router(faces.router)
app.include_router(ui.router)
app.include_router(integrations.router)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "status": "online", "service": "fastapi-backend"}


@app.get("/")
def root() -> JSONResponse:
    return JSONResponse(
        {
            "ok": True,
            "service": "IntruFlare Backend",
            "dashboard": "/dashboard",
            "health": "/health",
        }
    )


def _resolve_dashboard_dist_dir() -> Path:
    override = os.environ.get("DASHBOARD_DIST_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    if is_packaged_runtime():
        return resource_path("web_dist")
    project_root = Path(__file__).resolve().parents[2]
    return project_root / "web_dashboard_ui" / "dist"


WEB_DIST = _resolve_dashboard_dist_dir()
WEB_ASSETS = WEB_DIST / "assets"

if WEB_ASSETS.exists():
    app.mount(
        "/assets", StaticFiles(directory=str(WEB_ASSETS)), name="dashboard-assets"
    )
    app.mount(
        "/dashboard/assets",
        StaticFiles(directory=str(WEB_ASSETS)),
        name="dashboard-assets-nested",
    )


def _serve_web_file(path: str, media_type: str | None = None) -> FileResponse:
    file_path = WEB_DIST / path
    if not file_path.exists():
        raise HTTPException(
            status_code=404, detail=f"{path} not found in dashboard build."
        )
    return FileResponse(file_path, media_type=media_type)


@app.get("/dashboard/manifest.webmanifest")
def dashboard_manifest() -> FileResponse:
    return _serve_web_file(
        "manifest.webmanifest", media_type="application/manifest+json"
    )


@app.get("/dashboard/sw.js")
def dashboard_service_worker() -> FileResponse:
    return _serve_web_file("dashboard-sw.js", media_type="application/javascript")


@app.get("/dashboard/icon.svg")
def dashboard_icon() -> FileResponse:
    return _serve_web_file("icon.svg", media_type="image/svg+xml")


@app.get("/dashboard")
@app.get("/dashboard/{path:path}")
def dashboard(path: str = ""):
    index_file = WEB_DIST / "index.html"
    if not index_file.exists():
        raise HTTPException(
            status_code=404,
            detail="Dashboard build not found. Build web_dashboard_ui first.",
        )
    return FileResponse(index_file)


if __name__ == "__main__":
    import uvicorn

    load_env_file()
    uvicorn.run(
        "backend.app.main:app",
        host=os.environ.get("BACKEND_HOST", "127.0.0.1"),
        port=int(os.environ.get("BACKEND_PORT", "8765")),
        reload=False,
    )
