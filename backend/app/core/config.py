from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    project_root: Path
    backend_root: Path
    storage_root: Path
    db_path: Path
    snapshot_root: Path
    logs_root: Path
    face_samples_root: Path
    models_root: Path
    admin_username: str
    admin_password: str
    session_ttl_seconds: int
    node_offline_seconds: int
    camera_offline_seconds: int
    regular_snapshot_retention_days: int
    critical_snapshot_retention_days: int
    event_retention_days: int
    log_retention_days: int
    camera_indoor_rtsp: str
    camera_door_rtsp: str
    camera_processing_fps: int


def _env_int(name: str, default: int, low: int, high: int) -> int:
    raw = os.environ.get(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError:
        value = default
    return max(low, min(high, value))


def load_settings() -> Settings:
    backend_root = Path(__file__).resolve().parents[2]
    project_root = backend_root.parent
    storage_root = backend_root / "storage"
    db_path = Path(os.environ.get("BACKEND_DB_PATH", storage_root / "system.db"))

    settings = Settings(
        project_root=project_root,
        backend_root=backend_root,
        storage_root=storage_root,
        db_path=db_path,
        snapshot_root=Path(os.environ.get("SNAPSHOT_ROOT", storage_root / "snapshots")),
        logs_root=Path(os.environ.get("LOGS_ROOT", storage_root / "logs")),
        face_samples_root=Path(os.environ.get("FACE_SAMPLES_ROOT", storage_root / "face_samples")),
        models_root=Path(os.environ.get("MODELS_ROOT", storage_root / "models")),
        admin_username=os.environ.get("ADMIN_USERNAME", "admin").strip() or "admin",
        admin_password=os.environ.get("ADMIN_PASSWORD", "admin123").strip() or "admin123",
        session_ttl_seconds=_env_int("SESSION_TTL_SECONDS", 12 * 60 * 60, 900, 7 * 24 * 60 * 60),
        node_offline_seconds=_env_int("NODE_OFFLINE_SECONDS", 120, 20, 3600),
        camera_offline_seconds=_env_int("CAMERA_OFFLINE_SECONDS", 45, 10, 600),
        regular_snapshot_retention_days=_env_int("REGULAR_SNAPSHOT_RETENTION_DAYS", 30, 1, 365),
        critical_snapshot_retention_days=_env_int("CRITICAL_SNAPSHOT_RETENTION_DAYS", 90, 1, 365),
        event_retention_days=_env_int("EVENT_RETENTION_DAYS", 90, 1, 365),
        log_retention_days=_env_int("LOG_RETENTION_DAYS", 30, 1, 365),
        camera_indoor_rtsp=os.environ.get("CAMERA_INDOOR_RTSP", "").strip(),
        camera_door_rtsp=os.environ.get("CAMERA_DOOR_RTSP", "").strip(),
        camera_processing_fps=_env_int("CAMERA_PROCESSING_FPS", 12, 5, 20),
    )

    for path in (
        settings.storage_root,
        settings.snapshot_root,
        settings.logs_root,
        settings.face_samples_root,
        settings.models_root,
        settings.db_path.parent,
    ):
        path.mkdir(parents=True, exist_ok=True)

    return settings
