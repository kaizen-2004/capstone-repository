from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..db import store
from ..modules.event_engine import infer_location_from_node
from ..modules.face_service import FaceService
from ..modules.fire_service import FireService
from .camera_manager import CameraManager
from .notification_dispatcher import NotificationDispatcher


class Supervisor:
    def __init__(
        self,
        node_offline_seconds: int,
        camera_offline_seconds: int,
        event_retention_days: int,
        log_retention_days: int,
        snapshot_root: Path,
        regular_snapshot_retention_days: int,
        critical_snapshot_retention_days: int,
        notification_dispatcher: NotificationDispatcher | None = None,
        remote_access_poll_seconds: int = 60,
        camera_manager: CameraManager | None = None,
        face_service: FaceService | None = None,
        fire_service: FireService | None = None,
        fire_continuous_detection_enabled: bool = True,
        fire_scan_seconds: int = 2,
        fire_alert_cooldown_seconds: int = 45,
        authorized_presence_logging_enabled: bool = False,
        authorized_presence_scan_seconds: int = 2,
        authorized_presence_cooldown_seconds: int = 20,
        unknown_presence_logging_enabled: bool = False,
        unknown_presence_cooldown_seconds: int = 20,
    ) -> None:
        self.node_offline_seconds = node_offline_seconds
        self.camera_offline_seconds = max(10, int(camera_offline_seconds))
        self.event_retention_days = event_retention_days
        self.log_retention_days = log_retention_days
        self.snapshot_root = snapshot_root
        self.regular_snapshot_retention_days = regular_snapshot_retention_days
        self.critical_snapshot_retention_days = critical_snapshot_retention_days
        self.notification_dispatcher = notification_dispatcher
        self.remote_access_poll_seconds = max(20, int(remote_access_poll_seconds))
        self.camera_manager = camera_manager
        self.face_service = face_service
        self.fire_service = fire_service
        face_scan_dependencies_ready = (
            camera_manager is not None and face_service is not None
        )
        fire_scan_dependencies_ready = (
            camera_manager is not None and fire_service is not None
        )
        self.fire_continuous_detection_enabled = bool(
            fire_continuous_detection_enabled and fire_scan_dependencies_ready
        )
        self.fire_scan_seconds = max(1, int(fire_scan_seconds))
        self.fire_alert_cooldown_seconds = max(10, int(fire_alert_cooldown_seconds))
        self._fire_visible_by_node: dict[str, bool] = {}
        self._fire_miss_by_node: dict[str, int] = {}
        self._fire_last_logged_at_by_node: dict[str, float] = {}
        self.authorized_presence_logging_enabled = bool(
            authorized_presence_logging_enabled and face_scan_dependencies_ready
        )
        self.unknown_presence_logging_enabled = bool(
            unknown_presence_logging_enabled and face_scan_dependencies_ready
        )
        self.face_presence_logging_enabled = bool(
            self.authorized_presence_logging_enabled
            or self.unknown_presence_logging_enabled
        )
        self.authorized_presence_scan_seconds = max(
            1, int(authorized_presence_scan_seconds)
        )
        self.authorized_presence_cooldown_seconds = max(
            5, int(authorized_presence_cooldown_seconds)
        )
        self.unknown_presence_cooldown_seconds = max(
            5, int(unknown_presence_cooldown_seconds)
        )
        self._presence_visible_by_node: dict[str, bool] = {}
        self._presence_name_by_node: dict[str, str] = {}
        self._presence_miss_by_node: dict[str, int] = {}
        self._presence_last_logged_at_by_node: dict[str, float] = {}
        self._unknown_visible_by_node: dict[str, bool] = {}
        self._unknown_miss_by_node: dict[str, int] = {}
        self._unknown_last_logged_at_by_node: dict[str, float] = {}

        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @staticmethod
    def _parse_bool(raw: str | None, default: bool) -> bool:
        if raw is None:
            return default
        return str(raw).strip().lower() in {"1", "true", "yes", "on", "enabled"}

    def _presence_logging_enabled_runtime(self) -> bool:
        if self.camera_manager is None or self.face_service is None:
            return False

        auth_raw = store.get_setting("AUTHORIZED_PRESENCE_LOGGING_ENABLED")
        unknown_raw = store.get_setting("UNKNOWN_PRESENCE_LOGGING_ENABLED")

        authorized_enabled = self._parse_bool(
            auth_raw, self.authorized_presence_logging_enabled
        )
        unknown_enabled = self._parse_bool(
            unknown_raw, self.unknown_presence_logging_enabled
        )

        self.authorized_presence_logging_enabled = authorized_enabled
        self.unknown_presence_logging_enabled = unknown_enabled
        self.face_presence_logging_enabled = bool(
            authorized_enabled or unknown_enabled
        )
        return self.face_presence_logging_enabled

    def _fire_monitoring_enabled_runtime(self) -> bool:
        if self.camera_manager is None or self.fire_service is None:
            return False
        return self.fire_continuous_detection_enabled

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="backend-supervisor", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.5)

    def _run(self) -> None:
        next_retention_run = 0.0
        next_remote_access_poll = 0.0
        next_presence_scan = 0.0
        next_fire_scan = 0.0
        while not self._stop.is_set():
            try:
                self._check_nodes()
                store.prune_expired_sessions()

                now = time.time()
                if now >= next_retention_run:
                    self._run_retention()
                    next_retention_run = now + 3600

                if self.notification_dispatcher and now >= next_remote_access_poll:
                    self.notification_dispatcher.poll_access_link_changes()
                    next_remote_access_poll = now + float(
                        self.remote_access_poll_seconds
                    )

                presence_logging_enabled = self._presence_logging_enabled_runtime()

                if presence_logging_enabled and now >= next_presence_scan:
                    self._scan_face_presence(now)
                    next_presence_scan = now + float(
                        self.authorized_presence_scan_seconds
                    )

                fire_monitoring_enabled = self._fire_monitoring_enabled_runtime()
                if fire_monitoring_enabled and now >= next_fire_scan:
                    self._scan_fire_presence(now)
                    next_fire_scan = now + float(self.fire_scan_seconds)
            except Exception as exc:
                store.log("ERROR", f"supervisor loop failed: {exc}")

            self._stop.wait(
                1.0
                if (self.face_presence_logging_enabled or self.fire_continuous_detection_enabled)
                else 10.0
            )

    def _scan_fire_presence(self, now_ts: float) -> None:
        if (
            self.camera_manager is None
            or self.fire_service is None
            or not self.fire_continuous_detection_enabled
        ):
            return

        miss_reset_threshold = 2

        for camera in self.camera_manager.live_status():
            node_id = str(camera.get("node_id") or "")
            if not node_id:
                continue

            camera_status = str(camera.get("status") or "").strip().lower()
            if camera_status != "online":
                misses = self._fire_miss_by_node.get(node_id, 0) + 1
                self._fire_miss_by_node[node_id] = misses
                if misses >= miss_reset_threshold:
                    self._fire_visible_by_node[node_id] = False
                continue

            try:
                frame = self.camera_manager.snapshot_frame(node_id)
                if frame is None:
                    misses = self._fire_miss_by_node.get(node_id, 0) + 1
                    self._fire_miss_by_node[node_id] = misses
                    if misses >= miss_reset_threshold:
                        self._fire_visible_by_node[node_id] = False
                    continue

                fire_result = self.fire_service.detect_flame(frame)
                flame_detected = bool(fire_result.get("flame"))

                if flame_detected:
                    self._fire_miss_by_node[node_id] = 0
                    was_visible = self._fire_visible_by_node.get(node_id, False)
                    last_logged_at = self._fire_last_logged_at_by_node.get(node_id, 0.0)

                    cooldown_ready = (now_ts - last_logged_at) >= float(
                        self.fire_alert_cooldown_seconds
                    )
                    entered_view = not was_visible

                    if entered_view and cooldown_ready:
                        try:
                            snapshot_path = self.camera_manager.save_snapshot(
                                node_id,
                                frame,
                                "fire_confirmed_continuous",
                            )
                        except Exception:
                            snapshot_path = ""

                        location = infer_location_from_node(node_id)
                        details = {
                            "detection_mode": "continuous_fire_scan",
                            "presence_transition": "entered_fov",
                            "snapshot_path": snapshot_path,
                            "flame_confirmation": {
                                **fire_result,
                                "camera_node": node_id,
                            },
                        }
                        event_id = store.create_event(
                            event_type="fire",
                            event_code="FLAME_SIGNAL",
                            source_node=node_id,
                            location=location,
                            severity="warning",
                            title="Possible Flame Signal",
                            description="Continuous camera flame detection signal",
                            details=details,
                        )
                        alert_id = store.create_alert(
                            alert_type="FIRE",
                            severity="critical",
                            status="ACTIVE",
                            requires_ack=True,
                            title="Fire Alert",
                            description="Continuous camera frame flame detection",
                            source_node=node_id,
                            location=location,
                            event_id=event_id,
                            snapshot_path=snapshot_path,
                            details=details,
                        )
                        store.log(
                            "INFO",
                            f"continuous fire alert node={node_id} alert_id={alert_id} snapshot={snapshot_path or 'none'}",
                        )
                        if self.notification_dispatcher:
                            try:
                                self.notification_dispatcher.dispatch_alert_by_id(alert_id)
                            except Exception as exc:
                                store.log(
                                    "ERROR",
                                    f"notification dispatch failed for alert {alert_id}: {exc}",
                                )
                        self._fire_last_logged_at_by_node[node_id] = now_ts

                    self._fire_visible_by_node[node_id] = True
                    continue

                misses = self._fire_miss_by_node.get(node_id, 0) + 1
                self._fire_miss_by_node[node_id] = misses
                if misses >= miss_reset_threshold:
                    self._fire_visible_by_node[node_id] = False
            except Exception as exc:
                store.log("ERROR", f"fire presence scan failed for {node_id}: {exc}")

    def _scan_face_presence(self, now_ts: float) -> None:
        if self.camera_manager is None or self.face_service is None:
            return

        miss_reset_threshold = 1

        for camera in self.camera_manager.live_status():
            node_id = str(camera.get("node_id") or "")
            if not node_id:
                continue

            try:
                frame = self.camera_manager.snapshot_frame(node_id)
                if frame is None:
                    authorized_misses = self._presence_miss_by_node.get(node_id, 0) + 1
                    unknown_misses = self._unknown_miss_by_node.get(node_id, 0) + 1
                    self._presence_miss_by_node[node_id] = authorized_misses
                    self._unknown_miss_by_node[node_id] = unknown_misses
                    if authorized_misses >= miss_reset_threshold:
                        self._presence_visible_by_node[node_id] = False
                        self._presence_name_by_node[node_id] = ""
                    if unknown_misses >= miss_reset_threshold:
                        self._unknown_visible_by_node[node_id] = False
                    continue

                verdicts = self.face_service.classify_faces_with_bbox(frame, max_faces=5)
                location = infer_location_from_node(node_id)

                authorized_verdicts = [
                    verdict
                    for verdict in verdicts
                    if str(verdict.get("result") or "").lower() == "authorized"
                ]
                unknown_verdicts = [
                    verdict
                    for verdict in verdicts
                    if str(verdict.get("result") or "").lower() == "unknown"
                    and bool(verdict.get("face_present"))
                ]

                if unknown_verdicts:
                    self._presence_miss_by_node[node_id] = 0
                    self._presence_visible_by_node[node_id] = False
                    self._presence_name_by_node[node_id] = ""

                    self._unknown_miss_by_node[node_id] = 0
                    was_unknown_visible = self._unknown_visible_by_node.get(
                        node_id, False
                    )
                    last_unknown_logged_at = self._unknown_last_logged_at_by_node.get(
                        node_id, 0.0
                    )
                    unknown_cooldown_ready = (now_ts - last_unknown_logged_at) >= float(
                        self.unknown_presence_cooldown_seconds
                    )
                    unknown_entered_view = not was_unknown_visible

                    primary_unknown = unknown_verdicts[0]

                    if self.unknown_presence_logging_enabled and (
                        unknown_entered_view or unknown_cooldown_ready
                    ):
                        try:
                            snapshot_path = self.camera_manager.save_snapshot(
                                node_id, frame, "intruder_unknown_presence"
                            )
                        except Exception:
                            snapshot_path = ""
                        details = {
                            "face": primary_unknown,
                            "faces": verdicts,
                            "detection_mode": "unknown_presence_scan",
                            "presence_transition": "entered_fov",
                            "snapshot_path": snapshot_path,
                        }
                        event_id = store.create_event(
                            event_type="intruder",
                            event_code="UNKNOWN",
                            source_node=node_id,
                            location=location,
                            severity="critical",
                            title="Non-Authorized Person Detected",
                            description="Non-authorized face classification in camera field of view",
                            details=details,
                        )
                        alert_id = store.create_alert(
                            alert_type="INTRUDER",
                            severity="critical",
                            status="ACTIVE",
                            requires_ack=True,
                            title="Non-Authorized Person / Tamper Alert",
                            description="Non-authorized face classification in camera field of view",
                            source_node=node_id,
                            location=location,
                            event_id=event_id,
                            snapshot_path=snapshot_path,
                            details=details,
                        )
                        store.log(
                            "INFO",
                            f"unknown presence alert node={node_id} alert_id={alert_id} snapshot={snapshot_path or 'none'}",
                        )
                        if self.notification_dispatcher:
                            try:
                                self.notification_dispatcher.dispatch_alert_by_id(
                                    alert_id
                                )
                            except Exception as exc:
                                store.log(
                                    "ERROR",
                                    f"notification dispatch failed for alert {alert_id}: {exc}",
                                )
                        self._unknown_last_logged_at_by_node[node_id] = now_ts

                    self._unknown_visible_by_node[node_id] = True
                    continue

                if authorized_verdicts:
                    self._presence_miss_by_node[node_id] = 0
                    self._unknown_miss_by_node[node_id] = 0
                    self._unknown_visible_by_node[node_id] = False

                    was_visible = self._presence_visible_by_node.get(node_id, False)
                    last_logged_at = self._presence_last_logged_at_by_node.get(
                        node_id, 0.0
                    )

                    cooldown_ready = (now_ts - last_logged_at) >= float(
                        self.authorized_presence_cooldown_seconds
                    )
                    entered_view = not was_visible
                    primary_authorized = authorized_verdicts[0]

                    if self.authorized_presence_logging_enabled and (
                        entered_view or cooldown_ready
                    ):
                        try:
                            snapshot_path = self.camera_manager.save_snapshot(
                                node_id, frame, "authorized_presence"
                            )
                        except Exception:
                            snapshot_path = ""

                        details = {
                            "face": primary_authorized,
                            "faces": verdicts,
                            "detection_mode": "authorized_presence_scan",
                            "presence_transition": "entered_fov",
                            "snapshot_path": snapshot_path,
                        }
                        event_id = store.create_event(
                            event_type="authorized",
                            event_code="AUTHORIZED",
                            source_node=node_id,
                            location=location,
                            severity="normal",
                            title="Authorized Person Detected",
                            description="Authorized face classification in camera field of view",
                            details=details,
                        )
                        alert_id = store.create_alert(
                            alert_type="AUTHORIZED_ENTRY",
                            severity="info",
                            status="RESOLVED",
                            requires_ack=False,
                            title="Authorized Entry",
                            description="Authorized face classification",
                            source_node=node_id,
                            location=location,
                            event_id=event_id,
                            snapshot_path=snapshot_path,
                            details=details,
                        )
                        store.log(
                            "INFO",
                            f"authorized presence alert node={node_id} alert_id={alert_id} snapshot={snapshot_path or 'none'}",
                        )
                        if self.notification_dispatcher:
                            try:
                                self.notification_dispatcher.dispatch_alert_by_id(
                                    alert_id
                                )
                            except Exception as exc:
                                store.log(
                                    "ERROR",
                                    f"notification dispatch failed for alert {alert_id}: {exc}",
                                )
                        self._presence_last_logged_at_by_node[node_id] = now_ts

                    self._presence_visible_by_node[node_id] = True
                    self._presence_name_by_node[node_id] = "authorized"
                    continue

                authorized_misses = self._presence_miss_by_node.get(node_id, 0) + 1
                unknown_misses = self._unknown_miss_by_node.get(node_id, 0) + 1
                self._presence_miss_by_node[node_id] = authorized_misses
                self._unknown_miss_by_node[node_id] = unknown_misses
                if authorized_misses >= miss_reset_threshold:
                    self._presence_visible_by_node[node_id] = False
                    self._presence_name_by_node[node_id] = ""
                if unknown_misses >= miss_reset_threshold:
                    self._unknown_visible_by_node[node_id] = False
            except Exception as exc:
                store.log("ERROR", f"face presence scan failed for {node_id}: {exc}")

    def _check_nodes(self) -> None:
        offline_rows = store.list_offline_devices(self.node_offline_seconds)
        for row in offline_rows:
            node_id = str(row.get("node_id") or "unknown")
            store.set_device_status(node_id, "offline", "heartbeat timeout")
            if store.event_exists_recent("NODE_OFFLINE", node_id, window_seconds=300):
                continue
            event_id = store.create_event(
                event_type="system",
                event_code="NODE_OFFLINE",
                source_node=node_id,
                location=infer_location_from_node(node_id),
                severity="warning",
                title="Sensor Node Offline",
                description=f"{node_id} has not sent heartbeat in {self.node_offline_seconds}s",
                details={"timeout_seconds": self.node_offline_seconds},
            )
            alert_id = store.create_alert(
                alert_type="NODE_OFFLINE",
                severity="warning",
                status="ACTIVE",
                requires_ack=True,
                title="Sensor Node Offline",
                description=f"{node_id} heartbeat timeout",
                source_node=node_id,
                location=infer_location_from_node(node_id),
                event_id=event_id,
                details={"timeout_seconds": self.node_offline_seconds},
            )
            if self.notification_dispatcher:
                try:
                    self.notification_dispatcher.dispatch_alert_by_id(alert_id)
                except Exception as exc:
                    store.log(
                        "ERROR",
                        f"notification dispatch failed for alert {alert_id}: {exc}",
                    )

        self._check_cameras()

    def _check_cameras(self) -> None:
        now = datetime.now(timezone.utc)
        for row in store.list_cameras():
            node_id = str(row.get("node_id") or "")
            if not node_id:
                continue

            last_seen_raw = str(row.get("last_seen_ts") or "").strip()
            if not last_seen_raw:
                continue

            try:
                seen = datetime.fromisoformat(last_seen_raw.replace("Z", "+00:00"))
            except ValueError:
                continue
            if seen.tzinfo is None:
                seen = seen.replace(tzinfo=timezone.utc)
            else:
                seen = seen.astimezone(timezone.utc)

            elapsed = (now - seen).total_seconds()
            if elapsed <= float(self.camera_offline_seconds):
                continue

            if str(row.get("status") or "").strip().lower() != "offline":
                store.set_camera_runtime(
                    node_id,
                    "offline",
                    f"stream timeout ({self.camera_offline_seconds}s)",
                )

            if store.event_exists_recent("CAMERA_OFFLINE", node_id, window_seconds=300):
                continue

            location = str(row.get("location") or infer_location_from_node(node_id))
            event_id = store.create_event(
                event_type="system",
                event_code="CAMERA_OFFLINE",
                source_node=node_id,
                location=location,
                severity="warning",
                title="Camera Disconnected",
                description=f"{node_id} stream unavailable for {self.camera_offline_seconds}s",
                details={"timeout_seconds": self.camera_offline_seconds},
            )
            alert_id = store.create_alert(
                alert_type="CAMERA_OFFLINE",
                severity="warning",
                status="ACTIVE",
                requires_ack=True,
                title="Camera Disconnected",
                description=f"{node_id} stream unavailable",
                source_node=node_id,
                location=location,
                event_id=event_id,
                details={"timeout_seconds": self.camera_offline_seconds},
            )
            if self.notification_dispatcher:
                try:
                    self.notification_dispatcher.dispatch_alert_by_id(alert_id)
                except Exception as exc:
                    store.log(
                        "ERROR",
                        f"notification dispatch failed for alert {alert_id}: {exc}",
                    )

    def _run_retention(self) -> None:
        store.cleanup_old_records(self.event_retention_days, self.log_retention_days)

        now = datetime.now(timezone.utc)
        regular_cutoff = now - timedelta(days=self.regular_snapshot_retention_days)
        critical_cutoff = now - timedelta(days=self.critical_snapshot_retention_days)

        if not self.snapshot_root.exists():
            return

        for day_dir in self.snapshot_root.iterdir():
            if not day_dir.is_dir():
                continue
            for file_path in day_dir.iterdir():
                if not file_path.is_file():
                    continue
                name = file_path.name.lower()
                cutoff = (
                    critical_cutoff
                    if ("fire_confirmed" in name or "intruder_unknown" in name)
                    else regular_cutoff
                )
                mtime = datetime.fromtimestamp(
                    file_path.stat().st_mtime, tz=timezone.utc
                )
                if mtime < cutoff:
                    try:
                        file_path.unlink(missing_ok=True)
                    except Exception:
                        continue
            try:
                next(day_dir.iterdir())
            except StopIteration:
                try:
                    day_dir.rmdir()
                except Exception:
                    pass
