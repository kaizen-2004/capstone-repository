from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..db import store
from ..modules.event_engine import infer_location_from_node
from ..modules.face_service import FaceService
from .camera_manager import CameraManager
from .notification_dispatcher import NotificationDispatcher


class Supervisor:
    def __init__(
        self,
        node_offline_seconds: int,
        event_retention_days: int,
        log_retention_days: int,
        snapshot_root: Path,
        regular_snapshot_retention_days: int,
        critical_snapshot_retention_days: int,
        notification_dispatcher: NotificationDispatcher | None = None,
        remote_access_poll_seconds: int = 60,
        camera_manager: CameraManager | None = None,
        face_service: FaceService | None = None,
        authorized_presence_logging_enabled: bool = False,
        authorized_presence_scan_seconds: int = 2,
        authorized_presence_cooldown_seconds: int = 20,
        unknown_presence_logging_enabled: bool = False,
        unknown_presence_cooldown_seconds: int = 20,
    ) -> None:
        self.node_offline_seconds = node_offline_seconds
        self.event_retention_days = event_retention_days
        self.log_retention_days = log_retention_days
        self.snapshot_root = snapshot_root
        self.regular_snapshot_retention_days = regular_snapshot_retention_days
        self.critical_snapshot_retention_days = critical_snapshot_retention_days
        self.notification_dispatcher = notification_dispatcher
        self.remote_access_poll_seconds = max(20, int(remote_access_poll_seconds))
        self.camera_manager = camera_manager
        self.face_service = face_service
        face_scan_dependencies_ready = (
            camera_manager is not None and face_service is not None
        )
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

                if self.face_presence_logging_enabled and now >= next_presence_scan:
                    self._scan_face_presence(now)
                    next_presence_scan = now + float(
                        self.authorized_presence_scan_seconds
                    )
            except Exception as exc:
                store.log("ERROR", f"supervisor loop failed: {exc}")

            self._stop.wait(1.0 if self.face_presence_logging_enabled else 10.0)

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

                verdict = self.face_service.classify_frame_with_bbox(frame)
                result = str(verdict.get("result") or "").lower()
                face_present = bool(verdict.get("face_present"))
                location = infer_location_from_node(node_id)

                if result == "authorized":
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

                    if self.authorized_presence_logging_enabled and (
                        entered_view or cooldown_ready
                    ):
                        snapshot_path = self.camera_manager.save_snapshot(
                            node_id, frame, "authorized_presence"
                        )
                        details = {
                            "face": verdict,
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

                is_unknown_face = result == "unknown" and face_present
                if is_unknown_face:
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

                    if self.unknown_presence_logging_enabled and (
                        unknown_entered_view or unknown_cooldown_ready
                    ):
                        snapshot_path = self.camera_manager.save_snapshot(
                            node_id, frame, "intruder_unknown_presence"
                        )
                        details = {
                            "face": verdict,
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
