from __future__ import annotations

import asyncio
import json
import re
import shutil
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

import cv2
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import (
    FileResponse,
    JSONResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)

from ..core.auth import get_current_user
from ..core.config import Settings
from ..core.security import parse_iso
from ..db import store
from ..schemas.api import (
    AlertReviewUpdateRequest,
    AssistantQueryRequest,
    BackupRestoreRequest,
    CameraControlRequest,
    RuntimeSettingUpdateRequest,
)

router = APIRouter(tags=["ui"])

FACE_DEBUG_CLASSIFY_INTERVAL_SECONDS = 0.5
FIRE_DEBUG_CLASSIFY_INTERVAL_SECONDS = 0.5
DEBUG_OVERLAY_FAILURE_COOLDOWN_SECONDS = 10.0
DEBUG_OVERLAY_MAX_CONSECUTIVE_FAILURES = 3
DEBUG_OVERLAY_LOG_INTERVAL_SECONDS = 8.0

ASSISTANT_NODE_LABELS: dict[str, str] = {
    "cam_indoor": "Indoor Camera",
    "cam_door": "Door Camera",
    "smoke_node1": "Smoke Node 1",
    "smoke_node2": "Smoke Node 2",
    "door_force": "Door Sensor",
}


def _face_debug_enabled_for_node(node_id: str, requested: bool) -> bool:
    _ = node_id
    return bool(requested)


def _direct_http_stream_url(node_id: str) -> str:
    normalized_node = node_id.strip().lower()
    for row in store.list_cameras():
        row_node = str(row.get("node_id") or "").strip().lower()
        if row_node != normalized_node:
            continue
        source_url = str(row.get("rtsp_url") or "").strip()
        source_lower = source_url.lower()
        if source_lower.startswith(("http://", "https://")) and source_lower.endswith(
            "/stream"
        ):
            return source_url
        return ""
    return ""


