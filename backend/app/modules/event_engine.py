from __future__ import annotations

import json
import threading
import time
from typing import Any

from ..db import store
from ..services.camera_http_control import CameraHttpController
from ..services.camera_manager import CameraManager
from ..services.notification_dispatcher import NotificationDispatcher
from .face_service import FaceService
from .fire_service import FireService

ROOM_LIVING = "Living Room"
ROOM_DOOR = "Door Entrance Area"

NODE_DEFAULTS: dict[str, dict[str, str]] = {
    "smoke_node1": {
        "location": ROOM_LIVING,
        "label": "Smoke Sensor Node 1",
        "type": "smoke",
    },
    "smoke_node2": {
        "location": ROOM_DOOR,
        "label": "Smoke Sensor Node 2",
        "type": "smoke",
    },
    "door_force": {"location": ROOM_DOOR, "label": "Door Force Node", "type": "force"},
    "cam_indoor": {
        "location": ROOM_LIVING,
        "label": "Indoor RTSP Camera",
        "type": "camera",
    },
    "cam_door": {"location": ROOM_DOOR, "label": "Door RTSP Camera", "type": "camera"},
}

EVENT_META: dict[str, dict[str, str]] = {
    "NODE_HEARTBEAT": {"type": "sensor", "severity": "info", "title": "Node Heartbeat"},
    "SMOKE_HIGH": {
        "type": "sensor",
        "severity": "warning",
        "title": "Smoke Threshold Exceeded",
    },
    "SMOKE_NORMAL": {
        "type": "sensor",
        "severity": "normal",
        "title": "Smoke Back To Normal",
    },
    "DOOR_FORCE": {
        "type": "intruder",
        "severity": "warning",
        "title": "Door Force Anomaly",
    },
    "ENTRY_MOTION": {
        "type": "intruder",
        "severity": "warning",
        "title": "Entry Motion Trigger",
    },
    "PERSON_DETECTED": {
        "type": "intruder",
        "severity": "warning",
        "title": "Person Near Entry",
    },
    "UNKNOWN": {
        "type": "intruder",
        "severity": "critical",
        "title": "Non-Authorized Person Detected",
    },
    "AUTHORIZED": {
        "type": "authorized",
        "severity": "normal",
        "title": "Authorized Person Detected",
    },
    "FLAME_SIGNAL": {
        "type": "fire",
        "severity": "warning",
        "title": "Possible Flame Signal",
    },
    "NODE_OFFLINE": {"type": "system", "severity": "warning", "title": "Node Offline"},
    "CAMERA_OFFLINE": {
        "type": "system",
        "severity": "warning",
        "title": "Camera Offline",
    },
}

INTRUDER_TRIGGER_CODES = {"DOOR_FORCE", "ENTRY_MOTION", "PERSON_DETECTED", "UNKNOWN"}


