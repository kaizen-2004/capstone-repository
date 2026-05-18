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
        "title": "Smoke level is high",
    },
    "SMOKE_WARNING": {
        "type": "sensor",
        "severity": "warning",
        "title": "Smoke level warning",
    },
    "SMOKE_NORMAL": {
        "type": "sensor",
        "severity": "normal",
        "title": "Smoke level is back to normal",
    },
    "DOOR_FORCE": {
        "type": "intruder",
        "severity": "warning",
        "title": "Strong door impact detected",
    },
    "DOOR_OPEN": {
        "type": "sensor",
        "severity": "info",
        "title": "Door opened",
    },
    "DOOR_CLOSED": {
        "type": "sensor",
        "severity": "info",
        "title": "Door closed",
    },
    "ENTRY_MOTION": {
        "type": "intruder",
        "severity": "warning",
        "title": "Motion detected near the entry",
    },
    "PERSON_DETECTED": {
        "type": "intruder",
        "severity": "warning",
        "title": "Person detected near the entry",
    },
    "UNKNOWN": {
        "type": "intruder",
        "severity": "critical",
        "title": "Unknown person detected",
    },
    "AUTHORIZED": {
        "type": "authorized",
        "severity": "normal",
        "title": "Recognized person detected",
    },
    "FLAME_SIGNAL": {
        "type": "fire",
        "severity": "warning",
        "title": "Possible fire detected",
    },
    "NODE_OFFLINE": {
        "type": "system",
        "severity": "warning",
        "title": "Device disconnected",
    },
    "CAMERA_OFFLINE": {
        "type": "system",
        "severity": "warning",
        "title": "Camera disconnected",
    },
}