def _safe_json(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _is_dashboard_noise_node(node_id: str) -> bool:
    normalized = node_id.strip().lower()
    if not normalized:
        return False
    return any(
        normalized.startswith(prefix)
        for prefix in store.DASHBOARD_NOISE_NODE_PREFIXES
    )


def _assistant_node_label(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "Unknown node"
    normalized = raw.lower()
    return ASSISTANT_NODE_LABELS.get(normalized, raw)


def _assistant_friendly_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    for node_id, label in ASSISTANT_NODE_LABELS.items():
        pattern = re.compile(rf"\b{re.escape(node_id)}\b", flags=re.IGNORECASE)
        text = pattern.sub(label, text)
    return text


def _face_overlays_from_details(details: dict[str, Any]) -> list[dict[str, Any]]:
    raw_faces = details.get("faces")
    candidates: list[dict[str, Any]] = []
    if isinstance(raw_faces, list):
        candidates.extend(item for item in raw_faces if isinstance(item, dict))

    single_face = details.get("face")
    if isinstance(single_face, dict):
        candidates.append(single_face)

    overlays: list[dict[str, Any]] = []
    seen_boxes: set[tuple[int, int, int, int]] = set()
    for face in candidates:
        bbox = face.get("bbox")
        if not (isinstance(bbox, list) and len(bbox) == 4):
            continue

        try:
            x, y, w, h = [int(float(value)) for value in bbox]
        except Exception:
            continue
        if w <= 0 or h <= 0:
            continue

        box_key = (x, y, w, h)
        if box_key in seen_boxes:
            continue
        seen_boxes.add(box_key)

        classification = str(face.get("classification") or "").strip().upper()
        if not classification:
            result = str(face.get("result") or "").strip().lower()
            classification = "AUTHORIZED" if result == "authorized" else "NON-AUTHORIZED"

        try:
            confidence = float(face.get("confidence") or 0.0)
        except Exception:
            confidence = 0.0

        overlays.append(
            {
                "bbox": [x, y, w, h],
                "classification": classification,
                "confidence": round(confidence, 1),
                "label": f"{classification} {confidence:.1f}%",
            }
        )

    return overlays


def _alert_to_ui(row: dict[str, Any]) -> dict[str, Any]:
    details = _safe_json(row.get("details_json"))
    snapshot_path = str(row.get("snapshot_path") or "")
    snapshot_url = ""
    if snapshot_path:
        snapshot_url = (
            snapshot_path if snapshot_path.startswith("/") else f"/{snapshot_path}"
        )
    return {
        "id": int(row["id"]),
        "timestamp": str(row["ts"]),
        "severity": str(row.get("severity") or "info").lower(),
        "type": "intruder"
        if str(row.get("type", "")).upper()
        in {"INTRUDER", "DOOR_TAMPER", "AUTHORIZED_ENTRY"}
        else (
            "fire"
            if str(row.get("type", "")).upper() in {"FIRE", "SMOKE_WARNING"}
            else "system"
        ),
        "event_code": str(row.get("type") or "ALERT"),
        "source_node": str(details.get("source_node") or "system"),
        "location": str(details.get("location") or ""),
        "title": str(details.get("title") or row.get("type") or "Alert"),
        "description": str(details.get("description") or ""),
        "acknowledged": str(row.get("status") or "").upper() != "ACTIVE",
        "review_status": str(row.get("review_status") or "needs_review").lower(),
        "review_note": str(row.get("review_note") or ""),
        "reviewed_by": str(row.get("reviewed_by") or ""),
        "reviewed_ts": str(row.get("reviewed_ts") or ""),
        "confidence": details.get("confidence"),
        "fusion_evidence": details.get("fusion_evidence") or [],
        "snapshot_path": snapshot_url,
        "face_overlays": _face_overlays_from_details(details),
    }


def _snapshot_target_path(snapshot_path: str, snapshot_root: Path) -> Path | None:
    raw_value = str(snapshot_path or "").strip().lstrip("/")
    if not raw_value:
        return None

    relative_value = raw_value
    if relative_value.startswith("snapshots/"):
        relative_value = relative_value[len("snapshots/") :]
    if not relative_value:
        return None

    target = (snapshot_root / relative_value).resolve()
    if target != snapshot_root and snapshot_root not in target.parents:
        return None
    return target


def _normalize_query_timestamp(value: str | None) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    parsed = parse_iso(raw)
    if parsed is None:
        raise HTTPException(status_code=400, detail="invalid timestamp query parameter")
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")


def _event_to_ui(row: dict[str, Any]) -> dict[str, Any]:
    details = _safe_json(row.get("details_json"))
    return {
        "id": int(row["id"]),
        "timestamp": str(row["ts"]),
        "severity": str(row.get("severity") or "info").lower(),
        "type": str(row.get("type") or "system").lower(),
        "event_code": str(row.get("event_code") or "EVENT"),
        "source_node": str(row.get("source_node") or "system"),
        "location": str(row.get("location") or ""),
        "title": str(row.get("title") or row.get("event_code") or "Event"),
        "description": str(row.get("description") or ""),
        "acknowledged": True,
        "review_status": "archived",
        "review_note": "",
        "reviewed_by": "",
        "reviewed_ts": "",
        "confidence": details.get("confidence"),
        "fusion_evidence": details.get("fusion_evidence") or [],
        "face_overlays": _face_overlays_from_details(details),
    }


RUNTIME_SETTING_SPECS: dict[str, dict[str, Any]] = {
    "FACE_COSINE_THRESHOLD": {
        "description": "Higher is stricter; lower accepts more matches",
        "group": "Detection & Fusion",
        "value_type": "float",
        "input_type": "number",
        "min": 0.30,
        "max": 0.95,
        "step": 0.01,
        "live_apply": True,
    },
    "FIRE_MODEL_ENABLED": {
        "description": "Enable continuous camera-frame flame scanning",
        "group": "Detection & Fusion",
        "value_type": "bool",
        "input_type": "switch",
        "live_apply": True,
    },
    "FIRE_MODEL_THRESHOLD": {
        "description": "Higher is stricter; lower detects easier",
        "group": "Detection & Fusion",
        "value_type": "float",
        "input_type": "number",
        "min": 0.05,
        "max": 0.99,
        "step": 0.01,
        "live_apply": True,
    },
    "INTRUDER_EVENT_COOLDOWN_SECONDS": {
        "description": "Minimum seconds between repeated intruder trigger events per node",
        "group": "Detection & Fusion",
        "value_type": "int",
        "input_type": "number",
        "min": 0,
        "max": 600,
        "step": 1,
        "live_apply": True,
    },
    "AUTHORIZED_PRESENCE_LOGGING_ENABLED": {
        "description": "Auto-log authorized re-entry events from live camera view",
        "group": "Detection & Fusion",
        "value_type": "bool",
        "input_type": "switch",
        "live_apply": True,
    },
    "AUTHORIZED_PRESENCE_SCAN_SECONDS": {
        "description": "Face-presence scan interval in seconds",
        "group": "Detection & Fusion",
        "value_type": "int",
        "input_type": "number",
        "min": 1,
        "max": 30,
        "step": 1,
        "live_apply": True,
    },
    "AUTHORIZED_PRESENCE_COOLDOWN_SECONDS": {
        "description": "Cooldown before logging another authorized re-entry",
        "group": "Detection & Fusion",
        "value_type": "int",
        "input_type": "number",
        "min": 5,
        "max": 600,
        "step": 1,
        "live_apply": True,
    },
    "UNKNOWN_PRESENCE_LOGGING_ENABLED": {
        "description": "Auto-log unknown-person re-entry events from live camera view",
        "group": "Detection & Fusion",
        "value_type": "bool",
        "input_type": "switch",
        "live_apply": True,
    },
    "UNKNOWN_PRESENCE_COOLDOWN_SECONDS": {
        "description": "Cooldown before logging another unknown-person re-entry",
        "group": "Detection & Fusion",
        "value_type": "int",
        "input_type": "number",
        "min": 5,
        "max": 600,
        "step": 1,
        "live_apply": True,
    },
    "NODE_OFFLINE_SECONDS": {
        "description": "Seconds before sensor node is marked offline",
        "group": "Retention & Health",
        "value_type": "int",
        "input_type": "number",
        "min": 20,
        "max": 3600,
        "step": 1,
        "live_apply": True,
    },
    "CAMERA_OFFLINE_SECONDS": {
        "description": "Seconds before camera stream is marked disconnected",
        "group": "Retention & Health",
        "value_type": "int",
        "input_type": "number",
        "min": 10,
        "max": 600,
        "step": 1,
        "live_apply": True,
    },
    "EVENT_RETENTION_DAYS": {
        "description": "Event retention window",
        "group": "Retention & Health",
        "value_type": "int",
        "input_type": "number",
        "min": 1,
        "max": 365,
        "step": 1,
        "live_apply": True,
    },
    "LOG_RETENTION_DAYS": {
        "description": "System log retention window",
        "group": "Retention & Health",
        "value_type": "int",
        "input_type": "number",
        "min": 1,
        "max": 365,
        "step": 1,
        "live_apply": True,
    },
    "REGULAR_SNAPSHOT_RETENTION_DAYS": {
        "description": "Regular snapshot retention window",
        "group": "Retention & Health",
        "value_type": "int",
        "input_type": "number",
        "min": 1,
        "max": 365,
        "step": 1,
        "live_apply": True,
    },
    "CRITICAL_SNAPSHOT_RETENTION_DAYS": {
        "description": "Critical snapshot retention window",
        "group": "Retention & Health",
        "value_type": "int",
        "input_type": "number",
        "min": 1,
        "max": 365,
        "step": 1,
        "live_apply": True,
    },
    "mobile_remote_enabled": {
        "description": "Enable mobile remote web interface",
        "group": "Notifications",
        "value_type": "bool",
        "input_type": "switch",
        "live_apply": True,
    },
    "mobile_push_enabled": {
        "description": "Enable web push delivery for mobile devices",
        "group": "Notifications",
        "value_type": "bool",
        "input_type": "switch",
        "live_apply": True,
    },
    "LAN_BASE_URL": {
        "description": "Optional fixed local backend URL; leave blank to auto-detect LAN IP",
        "group": "Connectivity",
        "value_type": "url",
        "input_type": "text",
        "allow_empty": True,
        "live_apply": True,
    },
    "TAILSCALE_BASE_URL": {
        "description": "Tailscale backend URL used by mobile clients outside the local network",
        "group": "Connectivity",
        "value_type": "url",
        "input_type": "text",
        "allow_empty": True,
        "live_apply": True,
    },
    "CAMERA_INDOOR_STREAM_URL": {
        "description": "Indoor camera RTSP stream URL",
        "group": "Connectivity",
        "value_type": "str",
        "input_type": "text",
        "allow_empty": True,
        "live_apply": True,
    },
    "CAMERA_DOOR_STREAM_URL": {
        "description": "Door camera RTSP stream URL",
        "group": "Connectivity",
        "value_type": "str",
        "input_type": "text",
        "allow_empty": True,
        "live_apply": True,
    },
    "WEBPUSH_VAPID_PUBLIC_KEY": {
        "description": "VAPID public key used by web push subscriptions",
        "group": "Secrets",
        "value_type": "str",
        "input_type": "secret",
        "secret": True,
        "live_apply": True,
    },
    "WEBPUSH_VAPID_PRIVATE_KEY": {
        "description": "VAPID private key used for web push delivery",
        "group": "Secrets",
        "value_type": "str",
        "input_type": "secret",
        "secret": True,
        "live_apply": True,
    },
    "WEBPUSH_VAPID_SUBJECT": {
        "description": "Contact subject used for web push headers",
        "group": "Secrets",
        "value_type": "str",
        "input_type": "text",
        "secret": True,
        "live_apply": True,
    },
    "SENSOR_EVENT_URL": {
        "description": "HTTP sensor event ingest endpoint",
        "group": "Read Only",
        "value_type": "str",
        "input_type": "text",
        "editable": False,
        "live_apply": False,
    },
    "TRANSPORT_MODE": {
        "description": "Node transport protocol",
        "group": "Read Only",
        "value_type": "str",
        "input_type": "text",
        "editable": False,
        "live_apply": False,
    },
}


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on", "enabled"}:
        return True
    if normalized in {"0", "false", "no", "off", "disabled"}:
        return False
    raise ValueError("value must be true or false")


def _runtime_default_value(key: str, settings: Settings) -> str:
    if key == "FACE_COSINE_THRESHOLD":
        return str(settings.face_cosine_threshold)
    if key == "FIRE_MODEL_ENABLED":
        return "true" if settings.fire_model_enabled else "false"
    if key == "FIRE_MODEL_THRESHOLD":
        return str(settings.fire_model_threshold)
    if key == "INTRUDER_EVENT_COOLDOWN_SECONDS":
        return str(settings.intruder_event_cooldown_seconds)
    if key == "AUTHORIZED_PRESENCE_LOGGING_ENABLED":
        return "true" if settings.authorized_presence_logging_enabled else "false"
    if key == "AUTHORIZED_PRESENCE_SCAN_SECONDS":
        return str(settings.authorized_presence_scan_seconds)
    if key == "AUTHORIZED_PRESENCE_COOLDOWN_SECONDS":
        return str(settings.authorized_presence_cooldown_seconds)
    if key == "UNKNOWN_PRESENCE_LOGGING_ENABLED":
        return "true" if settings.unknown_presence_logging_enabled else "false"
    if key == "UNKNOWN_PRESENCE_COOLDOWN_SECONDS":
        return str(settings.unknown_presence_cooldown_seconds)
    if key == "NODE_OFFLINE_SECONDS":
        return str(settings.node_offline_seconds)
    if key == "CAMERA_OFFLINE_SECONDS":
        return str(settings.camera_offline_seconds)
    if key == "EVENT_RETENTION_DAYS":
        return str(settings.event_retention_days)
    if key == "LOG_RETENTION_DAYS":
        return str(settings.log_retention_days)
    if key == "REGULAR_SNAPSHOT_RETENTION_DAYS":
        return str(settings.regular_snapshot_retention_days)
    if key == "CRITICAL_SNAPSHOT_RETENTION_DAYS":
        return str(settings.critical_snapshot_retention_days)
    if key == "mobile_remote_enabled":
        return "false"
    if key == "mobile_push_enabled":
        return "true"
    if key == "LAN_BASE_URL":
        return settings.lan_base_url
    if key == "TAILSCALE_BASE_URL":
        return settings.tailscale_base_url
    if key == "CAMERA_INDOOR_STREAM_URL":
        return settings.camera_indoor_rtsp
    if key == "CAMERA_DOOR_STREAM_URL":
        return settings.camera_door_rtsp
    if key == "WEBPUSH_VAPID_PUBLIC_KEY":
        return settings.webpush_vapid_public_key
    if key == "WEBPUSH_VAPID_PRIVATE_KEY":
        return settings.webpush_vapid_private_key
    if key == "WEBPUSH_VAPID_SUBJECT":
        return settings.webpush_vapid_subject
    if key == "SENSOR_EVENT_URL":
        return "http://127.0.0.1:8765/api/sensors/event"
    if key == "TRANSPORT_MODE":
        return "HTTP"
    return ""


def _normalize_runtime_setting_value(key: str, value: str, settings: Settings) -> str:
    spec = RUNTIME_SETTING_SPECS[key]
    value_type = str(spec.get("value_type") or "str")
    raw = value.strip()

    if value_type == "bool":
        return "true" if _parse_bool(raw) else "false"

    if value_type == "int":
        parsed = int(raw)
        min_value = int(spec.get("min", -2147483648))
        max_value = int(spec.get("max", 2147483647))
        if parsed < min_value or parsed > max_value:
            raise ValueError(f"value must be between {min_value} and {max_value}")
        return str(parsed)

    if value_type == "float":
        parsed = float(raw)
        min_value = float(spec.get("min", -1.0e30))
        max_value = float(spec.get("max", 1.0e30))
        if parsed < min_value or parsed > max_value:
            raise ValueError(f"value must be between {min_value} and {max_value}")
        step = float(spec.get("step", 0.01))
        decimals = 2 if step >= 0.01 else 4
        return f"{parsed:.{decimals}f}".rstrip("0").rstrip(".")

    if value_type == "url":
        if not raw:
            if bool(spec.get("allow_empty", False)):
                return ""
            raise ValueError("value is required")
        candidate = raw if "://" in raw else f"http://{raw}"
        parsed = urlparse(candidate)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("value must be a valid http(s) URL")
        path = parsed.path.rstrip("/")
        return f"{parsed.scheme}://{parsed.netloc}{path}".rstrip("/")

    if bool(spec.get("secret")):
        return raw

    if not raw:
        if bool(spec.get("allow_empty", False)):
            return ""
        default_value = _runtime_default_value(key, settings).strip()
        if default_value:
            return default_value
        raise ValueError("value is required")
    return raw


def _runtime_effective_value(key: str, settings: Settings) -> str:
    stored = store.get_setting(key)
    if stored is not None:
        candidate = str(stored).strip()
    else:
        candidate = _runtime_default_value(key, settings).strip()

    try:
        return _normalize_runtime_setting_value(key, candidate, settings)
    except Exception:
        return _normalize_runtime_setting_value(
            key, _runtime_default_value(key, settings), settings
        )


def _runtime_settings(settings: Settings) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for key, spec in RUNTIME_SETTING_SPECS.items():
        effective_value = _runtime_effective_value(key, settings)
        is_secret = bool(spec.get("secret", False))

        item: dict[str, Any] = {
            "key": key,
            "value": "" if is_secret else effective_value,
            "description": str(spec.get("description") or ""),
            "editable": bool(spec.get("editable", True)),
            "secret": is_secret,
            "configured": bool(effective_value) if is_secret else False,
            "group": str(spec.get("group") or "Runtime"),
            "input_type": str(spec.get("input_type") or "text"),
            "live_apply": bool(spec.get("live_apply", False)),
        }
        if "min" in spec:
            item["min"] = spec["min"]
        if "max" in spec:
            item["max"] = spec["max"]
        if "step" in spec:
            item["step"] = spec["step"]
        items.append(item)
    return items


def _backup_dir(settings: Settings) -> Path:
    path = Path(settings.storage_root) / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _list_backup_files(settings: Settings) -> list[Path]:
    path = _backup_dir(settings)
    files = [item for item in path.iterdir() if item.is_file() and item.suffix == ".zip"]
    files.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    return files


def _build_backup_archive(settings: Settings, *, prefix: str = "thesis_backup", include_snapshots: bool = True) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_name = f"{prefix}_{stamp}.zip"
    archive_path = _backup_dir(settings) / archive_name

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        db_path = Path(settings.db_path)
        if db_path.exists() and db_path.is_file():
            archive.write(db_path, arcname="db/system.db")

        snapshot_root = Path(settings.snapshot_root)
        if include_snapshots and snapshot_root.exists() and snapshot_root.is_dir():
            for file_path in snapshot_root.rglob("*"):
                if file_path.is_file():
                    archive.write(file_path, arcname=f"snapshots/{file_path.relative_to(snapshot_root)}")

        manifest = {
            "created_ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "backend_port": int(settings.backend_port),
            "db_path": str(settings.db_path),
            "snapshot_root": str(settings.snapshot_root),
            "include_snapshots": bool(include_snapshots),
        }
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))

    return archive_path


