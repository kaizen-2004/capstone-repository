from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import cv2
import httpx
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
from ..db import store
from ..schemas.api import (
    CameraControlRequest,
    CameraOnboardingApplyRequest,
    RuntimeSettingUpdateRequest,
)

router = APIRouter(tags=["ui"])

PROVISIONABLE_NODE_IDS = ("cam_door", "door_force", "smoke_node1", "smoke_node2")
PROVISION_RESET_TIMEOUT_SECONDS = 4.0
FACE_DEBUG_CLASSIFY_INTERVAL_SECONDS = 0.35


def _face_debug_enabled_for_node(node_id: str, requested: bool) -> bool:
    _ = node_id
    return bool(requested)


def _known_node_ip_map() -> dict[str, str]:
    node_ip_map: dict[str, str] = {}
    for row in store.list_devices():
        node_id = str(row.get("node_id") or "").strip().lower()
        if node_id not in PROVISIONABLE_NODE_IDS:
            continue
        ip = str(row.get("ip_address") or "").strip()
        if ip:
            node_ip_map[node_id] = ip
    return node_ip_map


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


async def _request_node_reprovision_reset(
    client: httpx.AsyncClient, node_id: str, ip_address: str
) -> dict[str, str]:
    endpoint = f"http://{ip_address}/api/provision/reset"
    try:
        response = await client.post(
            endpoint, json={"clear_wifi": True, "clear_backend": True}
        )
    except httpx.TimeoutException:
        return {
            "node_id": node_id,
            "ip": ip_address,
            "status": "timeout",
            "detail": "Timed out while requesting node reset",
        }
    except Exception as exc:
        return {
            "node_id": node_id,
            "ip": ip_address,
            "status": "error",
            "detail": f"Failed to reach node reset endpoint: {exc}",
        }

    payload: dict[str, Any] = {}
    try:
        parsed = response.json()
        if isinstance(parsed, dict):
            payload = cast(dict[str, Any], parsed)
    except Exception:
        payload = {}

    if response.status_code >= 400:
        detail = (
            str(payload.get("detail") or payload.get("error") or "")
            or f"HTTP {response.status_code}"
        )
        if response.status_code == 404:
            detail = "Provisioning reset endpoint not found on node firmware"
        return {
            "node_id": node_id,
            "ip": ip_address,
            "status": "error",
            "detail": detail,
        }

    accepted = bool(payload.get("accepted", payload.get("ok", True)))
    detail = str(payload.get("detail") or "Provisioning reset accepted")
    return {
        "node_id": node_id,
        "ip": ip_address,
        "status": "accepted" if accepted else "error",
        "detail": detail,
    }


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
    telegram_snapshot_cooldown = store.get_setting(
        "TELEGRAM_SNAPSHOT_COOLDOWN_SECONDS"
    ) or str(settings.telegram_snapshot_cooldown_seconds)
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
            "key": "INTRUDER_EVENT_COOLDOWN_SECONDS",
            "value": str(settings.intruder_event_cooldown_seconds),
            "description": "Minimum seconds between repeated intruder trigger events per node",
        },
        {
            "key": "TELEGRAM_SNAPSHOT_COOLDOWN_SECONDS",
            "value": str(telegram_snapshot_cooldown),
            "description": "Minimum seconds between Telegram snapshot sends per source node and alert type",
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

    camera_status_by_node: dict[str, str] = {
        node_id: (
            "online"
            if str(row.get("status") or "").strip().lower() == "online"
            else "offline"
        )
        for node_id, row in camera_by_node.items()
    }

    sensor_statuses = []
    for row in devices:
        node_id = str(row.get("node_id") or "").strip().lower()
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


@router.post("/api/ui/settings/runtime")
def ui_runtime_setting_update(
    payload: RuntimeSettingUpdateRequest, request: Request
) -> dict:
    get_current_user(request)
    key = payload.key.strip().upper()
    value = payload.value.strip()

    if key != "TELEGRAM_SNAPSHOT_COOLDOWN_SECONDS":
        raise HTTPException(status_code=400, detail="unsupported runtime setting")

    try:
        cooldown_seconds = int(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="value must be an integer") from exc

    if cooldown_seconds < 10 or cooldown_seconds > 3600:
        raise HTTPException(
            status_code=400,
            detail="value must be between 10 and 3600 seconds",
        )

    store.upsert_setting(key, str(cooldown_seconds))
    return {
        "ok": True,
        "key": key,
        "value": str(cooldown_seconds),
        "description": "Minimum seconds between Telegram snapshot sends per source node and alert type",
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


@router.post("/api/ui/onboarding/camera/apply")
def ui_onboarding_camera_apply(
    payload: CameraOnboardingApplyRequest, request: Request
) -> dict:
    get_current_user(request)

    node_id = payload.node_id.strip().lower()
    stream_url = payload.stream_url.strip()
    fallback_stream_url = payload.fallback_stream_url.strip()

    target_url = stream_url or fallback_stream_url
    if not target_url:
        raise HTTPException(status_code=400, detail="stream_url is required")

    if not target_url.startswith(("http://", "https://", "rtsp://")):
        raise HTTPException(
            status_code=400,
            detail="stream_url must start with http://, https://, or rtsp://",
        )

    applier = getattr(request.app.state, "apply_camera_stream_override", None)
    if not callable(applier):
        raise HTTPException(
            status_code=503, detail="camera stream apply service unavailable"
        )

    try:
        result = applier(node_id, target_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    result_dict = cast(dict[str, Any], result if isinstance(result, dict) else {})

    camera_runtime = {}
    camera_manager = getattr(request.app.state, "camera_manager", None)
    if camera_manager is not None:
        try:
            statuses = camera_manager.live_status()
            for status_row in statuses:
                if not isinstance(status_row, dict):
                    continue
                status_dict = cast(dict[str, Any], status_row)
                if str(status_dict.get("node_id") or "").strip().lower() != node_id:
                    continue
                camera_runtime = {
                    "status": str(status_dict.get("status") or "offline"),
                    "last_error": str(status_dict.get("last_error") or ""),
                }
                break
        except Exception:
            camera_runtime = {}

    return {
        "ok": True,
        "applied": True,
        "node_id": str(result_dict.get("node_id") or node_id),
        "active_stream_url": str(result_dict.get("active_stream_url") or target_url),
        "camera_runtime": camera_runtime,
    }


@router.post("/api/ui/onboarding/reprovision-all")
async def ui_onboarding_reprovision_all(request: Request) -> dict:
    get_current_user(request)

    known_ips = _known_node_ip_map()
    results_by_node: dict[str, dict[str, str]] = {}
    pending_node_ids: list[str] = []

    for node_id in PROVISIONABLE_NODE_IDS:
        ip_address = known_ips.get(node_id, "")
        if not ip_address:
            results_by_node[node_id] = {
                "node_id": node_id,
                "ip": "",
                "status": "offline_no_ip",
                "detail": "Node has no known LAN IP yet",
            }
        else:
            pending_node_ids.append(node_id)

    if pending_node_ids:
        timeout = httpx.Timeout(PROVISION_RESET_TIMEOUT_SECONDS)
        async with httpx.AsyncClient(timeout=timeout) as client:
            task_results = await asyncio.gather(
                *[
                    _request_node_reprovision_reset(client, node_id, known_ips[node_id])
                    for node_id in pending_node_ids
                ]
            )
        for row in task_results:
            node_id = str(row.get("node_id") or "").strip().lower()
            if node_id:
                results_by_node[node_id] = row

    ordered_results = [
        results_by_node.get(
            node_id,
            {
                "node_id": node_id,
                "ip": "",
                "status": "error",
                "detail": "Missing result",
            },
        )
        for node_id in PROVISIONABLE_NODE_IDS
    ]

    accepted_count = sum(
        1 for row in ordered_results if row.get("status") == "accepted"
    )
    offline_count = sum(
        1 for row in ordered_results if row.get("status") == "offline_no_ip"
    )
    failed_count = len(ordered_results) - accepted_count - offline_count

    return {
        "ok": True,
        "requested_nodes": list(PROVISIONABLE_NODE_IDS),
        "results": ordered_results,
        "summary": {
            "accepted": accepted_count,
            "offline_no_ip": offline_count,
            "failed": failed_count,
        },
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
        normalized_node = node_id.strip().lower() or "unknown"
        cache_raw = getattr(request.app.state, "face_debug_cache", None)
        cache: dict[str, dict[str, Any]]
        if isinstance(cache_raw, dict):
            cache = cast(dict[str, dict[str, Any]], cache_raw)
        else:
            cache = {}
            request.app.state.face_debug_cache = cache

        now = time.monotonic()
        cached_entry = cache.get(normalized_node)
        verdict: dict[str, Any] | None = None
        if isinstance(cached_entry, dict):
            cached_ts = float(cached_entry.get("ts") or 0.0)
            cached_verdict = cached_entry.get("verdict")
            if (now - cached_ts) <= FACE_DEBUG_CLASSIFY_INTERVAL_SECONDS and isinstance(
                cached_verdict, dict
            ):
                verdict = cast(dict[str, Any], cached_verdict)

        if verdict is None:
            latest = request.app.state.face_service.classify_frame_with_bbox(frame)
            verdict = latest if isinstance(latest, dict) else {}
            cache[normalized_node] = {"ts": now, "verdict": verdict}

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
            if reason == "no_face_detected":
                reason = "No face detected"
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
