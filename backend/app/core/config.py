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
    camera_source_mode: str
    camera_webcam_single_node: str
    camera_indoor_rtsp: str
    camera_door_rtsp: str
    camera_indoor_webcam_index: int
    camera_door_webcam_index: int
    camera_processing_fps: int
    face_cosine_threshold: float
    face_detector_model_path: Path
    face_recognizer_model_path: Path
    face_detect_score_threshold: float
    face_detect_nms_threshold: float
    face_detect_top_k: int
    fire_model_enabled: bool
    fire_model_path: Path
    fire_model_threshold: float
    fire_model_input_size: int
    fire_model_fire_class_index: int
    authorized_presence_logging_enabled: bool
    authorized_presence_scan_seconds: int
    authorized_presence_cooldown_seconds: int
    unknown_presence_logging_enabled: bool
    unknown_presence_cooldown_seconds: int
    intruder_event_cooldown_seconds: int
    lan_base_url: str
    tailscale_base_url: str
    webpush_vapid_public_key: str
    webpush_vapid_private_key: str
    webpush_vapid_subject: str
    backend_host: str
    backend_port: int
    telegram_bot_token: str
    telegram_chat_id: str
    telegram_link_notifications_enabled: bool
    telegram_snapshot_cooldown_seconds: int
    mdns_enabled: bool
    mdns_service_name: str
    mdns_hostname: str


def load_env_file(project_root: Path | None = None, override: bool = False) -> None:
    if project_root is None:
        backend_root = Path(__file__).resolve().parents[2]
        project_root = backend_root.parent

    env_file = Path(os.environ.get("THESIS_ENV_FILE", str(project_root / ".env")))
    if not env_file.exists() or not env_file.is_file():
        return

    try:
        lines = env_file.read_text(encoding="utf-8").splitlines()
    except Exception:
        return

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue

        value = value.strip()
        if value and value[0] in {"'", '"'} and value[-1:] == value[0]:
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()

        if override or key not in os.environ:
            os.environ[key] = value