def _restore_backup_archive(settings: Settings, name: str, *, include_snapshots: bool) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+\.zip", name):
        raise HTTPException(status_code=400, detail="invalid backup name")

    backup_root = _backup_dir(settings).resolve()
    archive_path = (backup_root / name).resolve()
    if archive_path != backup_root and backup_root not in archive_path.parents:
        raise HTTPException(status_code=404, detail="backup not found")
    if not archive_path.exists() or not archive_path.is_file():
        raise HTTPException(status_code=404, detail="backup not found")

    db_path = Path(settings.db_path)
    snapshot_root = Path(settings.snapshot_root)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_root.mkdir(parents=True, exist_ok=True)

    rollback_archive = _build_backup_archive(
        settings,
        prefix="thesis_pre_restore",
        include_snapshots=True,
    )

    restored_snapshots = 0
    with zipfile.ZipFile(archive_path, "r") as archive:
        names = set(archive.namelist())
        if "db/system.db" not in names:
            raise HTTPException(status_code=400, detail="backup archive missing db/system.db")

        for member in names:
            if member.startswith("/") or ".." in member.split("/"):
                raise HTTPException(status_code=400, detail="backup archive contains unsafe paths")

        with archive.open("db/system.db", "r") as src, open(db_path, "wb") as dst:
            shutil.copyfileobj(src, dst)

        if include_snapshots:
            if snapshot_root.exists():
                shutil.rmtree(snapshot_root)
            snapshot_root.mkdir(parents=True, exist_ok=True)

            for member in archive.namelist():
                if not member.startswith("snapshots/"):
                    continue
                rel_name = member[len("snapshots/") :]
                if not rel_name or rel_name.endswith("/"):
                    continue
                target = (snapshot_root / rel_name).resolve()
                if target != snapshot_root and snapshot_root.resolve() not in target.parents:
                    raise HTTPException(status_code=400, detail="backup archive contains unsafe snapshot path")
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member, "r") as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                restored_snapshots += 1

    return {
        "snapshots_restored": restored_snapshots,
        "rollback_backup_name": rollback_archive.name,
        "scope": "database_and_snapshots" if include_snapshots else "database_only",
    }


