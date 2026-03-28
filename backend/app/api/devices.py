from __future__ import annotations

from fastapi import APIRouter, Request

from ..api.common import event_engine
from ..db import store
from ..schemas.api import DeviceHeartbeatRequest, DeviceRegisterRequest, SensorEventRequest, SensorReadingRequest

router = APIRouter(tags=["devices"])


@router.post("/api/devices/register")
def register_device(payload: DeviceRegisterRequest, request: Request) -> dict:
    engine = event_engine(request)
    engine.register_device_defaults(node_id=payload.node_id.strip().lower(), ip_address=payload.ip)
    store.upsert_device(
        node_id=payload.node_id.strip().lower(),
        label=payload.label.strip() or payload.node_id.strip().lower(),
        device_type=payload.device_type.strip().lower(),
        location=payload.location.strip(),
        ip_address=payload.ip.strip(),
        note=payload.note.strip() or "registered",
        status="online",
    )
    return {"ok": True, "node_id": payload.node_id.strip().lower()}


@router.post("/api/devices/heartbeat")
def heartbeat(payload: DeviceHeartbeatRequest) -> dict:
    node_id = payload.node_id.strip().lower()
    store.heartbeat_device(node_id=node_id, ip_address=payload.ip.strip(), note=payload.note.strip() or "heartbeat")
    return {"ok": True, "node_id": node_id}


@router.post("/api/sensors/reading")
def sensor_reading(payload: SensorReadingRequest) -> dict:
    node_id = payload.node_id.strip().lower()
    details = payload.details or {}
    details.update({"reading_type": payload.reading_type, "value": payload.value, "unit": payload.unit or ""})
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
    store.heartbeat_device(node_id=node_id, note="reading")
    return {"ok": True, "event_id": event_id}


@router.post("/api/sensors/event")
def sensor_event(payload: SensorEventRequest, request: Request) -> dict:
    data = payload.model_dump()
    result = event_engine(request).process_sensor_event(data)
    return {"ok": True, **result}
