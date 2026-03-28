from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import auth, devices, faces, integrations, ui
from .core.config import load_settings
from .db import store
from .modules.event_engine import EventEngine
from .modules.face_service import FaceService
from .modules.fire_service import FireService
from .services.camera_manager import CameraConfig, CameraManager
from .services.supervisor import Supervisor


def _seed_default_settings() -> None:
    store.upsert_setting("transport_mode", "http")
    store.upsert_setting("deployment_host", "windows_pc")
    store.upsert_setting("camera_processing_strategy", "event_triggered")


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
    event_engine = EventEngine(camera_manager=camera_manager, face_service=face_service, fire_service=fire_service)

    supervisor = Supervisor(
        node_offline_seconds=settings.node_offline_seconds,
        event_retention_days=settings.event_retention_days,
        log_retention_days=settings.log_retention_days,
        snapshot_root=settings.snapshot_root,
        regular_snapshot_retention_days=settings.regular_snapshot_retention_days,
        critical_snapshot_retention_days=settings.critical_snapshot_retention_days,
    )

    app.state.camera_manager = camera_manager
    app.state.face_service = face_service
    app.state.fire_service = fire_service
    app.state.event_engine = event_engine
    app.state.supervisor = supervisor

    camera_manager.start()
    supervisor.start()
    store.log("INFO", "Backend startup complete")

    try:
        yield
    finally:
        supervisor.stop()
        camera_manager.stop()
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


@app.get("/dashboard")
@app.get("/dashboard/{path:path}")
def dashboard(path: str = ""):
    index_file = WEB_DIST / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Dashboard build not found. Build web_dashboard_ui first.")
    return FileResponse(index_file)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.app.main:app",
        host=os.environ.get("BACKEND_HOST", "127.0.0.1"),
        port=int(os.environ.get("BACKEND_PORT", "8765")),
        reload=False,
    )