def _apply_runtime_setting(key: str, value: str, request: Request) -> None:
    normalized_key = key.strip()
    event_engine = getattr(request.app.state, "event_engine", None)
    supervisor = getattr(request.app.state, "supervisor", None)
    face_service = getattr(request.app.state, "face_service", None)
    fire_service = getattr(request.app.state, "fire_service", None)
    notification_dispatcher = getattr(request.app.state, "notification_dispatcher", None)

    if normalized_key == "INTRUDER_EVENT_COOLDOWN_SECONDS" and event_engine is not None:
        event_engine.intruder_event_cooldown_seconds = max(0, int(value))
        return

    if normalized_key == "FACE_COSINE_THRESHOLD" and face_service is not None:
        face_service.cosine_threshold = float(value)
        return

    if normalized_key == "FIRE_MODEL_ENABLED":
        enabled = _parse_bool(value)
        if fire_service is not None:
            fire_service.enabled = enabled
        if supervisor is not None:
            deps_ready = supervisor.camera_manager is not None and supervisor.fire_service is not None
            supervisor.fire_continuous_detection_enabled = bool(enabled and deps_ready)
        return

    if normalized_key == "FIRE_MODEL_THRESHOLD" and fire_service is not None:
        fire_service.threshold = max(0.01, min(0.99, float(value)))
        return

    if normalized_key == "NODE_OFFLINE_SECONDS" and supervisor is not None:
        supervisor.node_offline_seconds = max(20, int(value))
        return

    if normalized_key == "CAMERA_OFFLINE_SECONDS" and supervisor is not None:
        supervisor.camera_offline_seconds = max(10, int(value))
        return

    if normalized_key == "EVENT_RETENTION_DAYS" and supervisor is not None:
        supervisor.event_retention_days = max(1, int(value))
        return

    if normalized_key == "LOG_RETENTION_DAYS" and supervisor is not None:
        supervisor.log_retention_days = max(1, int(value))
        return

    if normalized_key == "REGULAR_SNAPSHOT_RETENTION_DAYS" and supervisor is not None:
        supervisor.regular_snapshot_retention_days = max(1, int(value))
        return

    if normalized_key == "CRITICAL_SNAPSHOT_RETENTION_DAYS" and supervisor is not None:
        supervisor.critical_snapshot_retention_days = max(1, int(value))
        return

    if normalized_key == "AUTHORIZED_PRESENCE_LOGGING_ENABLED" and supervisor is not None:
        supervisor.authorized_presence_logging_enabled = _parse_bool(value)
        supervisor.face_presence_logging_enabled = bool(
            supervisor.authorized_presence_logging_enabled
            or supervisor.unknown_presence_logging_enabled
        )
        return

    if normalized_key == "UNKNOWN_PRESENCE_LOGGING_ENABLED" and supervisor is not None:
        supervisor.unknown_presence_logging_enabled = _parse_bool(value)
        supervisor.face_presence_logging_enabled = bool(
            supervisor.authorized_presence_logging_enabled
            or supervisor.unknown_presence_logging_enabled
        )
        return

    if normalized_key == "AUTHORIZED_PRESENCE_SCAN_SECONDS" and supervisor is not None:
        supervisor.authorized_presence_scan_seconds = max(1, int(value))
        return

    if normalized_key == "AUTHORIZED_PRESENCE_COOLDOWN_SECONDS" and supervisor is not None:
        supervisor.authorized_presence_cooldown_seconds = max(5, int(value))
        return

    if normalized_key == "UNKNOWN_PRESENCE_COOLDOWN_SECONDS" and supervisor is not None:
        supervisor.unknown_presence_cooldown_seconds = max(5, int(value))
        return

    if normalized_key in {"LAN_BASE_URL", "TAILSCALE_BASE_URL"}:
        mdns_publisher = getattr(request.app.state, "mdns_publisher", None)
        if normalized_key == "LAN_BASE_URL" and mdns_publisher is not None:
            mdns_publisher.stop()
            mdns_publisher.start()
        return

    if normalized_key in {"CAMERA_INDOOR_STREAM_URL", "CAMERA_DOOR_STREAM_URL"}:
        stream_applier = getattr(request.app.state, "apply_camera_stream_override", None)
        if stream_applier is None:
            raise ValueError("camera stream override service unavailable")
        node_id = "cam_indoor" if normalized_key == "CAMERA_INDOOR_STREAM_URL" else "cam_door"
        stream_applier(node_id, value)
        return

    if notification_dispatcher is not None:
        notification_dispatcher.apply_runtime_setting(normalized_key, value)


@router.get("/api/ui/events/live")
def ui_events_live(request: Request, limit: int = 250) -> dict:
    get_current_user(request)
    alerts = store.list_alerts(limit=limit)
    events = store.list_events(limit=limit)
    return {
        "alerts": [_alert_to_ui(row) for row in alerts],
        "events": [_event_to_ui(row) for row in events],
    }


@router.get("/api/alerts")
def api_alerts(
    request: Request,
    limit: int = 100,
    from_ts: str | None = None,
    to_ts: str | None = None,
) -> dict:
    get_current_user(request)
    normalized_from_ts = _normalize_query_timestamp(from_ts)
    normalized_to_ts = _normalize_query_timestamp(to_ts)
    if normalized_from_ts and normalized_to_ts and normalized_from_ts >= normalized_to_ts:
        raise HTTPException(
            status_code=400,
            detail="from_ts must be earlier than to_ts",
        )

    rows = store.list_alerts(
        limit=max(1, min(limit, 500)),
        from_ts=normalized_from_ts,
        to_ts=normalized_to_ts,
    )
    return {"ok": True, "alerts": [_alert_to_ui(row) for row in rows]}


@router.get("/api/events")
def api_events(
    request: Request,
    limit: int = 100,
    from_ts: str | None = None,
    to_ts: str | None = None,
) -> dict:
    get_current_user(request)
    normalized_from_ts = _normalize_query_timestamp(from_ts)
    normalized_to_ts = _normalize_query_timestamp(to_ts)
    if normalized_from_ts and normalized_to_ts and normalized_from_ts >= normalized_to_ts:
        raise HTTPException(
            status_code=400,
            detail="from_ts must be earlier than to_ts",
        )

    rows = store.list_events(
        limit=max(1, min(limit, 500)),
        from_ts=normalized_from_ts,
        to_ts=normalized_to_ts,
    )
    return {"ok": True, "events": [_event_to_ui(row) for row in rows]}


@router.get("/api/nodes")
def api_nodes(request: Request) -> dict:
    payload = ui_nodes_live(request)
    return {"ok": True, "nodes": payload.get("sensor_statuses", [])}


@router.get("/api/sensors")
def api_sensors(request: Request) -> dict:
    payload = ui_nodes_live(request)
    rows = payload.get("sensor_statuses", [])
    sensors = [
        row
        for row in rows
        if str(row.get("type") or "").strip().lower() in {"smoke", "force"}
    ]
    return {"ok": True, "sensors": sensors}


