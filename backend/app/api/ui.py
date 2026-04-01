from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse

from ..core.auth import get_current_user
from ..core.config import Settings
from ..db import store
from ..schemas.api import CameraControlRequest

router = APIRouter(tags=["ui"])


def _safe_json(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


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
        "confidence": details.get("confidence"),
        "fusion_evidence": details.get("fusion_evidence") or [],
        "snapshot_path": snapshot_url,
    }


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
        "confidence": details.get("confidence"),
        "fusion_evidence": details.get("fusion_evidence") or [],
    }


def _runtime_settings(settings: Settings) -> list[dict[str, str]]:
    items = [
        {
            "key": "SENSOR_EVENT_URL",
            "value": "http://127.0.0.1:8765/api/sensors/event",
            "description": "HTTP sensor event ingest endpoint",
        },
        {
            "key": "CAMERA_SOURCE_MODE",
            "value": str(settings.camera_source_mode),
            "description": "Active camera source backend mode",
        },
        {
            "key": "CAMERA_WEBCAM_SINGLE_NODE",
            "value": str(settings.camera_webcam_single_node),
            "description": "Single-webcam mapped node in webcam mode",
        },
        {
            "key": "NODE_OFFLINE_SECONDS",
            "value": str(settings.node_offline_seconds),
            "description": "Seconds before sensor node is marked offline",
        },
        {
            "key": "CAMERA_OFFLINE_SECONDS",
            "value": str(settings.camera_offline_seconds),
            "description": "Seconds before camera stream is marked disconnected",
        },
        {
            "key": "CAMERA_PROCESSING_FPS",
            "value": str(settings.camera_processing_fps),
            "description": "Target processing FPS per camera",
        },
        {
            "key": "FACE_MATCH_THRESHOLD",
            "value": str(settings.face_match_threshold),
            "description": "Lower is stricter; higher reduces unknowns in webcam tests",
        },
        {
            "key": "AUTHORIZED_PRESENCE_LOGGING_ENABLED",
            "value": str(settings.authorized_presence_logging_enabled).lower(),
            "description": "Auto-log authorized re-entry events from live camera view",
        },
        {
            "key": "AUTHORIZED_PRESENCE_SCAN_SECONDS",
            "value": str(settings.authorized_presence_scan_seconds),
            "description": "Face-presence scan interval in seconds",
        },
        {
            "key": "AUTHORIZED_PRESENCE_COOLDOWN_SECONDS",
            "value": str(settings.authorized_presence_cooldown_seconds),
            "description": "Cooldown before logging another authorized re-entry",
        },
        {
            "key": "UNKNOWN_PRESENCE_LOGGING_ENABLED",
            "value": str(settings.unknown_presence_logging_enabled).lower(),
            "description": "Auto-log unknown-person re-entry events from live camera view",
        },
        {
            "key": "UNKNOWN_PRESENCE_COOLDOWN_SECONDS",
            "value": str(settings.unknown_presence_cooldown_seconds),
            "description": "Cooldown before logging another unknown-person re-entry",
        },
        {
            "key": "EVENT_RETENTION_DAYS",
            "value": str(settings.event_retention_days),
            "description": "Event retention window",
        },
        {
            "key": "REGULAR_SNAPSHOT_RETENTION_DAYS",
            "value": str(settings.regular_snapshot_retention_days),
            "description": "Regular snapshot retention window",
        },
        {
            "key": "CRITICAL_SNAPSHOT_RETENTION_DAYS",
            "value": str(settings.critical_snapshot_retention_days),
            "description": "Critical snapshot retention window",
        },
        {
            "key": "TRANSPORT_MODE",
            "value": "HTTP",
            "description": "Node transport protocol",
        },
    ]
    return items


@router.get("/api/ui/events/live")
def ui_events_live(request: Request, limit: int = 250) -> dict:
    get_current_user(request)
    alerts = store.list_alerts(limit=limit)
    events = store.list_events(limit=limit)
    return {
        "alerts": [_alert_to_ui(row) for row in alerts],
        "events": [_event_to_ui(row) for row in events],
    }