def _env_int(name: str, default: int, low: int, high: int) -> int:
    raw = os.environ.get(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError:
        value = default
    return max(low, min(high, value))


def _env_float(name: str, default: float, low: float, high: float) -> float:
    raw = os.environ.get(name, str(default)).strip()
    try:
        value = float(raw)
    except ValueError:
        value = default
    return max(low, min(high, value))


def _env_str(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "enabled"}


def _env_camera_source_mode(name: str, default: str = "rtsp") -> str:
    mode = os.environ.get(name, default).strip().lower()
    if mode not in {"rtsp", "webcam"}:
        return default
    return mode


def _env_webcam_single_node(name: str, default: str = "cam_door") -> str:
    raw = os.environ.get(name, default).strip().lower()
    if raw in {"", "none", "off", "false", "0", "disabled"}:
        return "none"
    if raw in {"cam_door", "cam_indoor"}:
        return raw
    return default


def load_settings() -> Settings:
    load_env_file()

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
        face_samples_root=Path(
            os.environ.get("FACE_SAMPLES_ROOT", storage_root / "face_samples")
        ),
        models_root=Path(os.environ.get("MODELS_ROOT", storage_root / "models")),
        admin_username=os.environ.get("ADMIN_USERNAME", "admin").strip() or "admin",
        admin_password=os.environ.get("ADMIN_PASSWORD", "admin123").strip()
        or "admin123",
        session_ttl_seconds=_env_int(
            "SESSION_TTL_SECONDS", 12 * 60 * 60, 900, 7 * 24 * 60 * 60
        ),
        node_offline_seconds=_env_int("NODE_OFFLINE_SECONDS", 120, 20, 3600),
        camera_offline_seconds=_env_int("CAMERA_OFFLINE_SECONDS", 45, 10, 600),
        regular_snapshot_retention_days=_env_int(
            "REGULAR_SNAPSHOT_RETENTION_DAYS", 30, 1, 365
        ),
        critical_snapshot_retention_days=_env_int(
            "CRITICAL_SNAPSHOT_RETENTION_DAYS", 90, 1, 365
        ),
        event_retention_days=_env_int("EVENT_RETENTION_DAYS", 90, 1, 365),
        log_retention_days=_env_int("LOG_RETENTION_DAYS", 30, 1, 365),
        camera_source_mode=_env_camera_source_mode("CAMERA_SOURCE_MODE", "rtsp"),
        camera_webcam_single_node=_env_webcam_single_node(
            "CAMERA_WEBCAM_SINGLE_NODE", "cam_door"
        ),
        camera_indoor_rtsp=os.environ.get("CAMERA_INDOOR_RTSP", "").strip(),
        camera_door_rtsp=os.environ.get("CAMERA_DOOR_RTSP", "").strip(),
        camera_indoor_webcam_index=_env_int("CAMERA_INDOOR_WEBCAM_INDEX", 0, 0, 20),
        camera_door_webcam_index=_env_int("CAMERA_DOOR_WEBCAM_INDEX", 1, 0, 20),
        camera_processing_fps=_env_int("CAMERA_PROCESSING_FPS", 12, 5, 20),
        face_cosine_threshold=_env_float("FACE_COSINE_THRESHOLD", 0.52, 0.30, 0.95),
        face_detector_model_path=Path(
            os.environ.get(
                "FACE_DETECTOR_MODEL_PATH",
                str(
                    storage_root
                    / "models"
                    / "face"
                    / "face_detection_yunet_2023mar.onnx"
                ),
            )
        ),
        face_recognizer_model_path=Path(
            os.environ.get(
                "FACE_RECOGNIZER_MODEL_PATH",
                str(
                    storage_root
                    / "models"
                    / "face"
                    / "face_recognition_sface_2021dec.onnx"
                ),
            )
        ),
        face_detect_score_threshold=_env_float(
            "FACE_DETECT_SCORE_THRESHOLD", 0.90, 0.01, 1.0
        ),
        face_detect_nms_threshold=_env_float(
            "FACE_DETECT_NMS_THRESHOLD", 0.30, 0.01, 1.0
        ),
        face_detect_top_k=_env_int("FACE_DETECT_TOP_K", 5000, 1, 50000),
        fire_model_enabled=_env_bool("FIRE_MODEL_ENABLED", True),
        fire_model_path=Path(
            os.environ.get(
                "FIRE_MODEL_PATH",
                str(storage_root / "models" / "fire" / "firenet.pb"),
            )
        ),
        fire_model_threshold=_env_float("FIRE_MODEL_THRESHOLD", 0.60, 0.05, 0.99),
        fire_model_input_size=_env_int("FIRE_MODEL_INPUT_SIZE", 224, 64, 640),
        fire_model_fire_class_index=_env_int("FIRE_MODEL_FIRE_CLASS_INDEX", 0, 0, 8),
        authorized_presence_logging_enabled=_env_bool(
            "AUTHORIZED_PRESENCE_LOGGING_ENABLED", True
        ),
        authorized_presence_scan_seconds=_env_int(
            "AUTHORIZED_PRESENCE_SCAN_SECONDS", 2, 1, 30
        ),
        authorized_presence_cooldown_seconds=_env_int(
            "AUTHORIZED_PRESENCE_COOLDOWN_SECONDS", 20, 5, 600
        ),
        unknown_presence_logging_enabled=_env_bool(
            "UNKNOWN_PRESENCE_LOGGING_ENABLED", True
        ),
        unknown_presence_cooldown_seconds=_env_int(
            "UNKNOWN_PRESENCE_COOLDOWN_SECONDS", 20, 5, 600
        ),
        intruder_event_cooldown_seconds=_env_int(
            "INTRUDER_EVENT_COOLDOWN_SECONDS", 20, 0, 600
        ),
        lan_base_url=_env_str("LAN_BASE_URL", ""),
        tailscale_base_url=_env_str("TAILSCALE_BASE_URL", ""),
        webpush_vapid_public_key=_env_str("WEBPUSH_VAPID_PUBLIC_KEY", ""),
        webpush_vapid_private_key=_env_str("WEBPUSH_VAPID_PRIVATE_KEY", ""),
        webpush_vapid_subject=_env_str(
            "WEBPUSH_VAPID_SUBJECT", "mailto:admin@localhost"
        ),
        backend_host=_env_str("BACKEND_HOST", "127.0.0.1"),
        backend_port=_env_int("BACKEND_PORT", 8765, 1, 65535),
        telegram_bot_token=_env_str("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=_env_str("TELEGRAM_CHAT_ID", ""),
        telegram_link_notifications_enabled=_env_bool(
            "TELEGRAM_LINK_NOTIFICATIONS_ENABLED", True
        ),
        telegram_snapshot_cooldown_seconds=_env_int(
            "TELEGRAM_SNAPSHOT_COOLDOWN_SECONDS", 60, 10, 3600
        ),
        mdns_enabled=_env_bool("MDNS_ENABLED", True),
        mdns_service_name=_env_str("MDNS_SERVICE_NAME", "thesis-monitor"),
        mdns_hostname=_env_str("MDNS_HOSTNAME", ""),
    )

    for path in (
        settings.storage_root,
        settings.snapshot_root,
        settings.logs_root,
        settings.face_samples_root,
        settings.models_root,
        settings.face_detector_model_path.parent,
        settings.face_recognizer_model_path.parent,
        settings.fire_model_path.parent,
        settings.db_path.parent,
    ):
        path.mkdir(parents=True, exist_ok=True)

    return settings