@router.get("/api/status")
def api_status(request: Request) -> dict:
    payload = ui_nodes_live(request)
    nodes = payload.get("sensor_statuses", [])
    online = sum(1 for row in nodes if str(row.get("status") or "").lower() == "online")
    offline = sum(1 for row in nodes if str(row.get("status") or "").lower() != "online")
    return {
        "ok": True,
        "backend": "online",
        "active_alerts": int(payload.get("system_health", {}).get("active_alerts", 0)),
        "nodes_online": online,
        "nodes_offline": offline,
        "last_sync": str(payload.get("system_health", {}).get("last_sync") or ""),
    }


@router.get("/api/health")
def api_health(request: Request) -> dict:
    return api_status(request)


def _resolve_assistant_question_id(question_id: str, question: str) -> str:
    normalized_id = question_id.strip().lower()
    if normalized_id:
        return normalized_id

    text = question.strip().lower()
    if "status" in text:
        return "current_system_status"
    if "last alert" in text or "trigger" in text:
        return "last_alert_reason"
    if "smoke" in text and "which" in text:
        return "which_node_detected_smoke"
    if "offline" in text:
        return "are_any_nodes_offline"
    if "intrusion" in text:
        return "recent_intrusion_events"
    if "warning" in text:
        return "explain_current_warning"
    return "current_system_status"


@router.post("/api/assistant/query")
def assistant_query(payload: AssistantQueryRequest, request: Request) -> dict:
    get_current_user(request)
    resolved_id = _resolve_assistant_question_id(
        payload.question_id or "", payload.question or ""
    )

    nodes_payload = ui_nodes_live(request)
    node_rows = list(nodes_payload.get("sensor_statuses", []))
    active_alerts = store.list_active_alerts()
    alerts = store.list_alerts(limit=5)
    events = store.list_events(limit=50)

    if resolved_id == "current_system_status":
        online = sum(
            1
            for row in node_rows
            if str(row.get("status") or "").strip().lower() == "online"
        )
        total = len(node_rows)
        answer = (
            f"The system is online. {online} of {total} monitored nodes are online, "
            f"and there are {len(active_alerts)} active alerts."
        )
    elif resolved_id == "last_alert_reason":
        if alerts:
            latest = _alert_to_ui(alerts[0])
            title = _assistant_friendly_text(latest.get("title") or "Alert")
            source_node = _assistant_node_label(latest.get("source_node"))
            location = str(latest.get("location") or "").strip()
            detail = _assistant_friendly_text(
                latest.get("description") or "No extra details were provided."
            )
            location_text = f" in {location}" if location else ""
            answer = (
                f"The latest alert is '{title}' from {source_node}{location_text}. "
                f"{detail}"
            )
        else:
            answer = "No alerts have been recorded yet."
    elif resolved_id == "which_node_detected_smoke":
        smoke_event = next(
            (
                row
                for row in events
                if str(row.get("event_code") or "").strip().upper() == "SMOKE_HIGH"
            ),
            None,
        )
        if smoke_event is None:
            answer = "No recent high-smoke detection is recorded."
        else:
            source_node = _assistant_node_label(smoke_event.get("source_node"))
            location = str(smoke_event.get("location") or "").strip()
            location_text = f" in {location}" if location else ""
            answer = (
                f"The most recent high-smoke detection came from {source_node}{location_text}."
            )
    elif resolved_id == "are_any_nodes_offline":
        offline_nodes = [
            row
            for row in node_rows
            if str(row.get("status") or "").strip().lower() != "online"
        ]
        if not offline_nodes:
            answer = "All monitored nodes are currently online."
        else:
            labels = ", ".join(
                _assistant_node_label(row.get("id") or "node")
                for row in offline_nodes
            )
            answer = f"These nodes are currently offline: {labels}."
    elif resolved_id == "recent_intrusion_events":
        intrusion_rows = [
            row
            for row in events
            if str(row.get("type") or "").strip().lower() == "intruder"
        ][:5]
        if not intrusion_rows:
            answer = "No recent intrusion events are recorded."
        else:
            first = intrusion_rows[0]
            source_node = _assistant_node_label(first.get("source_node"))
            title = _assistant_friendly_text(first.get("title") or "Intrusion event")
            answer = (
                f"There are {len(intrusion_rows)} recent intrusion events. "
                f"The latest is '{title}' from {source_node}."
            )
    elif resolved_id == "explain_current_warning":
        warning_alert = next(
            (
                row
                for row in alerts
                if str(row.get("severity") or "").strip().lower() in {"warning", "critical"}
            ),
            None,
        )
        if warning_alert is None:
            answer = "There is no active warning alert right now."
        else:
            latest = _alert_to_ui(warning_alert)
            title = _assistant_friendly_text(latest.get("title") or "Warning")
            source_node = _assistant_node_label(latest.get("source_node"))
            detail = _assistant_friendly_text(
                latest.get("description") or "Please open Alerts for details."
            )
            answer = (
                f"Current warning is '{title}' from {source_node}. "
                f"{detail}"
            )
    else:
        answer = "Unsupported assistant question. Use a predefined question_id."

    return {"ok": True, "question_id": resolved_id, "answer": answer}