@router.get("/api/ui/nodes/live")
def ui_nodes_live(request: Request) -> dict:
    get_current_user(request)
    settings: Settings = request.app.state.settings
    devices = store.list_devices()
    cameras = store.list_cameras()

    sensor_statuses = []
    for row in devices:
        sensor_statuses.append(
            {
                "id": str(row["node_id"]),
                "name": str(row["label"]),
                "location": str(row.get("location") or "System"),
                "type": "force"
                if str(row.get("device_type")) == "force"
                else ("camera" if str(row.get("device_type")) == "camera" else "smoke"),
                "status": "online" if str(row.get("status")) == "online" else "offline",
                "last_update": str(
                    row.get("last_seen_ts") or datetime.now(timezone.utc).isoformat()
                ),
                "note": str(row.get("note") or ""),
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
            if any(str(cam.get("status")) == "online" for cam in cameras)
            else "warning",
            "endpoint": "RTSP pull workers",
            "last_update": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "detail": "Persistent stream monitoring with reconnect",
        },
    ]

    camera_feeds = []
    for cam in cameras:
        node_id = str(cam.get("node_id") or "")
        camera_feeds.append(
            {
                "location": str(cam.get("location") or ""),
                "node_id": node_id,
                "status": "online" if str(cam.get("status")) == "online" else "offline",
                "quality": "720p",
                "fps": int(cam.get("fps_target") or settings.camera_processing_fps),
                "latency_ms": 120,
                "stream_path": f"/camera/stream/{node_id}",
                "stream_available": str(cam.get("status")) == "online",
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
                "name": "Smoke-First Fire Pipeline",
                "state": "active",
                "detail": "Smoke threshold triggers indoor camera flame confirmation",
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
                "role": "Authorized",
                "enrolled_at": str(row["created_ts"]),
                "sample_count": int(row.get("sample_count") or 0),
            }
            for row in faces
        ],
        "runtime_settings": _runtime_settings(settings),
    }


@router.post("/api/ui/camera/control")
def ui_camera_control(payload: CameraControlRequest, request: Request) -> dict:
    get_current_user(request)
    cmd = payload.command.strip().lower()
    if cmd not in {"flash_on", "flash_off", "status"}:
        raise HTTPException(status_code=400, detail="unsupported camera command")
    return {
        "ok": True,
        "node_id": payload.node_id,
        "command": cmd,
        "topic": f"http://local-camera-control/{payload.node_id}/{cmd}",
        "detail": "RTSP IP cameras do not expose flash command in core phase; command acknowledged as stub.",
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

    if face_debug:
        _draw_face_debug_overlay(request, frame)

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


def _draw_face_debug_overlay(request: Request, frame: Any) -> None:
    try:
        verdict = request.app.state.face_service.classify_frame_with_bbox(frame)
        bbox = verdict.get("bbox")
        if isinstance(bbox, list) and len(bbox) == 4:
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
        else:
            reason = str(verdict.get("reason") or "No face detected")
            cv2.putText(
                frame,
                reason,
                (12, 26),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (0, 165, 255),
                2,
                cv2.LINE_AA,
            )
    except Exception:
        pass


@router.get("/camera/stream/{node_id}")
async def camera_stream(
    node_id: str,
    request: Request,
    face_debug: bool = False,
    fps: int = 12,
) -> StreamingResponse:
    get_current_user(request)
    target_fps = max(2, min(30, int(fps)))
    frame_wait = 1.0 / float(target_fps)

    async def _stream_bytes():
        while True:
            if await request.is_disconnected():
                break

            frame = request.app.state.camera_manager.snapshot_frame(node_id)
            if frame is None:
                await asyncio.sleep(0.15)
                continue

            if face_debug:
                _draw_face_debug_overlay(request, frame)

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
