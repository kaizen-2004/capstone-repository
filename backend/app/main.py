from __future__ import annotations

import os
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
from .services.notification_dispatcher import NotificationDispatcher
from .services.remote_access import LinkResolver, MdnsPublisher
from .services.supervisor import Supervisor


def _seed_default_settings() -> None:
    store.upsert_setting("transport_mode", "http")
    store.upsert_setting("deployment_host", "windows_pc")
    store.upsert_setting("camera_processing_strategy", "event_triggered")
    store.upsert_setting("mobile_push_enabled", "true")
    store.upsert_setting("mobile_telegram_fallback_enabled", "true")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    app.state.settings = settings

    store.configure(path=settings.db_path, session_ttl_seconds=settings.session_ttl_seconds)
    store.init_db()
    store.ensure_admin_user(settings.admin_username, settings.admin_password)
    _seed_default_settings()

    store.upsert_camera("cam_indoor", "Indoor RTSP Camera", "Living Room", settings.camera_indoor_rtsp, settings.camera_processing_fps)
    store.upsert_camera("cam_door", "Door RTSP Camera", "Door Entrance Area", settings.camera_door_rtsp, settings.camera_processing_fps)

    camera_manager = CameraManager(storage_snapshot_root=settings.snapshot_root)
    camera_manager.configure(
        [
            CameraConfig(
                node_id="cam_indoor",
                label="Indoor RTSP Camera",
                location="Living Room",
                rtsp_url=settings.camera_indoor_rtsp,
                fps_target=settings.camera_processing_fps,
            ),
            CameraConfig(
                node_id="cam_door",
                label="Door RTSP Camera",
                location="Door Entrance Area",
                rtsp_url=settings.camera_door_rtsp,
                fps_target=settings.camera_processing_fps,
            ),
        ]
    )

    face_service = FaceService(sample_root=settings.face_samples_root, model_root=settings.models_root)
    fire_service = FireService()
    link_resolver = LinkResolver(settings=settings)
    mdns_publisher = MdnsPublisher(settings=settings, resolver=link_resolver)
    notification_dispatcher = NotificationDispatcher(
        settings=settings,
        link_resolver=link_resolver,
    )
    event_engine = EventEngine(
        camera_manager=camera_manager,
        face_service=face_service,
        fire_service=fire_service,
        notification_dispatcher=notification_dispatcher,
    )

    supervisor = Supervisor(
        node_offline_seconds=settings.node_offline_seconds,
        event_retention_days=settings.event_retention_days,
        log_retention_days=settings.log_retention_days,
        snapshot_root=settings.snapshot_root,
        regular_snapshot_retention_days=settings.regular_snapshot_retention_days,
        critical_snapshot_retention_days=settings.critical_snapshot_retention_days,
        notification_dispatcher=notification_dispatcher,
    )

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
    startup_links_result = notification_dispatcher.send_startup_access_links()
    store.log("INFO", f"startup access links dispatch status={startup_links_result.get('status')}")
    store.log("INFO", "Backend startup complete")

    try:
        yield
    finally:
        supervisor.stop()
        camera_manager.stop()
        mdns_publisher.stop()
        store.log("INFO", "Backend shutdown complete")


app = FastAPI(
    title="Condo Monitoring Backend",
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
        "tauri://localhost",
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
            "service": "Condo Monitoring Backend",
            "dashboard": "/dashboard",
            "health": "/health",
        }
    )


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WEB_DIST = PROJECT_ROOT / "web_dashboard_ui" / "dist"
WEB_ASSETS = WEB_DIST / "assets"

if WEB_ASSETS.exists():
    app.mount("/assets", StaticFiles(directory=str(WEB_ASSETS)), name="dashboard-assets")
    app.mount("/dashboard/assets", StaticFiles(directory=str(WEB_ASSETS)), name="dashboard-assets-nested")


def _serve_web_file(path: str, media_type: str | None = None) -> FileResponse:
    file_path = WEB_DIST / path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"{path} not found in dashboard build.")
    return FileResponse(file_path, media_type=media_type)


@app.get("/dashboard/manifest.webmanifest")
def dashboard_manifest() -> FileResponse:
    return _serve_web_file("manifest.webmanifest", media_type="application/manifest+json")


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
        raise HTTPException(status_code=404, detail="Dashboard build not found. Build web_dashboard_ui first.")
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