@router.get("/api/ui/nodes/live")
def ui_nodes_live(request: Request) -> dict:
    get_current_user(request)
    settings: Settings = request.app.state.settings
    devices = store.list_devices()
    cameras = store.list_cameras()

    now_iso = datetime.now(timezone.utc).isoformat()
    camera_defaults = {
        "cam_indoor": {
            "label": "Indoor RTSP Camera",
            "location": "Living Room",
        },
        "cam_door": {
            "label": "Door RTSP Camera",
            "location": "Door Entrance Area",
        },
    }

    device_by_node: dict[str, dict[str, Any]] = {
        str(row.get("node_id") or "").strip().lower(): row for row in devices
    }
    camera_by_node: dict[str, dict[str, Any]] = {
        str(row.get("node_id") or "").strip().lower(): row for row in cameras
    }

    camera_timeout_seconds = max(10, int(settings.camera_offline_seconds))
    now_dt = datetime.now(timezone.utc)

    def _camera_is_online(row: dict[str, Any]) -> bool:
        last_seen_raw = str(row.get("last_seen_ts") or "").strip()
        if not last_seen_raw:
            return False
        try:
            seen_dt = datetime.fromisoformat(last_seen_raw.replace("Z", "+00:00"))
        except ValueError:
            return False
        if seen_dt.tzinfo is None:
            seen_dt = seen_dt.replace(tzinfo=timezone.utc)
        else:
            seen_dt = seen_dt.astimezone(timezone.utc)
        return (now_dt - seen_dt).total_seconds() <= float(camera_timeout_seconds)

    camera_status_by_node: dict[str, str] = {
        node_id: ("online" if _camera_is_online(row) else "offline")
        for node_id, row in camera_by_node.items()
    }

    sensor_statuses = []
    for row in devices:
        node_id = str(row.get("node_id") or "").strip().lower()
        if _is_dashboard_noise_node(node_id):
            continue
        if str(row.get("device_type") or "").strip().lower() == "camera":
            continue
        sensor_statuses.append(
            {
                "id": node_id,
                "name": str(row["label"]),
                "location": str(row.get("location") or "System"),
                "type": "force"
                if str(row.get("device_type")) == "force"
                else ("camera" if str(row.get("device_type")) == "camera" else "smoke"),
                "status": "online" if str(row.get("status")) == "online" else "offline",
                "last_update": str(row.get("last_seen_ts") or now_iso),
                "note": str(row.get("note") or ""),
            }
        )

    for camera_node in ("cam_indoor", "cam_door"):
        cam_row = camera_by_node.get(camera_node, {})
        device_row = device_by_node.get(camera_node, {})
        defaults = camera_defaults[camera_node]
        display_status = camera_status_by_node.get(camera_node, "offline")

        runtime_error = str(cam_row.get("last_error") or "").strip()
        device_note = str(device_row.get("note") or "").strip()
        if runtime_error:
            note = runtime_error
        elif device_note and device_note.lower() != "heartbeat":
            note = device_note
        elif display_status == "online":
            note = "stream active"
        else:
            note = "stream unavailable"

        sensor_statuses.append(
            {
                "id": camera_node,
                "name": str(cam_row.get("label") or defaults["label"]),
                "location": str(cam_row.get("location") or defaults["location"]),
                "type": "camera",
                "status": display_status,
                "last_update": str(
                    cam_row.get("last_seen_ts")
                    or device_row.get("last_seen_ts")
                    or now_iso
                ),
                "note": note,
            }
        )

    service_statuses = [
        {
            "id": "desktop_backend",
            "name": "FastAPI Local Backend",
            "status": "online",
            "endpoint": "http://127.0.0.1:8765",
            "last_update": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "detail": "Local backend process active",
        },
        {
            "id": "sensor_transport",
            "name": "HTTP Sensor Transport",
            "status": "online"
            if any(item["status"] == "online" for item in sensor_statuses)
            else "warning",
            "endpoint": "POST /api/sensors/event",
            "last_update": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "detail": "ESP32-C3 nodes communicating via HTTP",
        },
        {
            "id": "camera_manager",
            "name": "RTSP Camera Manager",
            "status": "online"
            if any(status == "online" for status in camera_status_by_node.values())
            else "warning",
            "endpoint": "RTSP pull workers",
            "last_update": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "detail": "Persistent stream monitoring with reconnect",
        },
    ]

    camera_feeds = []
    for cam in cameras:
        node_id = str(cam.get("node_id") or "").strip().lower()
        display_status = camera_status_by_node.get(node_id, "offline")
        camera_feeds.append(
            {
                "location": str(cam.get("location") or ""),
                "node_id": node_id,
                "status": display_status,
                "quality": "720p",
                "fps": int(cam.get("fps_target") or settings.camera_processing_fps),
                "latency_ms": 120,
                "stream_path": f"/camera/stream/{node_id}",
                "stream_available": display_status == "online",
            }
        )

    active_alerts = store.list_active_alerts()

    return {
        "sensor_statuses": sensor_statuses,
        "service_statuses": service_statuses,
        "camera_feeds": camera_feeds,
        "detection_pipelines": [
            {
                "name": "Intrusion Event Pipeline",
                "state": "active",
                "detail": "Door-force/person triggers run selective face matching",
            },
            {
                "name": "Continuous Fire Vision Pipeline",
                "state": "active",
                "detail": "Camera frames are scanned continuously for flame; smoke warnings remain independent",
            },
            {
                "name": "Retention Cleanup",
                "state": "active",
                "detail": "Background retention job enforces 30/90-day windows",
            },
        ],
        "system_health": {
            "host": "online",
            "sensor_transport": "connected"
            if any(item["status"] == "online" for item in sensor_statuses)
            else "disconnected",
            "backend": "online",
            "last_sync": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "uptime": "running",
            "active_alerts": len(active_alerts),
        },
    }


@router.get("/api/ui/stats/daily")
def ui_stats_daily(request: Request, days: int = 7) -> dict:
    get_current_user(request)
    return {"stats": store.daily_stats(days)}


@router.get("/api/ui/settings/live")
def ui_settings_live(request: Request) -> dict:
    get_current_user(request)
    settings: Settings = request.app.state.settings
    faces = store.list_faces()
    return {
        "guest_mode": False,
        "authorized_profiles": [
            {
                "id": f"auth-{int(row['id']):03d}",
                "db_id": int(row["id"]),
                "label": str(row["name"]),
                "role": str(row.get("note") or "").strip() or "Authorized",
                "note": str(row.get("note") or "").strip(),
                "enrolled_at": str(row["created_ts"]),
                "sample_count": int(row.get("sample_count") or 0),
            }
            for row in faces
        ],
        "runtime_settings": _runtime_settings(settings),
    }


@router.post("/api/ui/settings/runtime")
def ui_runtime_setting_update(
    payload: RuntimeSettingUpdateRequest, request: Request
) -> dict:
    get_current_user(request)
    settings: Settings = request.app.state.settings
    requested_key = payload.key.strip()

    key = ""
    for candidate in (requested_key, requested_key.upper(), requested_key.lower()):
        if candidate in RUNTIME_SETTING_SPECS:
            key = candidate
            break
    if not key:
        raise HTTPException(status_code=400, detail="unsupported runtime setting")

    spec = RUNTIME_SETTING_SPECS[key]
    if not bool(spec.get("editable", True)):
        raise HTTPException(status_code=400, detail="runtime setting is read-only")

    try:
        normalized_value = _normalize_runtime_setting_value(key, payload.value, settings)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    store.upsert_setting(key, normalized_value)
    _apply_runtime_setting(key, normalized_value, request)

    is_secret = bool(spec.get("secret", False))
    return {
        "ok": True,
        "key": key,
        "value": "" if is_secret else normalized_value,
        "description": str(spec.get("description") or ""),
        "secret": is_secret,
        "configured": bool(normalized_value) if is_secret else False,
        "group": str(spec.get("group") or "Runtime"),
        "input_type": str(spec.get("input_type") or "text"),
        "live_apply": bool(spec.get("live_apply", False)),
    }


@router.get("/api/ui/backup/status")
def ui_backup_status(request: Request) -> dict:
    get_current_user(request)
    settings: Settings = request.app.state.settings
    files = _list_backup_files(settings)
    latest = files[0] if files else None
    return {
        "ok": True,
        "count": len(files),
        "files": [
            {
                "name": item.name,
                "size_bytes": int(item.stat().st_size),
                "modified_ts": datetime.fromtimestamp(
                    item.stat().st_mtime, tz=timezone.utc
                ).isoformat(timespec="seconds"),
            }
            for item in files
        ],
        "latest": {
            "name": latest.name,
            "size_bytes": int(latest.stat().st_size),
            "modified_ts": datetime.fromtimestamp(
                latest.stat().st_mtime, tz=timezone.utc
            ).isoformat(timespec="seconds"),
        }
        if latest
        else None,
    }


@router.post("/api/ui/backup/create")
def ui_backup_create(request: Request) -> dict:
    get_current_user(request)
    settings: Settings = request.app.state.settings
    archive_path = _build_backup_archive(settings)
    return {
        "ok": True,
        "name": archive_path.name,
        "size_bytes": int(archive_path.stat().st_size),
    }


@router.get("/api/ui/backup/download/{name}")
def ui_backup_download(name: str, request: Request) -> FileResponse:
    get_current_user(request)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+\.zip", name):
        raise HTTPException(status_code=400, detail="invalid backup name")
    settings: Settings = request.app.state.settings
    target = (_backup_dir(settings) / name).resolve()
    backup_root = _backup_dir(settings).resolve()
    if target != backup_root and backup_root not in target.parents:
        raise HTTPException(status_code=404, detail="backup not found")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="backup not found")
    return FileResponse(target, filename=name, media_type="application/zip")


@router.post("/api/ui/backup/restore")
def ui_backup_restore(payload: BackupRestoreRequest, request: Request) -> dict:
    get_current_user(request)
    settings: Settings = request.app.state.settings
    result = _restore_backup_archive(
        settings,
        payload.name.strip(),
        include_snapshots=bool(payload.include_snapshots),
    )
    return {
        "ok": True,
        "name": payload.name.strip(),
        "snapshots_restored": int(result.get("snapshots_restored", 0)),
        "rollback_backup_name": str(result.get("rollback_backup_name") or ""),
        "scope": str(result.get("scope") or "database_only"),
        "message": "Backup restored safely. A pre-restore rollback backup was created; restart backend to ensure all services use restored state.",
    }


