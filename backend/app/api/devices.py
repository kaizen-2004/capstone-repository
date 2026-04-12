from __future__ import annotations

from fastapi import APIRouter, Request

from ..api.common import event_engine
from ..db import store
from ..schemas.api import (
    DeviceHeartbeatRequest,
    DeviceRegisterRequest,
    SensorEventRequest,
    SensorReadingRequest,
)

router = APIRouter(tags=["devices"])


def _request_ip(request: Request) -> str:
    client = request.client
    if client is None:
        return ""
    return str(client.host or "").strip()


def _maybe_auto_apply_camera_stream(request: Request, data: dict[str, object]) -> None:
    node_id = str(data.get("node_id") or data.get("node") or "").strip().lower()
    if node_id != "cam_door":
        return

    event_code = str(data.get("event") or data.get("event_code") or "").strip().upper()
    if event_code != "CAM_HEARTBEAT":
        return

    ip_address = str(data.get("ip") or "").strip()
    if not ip_address:
        return

    desired_stream_url = f"http://{ip_address}:81/stream"
    current_stream_url = (store.get_setting("CAMERA_DOOR_STREAM_URL") or "").strip()
    if current_stream_url == desired_stream_url:
        return

    applier = getattr(request.app.state, "apply_camera_stream_override", None)
    if not callable(applier):
        return

    try:
        applier("cam_door", desired_stream_url)
    except Exception:
        return


@router.post("/api/devices/register")
def register_device(payload: DeviceRegisterRequest, request: Request) -> dict:
    reported_ip = payload.ip.strip() or _request_ip(request)
    engine = event_engine(request)
    engine.register_device_defaults(
        node_id=payload.node_id.strip().lower(), ip_address=reported_ip
    )
    store.upsert_device(
        node_id=payload.node_id.strip().lower(),
        label=payload.label.strip() or payload.node_id.strip().lower(),
        device_type=payload.device_type.strip().lower(),
        location=payload.location.strip(),
        ip_address=reported_ip,
        note=payload.note.strip() or "registered",
        status="online",
    )
    return {"ok": True, "node_id": payload.node_id.strip().lower()}


@router.post("/api/devices/heartbeat")
def heartbeat(payload: DeviceHeartbeatRequest, request: Request) -> dict:
    node_id = payload.node_id.strip().lower()
    reported_ip = payload.ip.strip() or _request_ip(request)
    store.heartbeat_device(
        node_id=node_id,
        ip_address=reported_ip,
        note=payload.note.strip() or "heartbeat",
    )
    return {"ok": True, "node_id": node_id}


@router.post("/api/sensors/reading")
def sensor_reading(payload: SensorReadingRequest, request: Request) -> dict:
    node_id = payload.node_id.strip().lower()
    details = payload.details or {}
    details.update(
        {
            "reading_type": payload.reading_type,
            "value": payload.value,
            "unit": payload.unit or "",
        }
    )
    event_id = store.create_event(
        event_type="sensor",
        event_code=f"READING_{payload.reading_type.strip().upper()}",
        source_node=node_id,
        location=details.get("location", ""),
        severity="info",
        title=f"Sensor Reading: {payload.reading_type}",
        description=f"{payload.reading_type}={payload.value}{payload.unit or ''}",
        details=details,
    )
    store.heartbeat_device(
        node_id=node_id, ip_address=_request_ip(request), note="reading"
    )
    return {"ok": True, "event_id": event_id}


@router.post("/api/sensors/event")
def sensor_event(payload: SensorEventRequest, request: Request) -> dict:
    data = payload.model_dump()
    reported_ip = str(data.get("ip") or "").strip() or _request_ip(request)
    if reported_ip:
        data["ip"] = reported_ip
    _maybe_auto_apply_camera_stream(request, data)
    result = event_engine(request).process_sensor_event(data)
    return {"ok": True, **result}