class EventEngine:
    def __init__(
        self,
        camera_manager: CameraManager,
        camera_http_controller: CameraHttpController | None,
        face_service: FaceService,
        fire_service: FireService,
        notification_dispatcher: NotificationDispatcher | None = None,
        intruder_event_cooldown_seconds: int = 20,
    ) -> None:
        self.camera_manager = camera_manager
        self.camera_http_controller = camera_http_controller
        self.face_service = face_service
        self.fire_service = fire_service
        self.notification_dispatcher = notification_dispatcher
        self.intruder_event_cooldown_seconds = max(
            0, int(intruder_event_cooldown_seconds)
        )
        self._intruder_alert_lock = threading.Lock()
        self._intruder_alert_last_ts_by_node: dict[str, float] = {}

    def _node_meta(self, node_id: str) -> dict[str, str]:
        return NODE_DEFAULTS.get(
            node_id, {"location": "", "label": node_id, "type": "sensor"}
        )

    def _event_meta(self, code: str) -> dict[str, str]:
        return EVENT_META.get(
            code, {"type": "system", "severity": "info", "title": code}
        )

    def register_device_defaults(self, node_id: str, ip_address: str = "") -> None:
        meta = self._node_meta(node_id)
        store.upsert_device(
            node_id=node_id,
            label=meta["label"],
            device_type=meta["type"],
            location=meta["location"],
            ip_address=ip_address,
            note="registered",
            status="online",
        )

    def process_sensor_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        node_id = (
            str(payload.get("node_id") or payload.get("node") or "unknown")
            .strip()
            .lower()
        )
        event_code = (
            str(payload.get("event") or payload.get("event_code") or "NODE_HEARTBEAT")
            .strip()
            .upper()
        )
        location = str(
            payload.get("location") or self._node_meta(node_id).get("location") or ""
        )
        details = payload.get("details")
        if isinstance(details, str):
            try:
                details = json.loads(details)
            except Exception:
                details = {"raw": details}
        if not isinstance(details, dict):
            details = {}

        self.register_device_defaults(
            node_id=node_id, ip_address=str(payload.get("ip") or "")
        )
        store.heartbeat_device(
            node_id=node_id, ip_address=str(payload.get("ip") or ""), note=event_code
        )

        meta = self._event_meta(event_code)
        description = str(
            payload.get("description") or details.get("description") or meta["title"]
        )

        if event_code in INTRUDER_TRIGGER_CODES:
            suppressed, remaining_seconds = self._should_suppress_intruder_event(
                node_id
            )
            if suppressed:
                return {
                    "event_id": None,
                    "event_code": event_code,
                    "classification": "intruder",
                    "alert_id": None,
                    "suppressed": True,
                    "suppression_reason": "intruder_cooldown",
                    "cooldown_seconds": self.intruder_event_cooldown_seconds,
                    "cooldown_remaining_seconds": round(remaining_seconds, 1),
                }

        event_id = store.create_event(
            event_type=meta["type"],
            event_code=event_code,
            source_node=node_id,
            location=location,
            severity=meta["severity"],
            title=meta["title"],
            description=description,
            details=details,
        )

        alert_id = None
        classification = {
            "event_id": event_id,
            "event_code": event_code,
            "classification": meta["type"],
            "alert_id": None,
            "suppressed": False,
        }

        if event_code == "SMOKE_HIGH":
            alert_id = self._handle_smoke_trigger(event_id, node_id, location, details)
            classification["classification"] = "fire"
        elif event_code in INTRUDER_TRIGGER_CODES:
            alert_id = self._handle_intruder_trigger(
                event_id, node_id, location, details
            )
            classification["classification"] = "intruder"
        elif event_code == "NODE_OFFLINE":
            alert_id = self._create_alert(
                event_id,
                alert_type="NODE_OFFLINE",
                severity="warning",
                title="Sensor Node Offline",
                description=f"{node_id} heartbeat timeout exceeded",
                source_node=node_id,
                location=location,
                details=details,
            )
        elif event_code == "CAMERA_OFFLINE":
            alert_id = self._create_alert(
                event_id,
                alert_type="CAMERA_OFFLINE",
                severity="warning",
                title="Camera Disconnected",
                description=f"{node_id} stream unavailable",
                source_node=node_id,
                location=location,
                details=details,
            )

        classification["alert_id"] = alert_id
        return classification

    def _should_suppress_intruder_event(self, node_id: str) -> tuple[bool, float]:
        cooldown_seconds = float(self.intruder_event_cooldown_seconds)
        if cooldown_seconds <= 0.0:
            return False, 0.0

        now_ts = time.time()
        with self._intruder_alert_lock:
            last_ts = self._intruder_alert_last_ts_by_node.get(node_id)
            if last_ts is not None:
                elapsed = now_ts - last_ts
                if elapsed < cooldown_seconds:
                    return True, max(0.0, cooldown_seconds - elapsed)
            self._intruder_alert_last_ts_by_node[node_id] = now_ts
        return False, 0.0

    def _handle_smoke_trigger(
        self, event_id: int, node_id: str, location: str, details: dict[str, Any]
    ) -> int:
        frame = self.camera_manager.snapshot_frame("cam_indoor")
        flame_result = {"flame": False, "confidence": 0.0}
        snapshot_path = ""

        if frame is not None:
            flame_result = self.fire_service.detect_flame(frame)
            prefix = "fire_confirmed" if flame_result["flame"] else "fire_check"
            snapshot_path = self.camera_manager.save_snapshot(
                "cam_indoor", frame, prefix
            )

        if flame_result["flame"]:
            return self._create_alert(
                event_id,
                alert_type="FIRE",
                severity="critical",
                title="Fire Alert",
                description="Smoke anomaly with indoor visual flame confirmation",
                source_node=node_id,
                location=location or ROOM_LIVING,
                snapshot_path=snapshot_path,
                details={"flame_confirmation": flame_result, **details},
            )

        return self._create_alert(
            event_id,
            alert_type="SMOKE_WARNING",
            severity="warning",
            title="Smoke Alert",
            description="Smoke anomaly detected; no visual flame confirmation",
            source_node=node_id,
            location=location or ROOM_LIVING,
            snapshot_path=snapshot_path,
            details={"flame_confirmation": flame_result, **details},
        )

    def _handle_intruder_trigger(
        self, event_id: int, node_id: str, location: str, details: dict[str, Any]
    ) -> int:
        primary_node = "cam_door"
        frame = None
        capture_detail = ""

        if node_id == "door_force" and self.camera_http_controller is not None:
            frame, capture_detail = self.camera_http_controller.capture_frame(
                primary_node, flash=True, timeout_seconds=4.0
            )
            if frame is not None:
                details = {
                    **details,
                    "triggered_snapshot": True,
                    "trigger_capture": capture_detail,
                }
            elif capture_detail:
                details = {
                    **details,
                    "triggered_snapshot": False,
                    "trigger_capture_error": capture_detail,
                }

        if frame is None:
            frame = self.camera_manager.snapshot_frame(primary_node)
        if frame is None:
            primary_node = "cam_indoor"
            frame = self.camera_manager.snapshot_frame("cam_indoor")

        face_result = {
            "result": "unknown",
            "classification": "NO-FACE",
            "confidence": 0.0,
            "face_present": False,
            "reason": "no_frame",
        }
        snapshot_path = ""
        if frame is not None:
            face_result = self.face_service.classify_frame(frame)
            prefix = (
                "authorized" if face_result.get("result") == "authorized" else "unknown"
            )
            snapshot_path = self.camera_manager.save_snapshot(
                primary_node, frame, f"intruder_{prefix}"
            )

        if face_result.get("result") == "authorized":
            store.create_event(
                event_type="authorized",
                event_code="AUTHORIZED",
                source_node=node_id,
                location=location or ROOM_DOOR,
                severity="normal",
                title="Authorized Person Detected",
                description="Face classified as authorized",
                details={"face": face_result, **details},
            )
            return self._create_alert(
                event_id,
                alert_type="AUTHORIZED_ENTRY",
                severity="info",
                title="Authorized Entry",
                description="Authorized face classification",
                source_node=node_id,
                location=location or ROOM_DOOR,
                snapshot_path=snapshot_path,
                details={"face": face_result, **details},
                requires_ack=False,
                dispatch_notification=True,
            )

        if not bool(face_result.get("face_present")):
            return self._create_alert(
                event_id,
                alert_type="INTRUDER",
                severity="critical",
                title="Entry Anomaly Alert",
                description="Entry anomaly detected; no face confirmation available",
                source_node=node_id,
                location=location or ROOM_DOOR,
                snapshot_path=snapshot_path,
                details={"face": face_result, **details},
                requires_ack=True,
            )

        return self._create_alert(
            event_id,
            alert_type="INTRUDER",
            severity="critical",
            title="Non-Authorized Person / Tamper Alert",
            description="Entry anomaly with non-authorized face classification",
            source_node=node_id,
            location=location or ROOM_DOOR,
            snapshot_path=snapshot_path,
            details={"face": face_result, **details},
            requires_ack=True,
        )

    def _create_alert(
        self,
        event_id: int,
        *,
        alert_type: str,
        severity: str,
        title: str,
        description: str,
        source_node: str,
        location: str,
        details: dict[str, Any],
        snapshot_path: str = "",
        requires_ack: bool = True,
        dispatch_notification: bool | None = None,
    ) -> int:
        alert_id = store.create_alert(
            alert_type=alert_type,
            severity=severity,
            status="ACTIVE" if requires_ack else "RESOLVED",
            requires_ack=requires_ack,
            title=title,
            description=description,
            source_node=source_node,
            location=location,
            event_id=event_id,
            snapshot_path=snapshot_path,
            details=details,
        )
        should_dispatch = (
            requires_ack
            if dispatch_notification is None
            else bool(dispatch_notification)
        )
        if self.notification_dispatcher and should_dispatch:
            try:
                self.notification_dispatcher.dispatch_alert_by_id(alert_id)
            except Exception as exc:
                store.log(
                    "ERROR", f"notification dispatch failed for alert {alert_id}: {exc}"
                )
        return alert_id


def infer_location_from_node(node_id: str) -> str:
    meta = NODE_DEFAULTS.get(node_id)
    return meta["location"] if meta else ""