@router.get("/api/ui/retention/status")
def ui_retention_status(request: Request) -> dict:
    get_current_user(request)
    settings: Settings = request.app.state.settings

    def _read_int(key: str, fallback: int) -> int:
        raw = store.get_setting(key)
        try:
            return int(str(raw).strip()) if raw is not None else int(fallback)
        except ValueError:
            return int(fallback)

    return {
        "ok": True,
        "event_retention_days": _read_int("EVENT_RETENTION_DAYS", settings.event_retention_days),
        "log_retention_days": _read_int("LOG_RETENTION_DAYS", settings.log_retention_days),
        "regular_snapshot_retention_days": _read_int(
            "REGULAR_SNAPSHOT_RETENTION_DAYS", settings.regular_snapshot_retention_days
        ),
        "critical_snapshot_retention_days": _read_int(
            "CRITICAL_SNAPSHOT_RETENTION_DAYS", settings.critical_snapshot_retention_days
        ),
        "last_run_ts": str(store.get_setting("RETENTION_LAST_RUN_TS") or ""),
        "last_events_deleted": _read_int("RETENTION_LAST_EVENTS_DELETED", 0),
        "last_logs_deleted": _read_int("RETENTION_LAST_LOGS_DELETED", 0),
        "last_snapshots_deleted": _read_int("RETENTION_LAST_SNAPSHOTS_DELETED", 0),
    }


@router.post("/api/ui/camera/control")
def ui_camera_control(payload: CameraControlRequest, request: Request) -> dict:
    get_current_user(request)
    cmd = payload.command.strip().lower()
    if cmd not in {"flash_on", "flash_off", "flash_pulse", "status"}:
        raise HTTPException(status_code=400, detail="unsupported camera command")
    controller = getattr(request.app.state, "camera_http_controller", None)
    if controller is None:
        raise HTTPException(
            status_code=503, detail="camera control service unavailable"
        )
    result = controller.send_command(payload.node_id, cmd)
    if not result.ok:
        raise HTTPException(status_code=502, detail=result.detail)
    return {
        "ok": True,
        "node_id": payload.node_id,
        "command": cmd,
        "topic": result.endpoint,
        "detail": result.detail,
    }


@router.post("/ack/{alert_id}")
def ack_compat(alert_id: int, request: Request) -> Response:
    user = get_current_user(request)
    ok = store.ack_alert(alert_id, ack_by=user["username"], status="ACK")
    if not ok:
        raise HTTPException(
            status_code=404, detail="alert not found or already acknowledged"
        )
    return JSONResponse({"ok": True, "alert_id": alert_id})


@router.post("/api/alerts/{alert_id}/ack")
def ack_json(alert_id: int, request: Request) -> dict:
    user = get_current_user(request)
    ok = store.ack_alert(alert_id, ack_by=user["username"], status="ACK")
    if not ok:
        raise HTTPException(
            status_code=404, detail="alert not found or already acknowledged"
        )
    return {"ok": True}


@router.post("/api/alerts/{alert_id}/acknowledge")
def ack_json_alias(alert_id: int, request: Request) -> dict:
    return ack_json(alert_id, request)


@router.post("/api/alerts/{alert_id}/review")
def update_alert_review(
    alert_id: int,
    payload: AlertReviewUpdateRequest,
    request: Request,
) -> dict:
    user = get_current_user(request)
    normalized_status = payload.review_status.strip().lower()
    allowed_statuses = {
        "needs_review",
        "confirmed",
        "false_positive",
        "resolved",
        "archived",
    }
    if normalized_status not in allowed_statuses:
        raise HTTPException(status_code=400, detail="unsupported review status")

    updated = store.update_alert_review(
        alert_id=alert_id,
        review_status=normalized_status,
        review_note=payload.review_note,
        reviewed_by=str(user.get("username") or "admin"),
    )
    if not updated:
        raise HTTPException(status_code=404, detail="alert not found")

    row = store.get_alert(alert_id)
    if row is None:
        raise HTTPException(status_code=404, detail="alert not found")
    return {"ok": True, "alert": _alert_to_ui(row)}


@router.get("/api/alerts/{alert_id}/review/history")
def alert_review_history(alert_id: int, request: Request, limit: int = 50) -> dict:
    get_current_user(request)
    row = store.get_alert(alert_id)
    if row is None:
        raise HTTPException(status_code=404, detail="alert not found")
    history = store.list_alert_review_history(alert_id, limit=limit)
    return {"ok": True, "history": history}


@router.post("/api/alerts/{alert_id}/snapshot/delete")
def delete_alert_snapshot(alert_id: int, request: Request) -> dict:
    get_current_user(request)
    row = store.get_alert(alert_id)
    if row is None:
        raise HTTPException(status_code=404, detail="alert not found")

    settings: Settings = request.app.state.settings
    snapshot_root = Path(settings.snapshot_root).resolve()
    snapshot_path = str(row.get("snapshot_path") or "")

    deleted_file = False
    if snapshot_path:
        target = _snapshot_target_path(snapshot_path, snapshot_root)
        if target is not None and target.exists() and target.is_file():
            target.unlink(missing_ok=True)
            deleted_file = True

    if not store.clear_alert_snapshot_path(alert_id):
        raise HTTPException(status_code=404, detail="alert not found")

    return {"ok": True, "alert_id": int(alert_id), "deleted_file": deleted_file}


@router.get("/snapshots/{snapshot_rel_path:path}")
def snapshot_file(snapshot_rel_path: str, request: Request) -> FileResponse:
    get_current_user(request)
    settings: Settings = request.app.state.settings
    root = Path(settings.snapshot_root).resolve()
    target = (root / snapshot_rel_path).resolve()

    if target != root and root not in target.parents:
        raise HTTPException(status_code=404, detail="snapshot not found")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="snapshot not found")
    return FileResponse(target)