INTRUDER_TRIGGER_CODES = {"DOOR_FORCE", "ENTRY_MOTION", "PERSON_DETECTED", "UNKNOWN"}
DOOR_STATE_NOTIFICATION_CODES = {"DOOR_OPEN", "DOOR_CLOSED"}


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

        guest_mode_active = store.is_guest_mode_active()

        if event_code in INTRUDER_TRIGGER_CODES and not guest_mode_active:
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

        if event_code in {"SMOKE_HIGH", "SMOKE_WARNING"}:
            alert_id = self._handle_smoke_trigger(event_id, node_id, location, details)
            classification["classification"] = "fire"
        elif event_code in INTRUDER_TRIGGER_CODES:
            alert_id = self._handle_intruder_trigger(
                event_id, node_id, location, details
            )
            if alert_id is None and guest_mode_active:
                classification["event_code"] = "GUEST_ACTIVITY"
                classification["classification"] = "guest"
            else:
                classification["classification"] = "intruder"
        elif event_code == "NODE_OFFLINE":
            alert_id = self._create_alert(
                event_id,
                alert_type="NODE_OFFLINE",
                severity="warning",
                title="Device disconnected",
                description=f"{node_id} stopped reporting. Check power and network.",
                source_node=node_id,
                location=location,
                details=details,
            )
        elif event_code == "CAMERA_OFFLINE":
            alert_id = self._create_alert(
                event_id,
                alert_type="CAMERA_OFFLINE",
                severity="warning",
                title="Camera disconnected",
                description=f"{node_id} camera feed is unavailable. Please check it.",
                source_node=node_id,
                location=location,
                details=details,
            )

        classification["alert_id"] = alert_id
        if alert_id is None and event_code in DOOR_STATE_NOTIFICATION_CODES:
            self._dispatch_normal_event_notification(
                event_id=event_id,
                event_code=event_code,
                source_node=node_id,
                location=location,
                severity=meta["severity"],
                title=meta["title"],
                description=description,
                details=details,
            )
        return classification

    def _dispatch_normal_event_notification(
        self,
        *,
        event_id: int,
        event_code: str,
        source_node: str,
        location: str,
        severity: str,
        title: str,
        description: str,
        details: dict[str, Any],
    ) -> None:
        if not self.notification_dispatcher:
            return
        try:
            self.notification_dispatcher.dispatch_event(
                {
                    "id": event_id,
                    "event_code": event_code,
                    "source_node": source_node,
                    "location": location,
                    "severity": severity,
                    "title": title,
                    "description": description,
                    "details_json": json.dumps(details or {}, separators=(",", ":")),
                }
            )
        except Exception as exc:
            store.log(
                "ERROR", f"notification dispatch failed for event {event_id}: {exc}"
            )

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
        preferred_camera = "cam_indoor"
        normalized_location = (location or "").strip().lower()
        if node_id in {"smoke_node2", "mq2_door"} or "door" in normalized_location:
            preferred_camera = "cam_door"

        frame = self.camera_manager.snapshot_frame(preferred_camera)
        camera_node_used = preferred_camera
        if frame is None and preferred_camera != "cam_indoor":
            frame = self.camera_manager.snapshot_frame("cam_indoor")
            camera_node_used = "cam_indoor"

        snapshot_path = ""

        if frame is not None:
            try:
                snapshot_path = self.camera_manager.save_snapshot(
                    camera_node_used, frame, "smoke_warning"
                )
            except Exception:
                snapshot_path = ""

        return self._create_alert(
            event_id,
            alert_type="SMOKE_WARNING",
            severity="warning",
            title="Smoke warning",
            description="Smoke level is high. Please check the area now.",
            source_node=node_id,
            location=location or ROOM_LIVING,
            snapshot_path=snapshot_path,
            details={
                **details,
                "detection_mode": "smoke_sensor_only",
                "camera_node": camera_node_used,
            },
        )

    def _pick_intruder_face_result(
        self, frame: Any
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        face_results = self.face_service.classify_faces_with_bbox(frame, max_faces=5)
        if not face_results:
            return self.face_service.classify_frame_with_bbox(frame), []

        unknown_faces = [
            verdict
            for verdict in face_results
            if str(verdict.get("face_status") or "").upper() == "UNKNOWN_FACE"
            or (
                str(verdict.get("result") or "").lower() == "unknown"
                and bool(verdict.get("face_present"))
                and str(verdict.get("face_status") or "").upper()
                not in {"FACE_UNCLEAR", "NO_FACE"}
            )
        ]
        unclear_faces = [
            verdict
            for verdict in face_results
            if str(verdict.get("face_status") or "").upper() == "FACE_UNCLEAR"
            and bool(verdict.get("face_present"))
        ]
        authorized_faces = [
            verdict
            for verdict in face_results
            if str(verdict.get("result") or "").lower() == "authorized"
        ]

        if unknown_faces:
            return unknown_faces[0], face_results
        if unclear_faces:
            return unclear_faces[0], face_results
        if authorized_faces:
            return authorized_faces[0], face_results
        return face_results[0], face_results

    @staticmethod
    def _intruder_decision_state(face_result: dict[str, Any]) -> str:
        if str(face_result.get("result") or "").lower() == "authorized":
            return "authorized"

        face_status = str(face_result.get("face_status") or "").upper()
        if face_status == "FACE_UNCLEAR":
            return "face_unclear"
        if face_status == "NO_FACE" or not bool(face_result.get("face_present")):
            return "no_face"
        return "unknown_face"

    def _classify_intruder_frame(self, frame: Any) -> dict[str, Any]:
        face_result, face_results = self._pick_intruder_face_result(frame)
        decision_state = self._intruder_decision_state(face_result)
        return {
            "decision_state": decision_state,
            "face": face_result,
            "faces": face_results,
            "frame": frame,
        }

    @staticmethod
    def _intruder_decision_summary(
        samples: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        summary = []
        for index, sample in enumerate(samples, start=1):
            face = sample.get("face") if isinstance(sample.get("face"), dict) else {}
            summary.append(
                {
                    "frame": index,
                    "decision_state": str(sample.get("decision_state") or ""),
                    "face_status": str(face.get("face_status") or ""),
                    "result": str(face.get("result") or ""),
                    "confidence": face.get("confidence", 0.0),
                }
            )
        return summary

    def _select_intruder_consensus(
        self, samples: list[dict[str, Any]]
    ) -> dict[str, Any]:
        if not samples:
            face_result = {
                "result": "unknown",
                "classification": "NO-FACE",
                "confidence": 0.0,
                "face_present": False,
                "reason": "no_frame",
                "face_status": "NO_FACE",
            }
            return {
                "decision_state": "no_face",
                "face": face_result,
                "faces": [],
                "frame": None,
                "decision_samples": [],
                "decision_votes": {"no_face": 0},
                "decision_consensus": "no_frame",
            }

        votes: dict[str, int] = {}
        for sample in samples:
            state = str(sample.get("decision_state") or "no_face")
            votes[state] = votes.get(state, 0) + 1

        if votes.get("authorized", 0) > 0:
            selected_state = "authorized"
            consensus = "authorized_seen"
        elif votes.get("unknown_face", 0) >= 2:
            selected_state = "unknown_face"
            consensus = "majority"
        elif votes.get("face_unclear", 0) >= 2:
            selected_state = "face_unclear"
            consensus = "majority"
        elif votes.get("no_face", 0) >= 2:
            selected_state = "no_face"
            consensus = "majority"
        elif votes.get("unknown_face", 0) > 0 or votes.get("face_unclear", 0) > 0:
            selected_state = "face_unclear"
            consensus = "mixed_unclear_review"
        else:
            selected_state = "no_face"
            consensus = "fallback"

        selected_sample = next(
            (
                sample
                for sample in samples
                if str(sample.get("decision_state") or "") == selected_state
            ),
            None,
        )
        if selected_sample is None and selected_state == "face_unclear":
            selected_sample = next(
                (
                    sample
                    for sample in samples
                    if str(sample.get("decision_state") or "")
                    in {"unknown_face", "face_unclear"}
                ),
                samples[0],
            )
        if selected_sample is None:
            selected_sample = samples[0]
        return {
            **selected_sample,
            "decision_state": selected_state,
            "decision_samples": self._intruder_decision_summary(samples),
            "decision_votes": votes,
            "decision_consensus": consensus,
        }

    def _handle_intruder_trigger(
        self, event_id: int, node_id: str, location: str, details: dict[str, Any]
    ) -> int | None:
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

        decision_samples: list[dict[str, Any]] = []
        if frame is not None:
            decision_samples.append(self._classify_intruder_frame(frame))
            while (
                len(decision_samples) < 3
                and not any(
                    str(sample.get("decision_state") or "") == "authorized"
                    for sample in decision_samples
                )
            ):
                time.sleep(0.15)
                next_frame = self.camera_manager.snapshot_frame(primary_node)
                if next_frame is None:
                    break
                decision_samples.append(self._classify_intruder_frame(next_frame))

        decision = self._select_intruder_consensus(decision_samples)
        decision_state = str(decision.get("decision_state") or "no_face")
        face_result = (
            decision.get("face") if isinstance(decision.get("face"), dict) else {}
        )
        face_results = (
            decision.get("faces") if isinstance(decision.get("faces"), list) else []
        )
        snapshot_frame = decision.get("frame")
        snapshot_path = ""
        if snapshot_frame is not None:
            prefix = f"intruder_{decision_state}"
            try:
                snapshot_path = self.camera_manager.save_snapshot(
                    primary_node, snapshot_frame, prefix
                )
            except Exception:
                snapshot_path = ""

        decision_details = {
            **details,
            "decision_state": decision_state,
            "decision_votes": decision.get("decision_votes", {}),
            "decision_consensus": decision.get("decision_consensus", ""),
            "decision_samples": decision.get("decision_samples", []),
            "consensus_frames": len(decision_samples),
            "consensus_required": 2,
            "face": face_result,
            "faces": face_results,
        }

        if decision_state == "authorized":
            store.create_event(
                event_type="authorized",
                event_code="AUTHORIZED",
                source_node=node_id,
                location=location or ROOM_DOOR,
                severity="normal",
                title="Recognized person detected",
                description="A recognized person was seen near the entry.",
                details=decision_details,
            )
            return self._create_alert(
                event_id,
                alert_type="AUTHORIZED_ENTRY",
                severity="info",
                title="Recognized entry",
                description="A recognized person entered. No action needed.",
                source_node=node_id,
                location=location or ROOM_DOOR,
                snapshot_path=snapshot_path,
                details=decision_details,
                requires_ack=False,
                dispatch_notification=True,
            )

        if store.is_guest_mode_active():
            return self._mark_guest_activity_event(
                event_id=event_id,
                node_id=node_id,
                location=location or ROOM_DOOR,
                snapshot_path=snapshot_path,
                details=decision_details,
            )

        if decision_state == "face_unclear":
            return self._create_alert(
                event_id,
                alert_type="INTRUDER",
                severity="warning",
                title="Entry face needs review",
                description="Door activity was detected, but the captured face was unclear.",
                source_node=node_id,
                location=location or ROOM_DOOR,
                snapshot_path=snapshot_path,
                details=decision_details,
                requires_ack=True,
            )

        if decision_state == "no_face":
            return self._create_alert(
                event_id,
                alert_type="INTRUDER",
                severity="warning",
                title="Entry activity needs review",
                description="Door activity was detected, but no face was captured.",
                source_node=node_id,
                location=location or ROOM_DOOR,
                snapshot_path=snapshot_path,
                details=decision_details,
                requires_ack=True,
            )

        return self._create_alert(
            event_id,
            alert_type="INTRUDER",
            severity="critical",
            title="Unknown person detected at the entry",
            description="An unknown person was seen near the entry. Please check now.",
            source_node=node_id,
            location=location or ROOM_DOOR,
            snapshot_path=snapshot_path,
            details=decision_details,
            requires_ack=True,
        )

    def _mark_guest_activity_event(
        self,
        *,
        event_id: int,
        node_id: str,
        location: str,
        snapshot_path: str,
        details: dict[str, Any],
    ) -> None:
        guest_details = {
            **details,
            "guest_mode": True,
            "guest_mode_until_ts": store.guest_mode_status()["until_ts"],
            "snapshot_path": snapshot_path,
        }
        store.update_event_classification(
            event_id,
            event_type="system",
            event_code="GUEST_ACTIVITY",
            severity="info",
            title="Guest activity observed",
            description="Entry activity was seen while Guest Mode was active. No intruder alert was created.",
            details=guest_details,
        )
        store.log(
            "INFO",
            f"guest mode suppressed intruder alert node={node_id} event_id={event_id}",
        )
        return None

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