@router.get("/camera/frame/{node_id}")
def camera_frame(node_id: str, request: Request, face_debug: bool = False) -> Response:
    get_current_user(request)
    frame = request.app.state.camera_manager.snapshot_frame(node_id)
    if frame is None:
        raise HTTPException(status_code=404, detail="camera frame unavailable")

    if _face_debug_enabled_for_node(node_id, face_debug):
        _draw_face_debug_overlay(request, node_id, frame)

    ok, encoded = cv2.imencode(".jpg", frame)
    if not ok:
        raise HTTPException(status_code=500, detail="failed to encode frame")
    return Response(
        content=encoded.tobytes(),
        media_type="image/jpeg",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


def _draw_face_debug_overlay(request: Request, node_id: str, frame: Any) -> None:
    try:
        if frame is None or not hasattr(frame, "shape"):
            return
        if int(frame.size) <= 0:
            return

        normalized_node = node_id.strip().lower() or "unknown"
        now = time.monotonic()

        state_raw = getattr(request.app.state, "debug_overlay_state", None)
        state_by_node: dict[str, dict[str, Any]]
        if isinstance(state_raw, dict):
            state_by_node = cast(dict[str, dict[str, Any]], state_raw)
        else:
            state_by_node = {}
            request.app.state.debug_overlay_state = state_by_node
        node_state = state_by_node.setdefault(normalized_node, {})

        def _log_debug_error(message: str) -> None:
            last_log_at = float(node_state.get("last_log_at") or 0.0)
            if (now - last_log_at) < DEBUG_OVERLAY_LOG_INTERVAL_SECONDS:
                return
            node_state["last_log_at"] = now
            store.log("ERROR", f"debug overlay node={normalized_node}: {message}")

        def _mark_failure(message: str) -> None:
            failures = int(node_state.get("failures") or 0) + 1
            node_state["failures"] = failures
            node_state["last_failure_at"] = now
            if failures >= DEBUG_OVERLAY_MAX_CONSECUTIVE_FAILURES:
                node_state["cooldown_until"] = now + DEBUG_OVERLAY_FAILURE_COOLDOWN_SECONDS
            _log_debug_error(f"{message}; failures={failures}")

        def _mark_success() -> None:
            node_state["failures"] = 0
            node_state["cooldown_until"] = 0.0

        cooldown_until = float(node_state.get("cooldown_until") or 0.0)
        infer_allowed = now >= cooldown_until

        cache_raw = getattr(request.app.state, "face_debug_cache", None)
        cache: dict[str, dict[str, Any]]
        if isinstance(cache_raw, dict):
            cache = cast(dict[str, dict[str, Any]], cache_raw)
        else:
            cache = {}
            request.app.state.face_debug_cache = cache

        cached_entry = cache.get(normalized_node)
        verdicts: list[dict[str, Any]] = []
        if isinstance(cached_entry, dict):
            cached_verdicts = cached_entry.get("verdicts")
            if isinstance(cached_verdicts, list):
                verdicts = [
                    cast(dict[str, Any], item)
                    for item in cached_verdicts
                    if isinstance(item, dict)
                ]

        should_refresh_face = infer_allowed
        if isinstance(cached_entry, dict):
            cached_ts = float(cached_entry.get("ts") or 0.0)
            if (now - cached_ts) <= FACE_DEBUG_CLASSIFY_INTERVAL_SECONDS:
                should_refresh_face = False

        face_ok = True
        if should_refresh_face:
            try:
                latest = request.app.state.face_service.classify_faces_with_bbox(
                    frame, max_faces=5
                )
                verdicts = latest if isinstance(latest, list) else []
                cache[normalized_node] = {"ts": now, "verdicts": verdicts}
            except Exception as exc:
                face_ok = False
                _mark_failure(f"face inference failed: {exc}")

        drawn = 0
        for verdict in verdicts:
            bbox = verdict.get("bbox")
            if not (isinstance(bbox, list) and len(bbox) == 4):
                continue

            x, y, w, h = [int(value) for value in bbox]
            is_authorized = str(verdict.get("result") or "") == "authorized"
            color = (50, 205, 50) if is_authorized else (0, 165, 255)
            label_state = "AUTHORIZED" if is_authorized else "NON-AUTHORIZED"
            confidence = float(verdict.get("confidence") or 0.0)
            label = f"{label_state} {confidence:.1f}%"

            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            text_x = max(4, x)
            text_y = max(20, y - 8)
            cv2.putText(
                frame,
                label,
                (text_x, text_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                color,
                2,
                cv2.LINE_AA,
            )
            drawn += 1

        if drawn == 0:
            cv2.putText(
                frame,
                "No face detected",
                (12, 26),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (0, 165, 255),
                2,
                cv2.LINE_AA,
            )

        fire_cache_raw = getattr(request.app.state, "fire_debug_cache", None)
        fire_cache: dict[str, dict[str, Any]]
        if isinstance(fire_cache_raw, dict):
            fire_cache = cast(dict[str, dict[str, Any]], fire_cache_raw)
        else:
            fire_cache = {}
            request.app.state.fire_debug_cache = fire_cache

        fire_cached_entry = fire_cache.get(normalized_node)
        fire_result: dict[str, Any] = {}
        if isinstance(fire_cached_entry, dict):
            cached_result = fire_cached_entry.get("result")
            if isinstance(cached_result, dict):
                fire_result = cast(dict[str, Any], cached_result)

        should_refresh_fire = infer_allowed
        if isinstance(fire_cached_entry, dict):
            fire_cached_ts = float(fire_cached_entry.get("ts") or 0.0)
            if (now - fire_cached_ts) <= FIRE_DEBUG_CLASSIFY_INTERVAL_SECONDS:
                should_refresh_fire = False

        fire_ok = True
        if should_refresh_fire:
            try:
                frame_for_fire = frame.copy()
                latest_fire = request.app.state.fire_service.detect_flame(frame_for_fire)
                fire_result = latest_fire if isinstance(latest_fire, dict) else {}
                fire_cache[normalized_node] = {"ts": now, "result": fire_result}
            except Exception as exc:
                fire_ok = False
                _mark_failure(f"fire inference failed: {exc}")

        fire_score = float(fire_result.get("confidence") or 0.0)
        fire_detected = bool(fire_result.get("flame"))
        detected_class = str(fire_result.get("detected_class") or "none").strip().lower()
        class_label = (
            detected_class.upper() if detected_class and detected_class != "none" else "NONE"
        )
        fire_color = (0, 0, 255) if fire_detected else (60, 180, 255)
        fire_text = f"FIRE {'YES' if fire_detected else 'NO'} [{class_label}] {fire_score:.1f}%"
        cv2.putText(
            frame,
            fire_text,
            (12, 56),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            fire_color,
            2,
            cv2.LINE_AA,
        )

        fire_bbox = fire_result.get("bbox")
        if isinstance(fire_bbox, list) and len(fire_bbox) == 4:
            fx, fy, fw, fh = [int(value) for value in fire_bbox]
            cv2.rectangle(frame, (fx, fy), (fx + fw, fy + fh), fire_color, 2)
            region_label = (
                "FIRE REGION"
                if detected_class == "fire"
                else "SMOKE REGION"
                if detected_class == "smoke"
                else "DETECTION REGION"
            )
            cv2.putText(
                frame,
                region_label,
                (max(4, fx), max(74, fy - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                fire_color,
                2,
                cv2.LINE_AA,
            )

        if face_ok and fire_ok and infer_allowed:
            _mark_success()
    except Exception as exc:
        try:
            store.log("ERROR", f"debug overlay fatal node={node_id}: {exc}")
        except Exception:
            pass


@router.get("/camera/stream/{node_id}")
async def camera_stream(
    node_id: str,
    request: Request,
    face_debug: bool = False,
    fps: int = 20,
) -> Response:
    get_current_user(request)
    normalized_node = node_id.strip().lower()
    face_debug_enabled = _face_debug_enabled_for_node(normalized_node, face_debug)

    if normalized_node == "cam_door" and not face_debug_enabled:
        direct_stream_url = _direct_http_stream_url(normalized_node)
        if direct_stream_url:
            return RedirectResponse(url=direct_stream_url, status_code=307)

    target_fps = max(4, min(30, int(fps)))
    frame_wait = 1.0 / float(target_fps)

    async def _stream_bytes():
        while True:
            if await request.is_disconnected():
                break

            frame = request.app.state.camera_manager.snapshot_frame(node_id)
            if frame is None:
                await asyncio.sleep(0.15)
                continue

            if face_debug_enabled:
                _draw_face_debug_overlay(request, node_id, frame)

            ok, encoded = cv2.imencode(".jpg", frame)
            if not ok:
                await asyncio.sleep(frame_wait)
                continue

            payload = encoded.tobytes()
            header = (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n"
                + f"Content-Length: {len(payload)}\r\n".encode("ascii")
                + b"Cache-Control: no-cache\r\n"
                + b"Pragma: no-cache\r\n\r\n"
            )
            yield header + payload + b"\r\n"
            await asyncio.sleep(frame_wait)

    return StreamingResponse(
        _stream_bytes(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Accel-Buffering": "no",
        },
    )
