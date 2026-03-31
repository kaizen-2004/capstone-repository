from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..db import store
from ..modules.event_engine import infer_location_from_node
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
    ) -> None:
        self.node_offline_seconds = node_offline_seconds
        self.event_retention_days = event_retention_days
        self.log_retention_days = log_retention_days
        self.snapshot_root = snapshot_root
        self.regular_snapshot_retention_days = regular_snapshot_retention_days
        self.critical_snapshot_retention_days = critical_snapshot_retention_days
        self.notification_dispatcher = notification_dispatcher
        self.remote_access_poll_seconds = max(20, int(remote_access_poll_seconds))

        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="backend-supervisor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.5)

    def _run(self) -> None:
        next_retention_run = 0.0
        next_remote_access_poll = 0.0
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
                    next_remote_access_poll = now + float(self.remote_access_poll_seconds)
            except Exception as exc:
                store.log("ERROR", f"supervisor loop failed: {exc}")

            self._stop.wait(10.0)

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
                    store.log("ERROR", f"notification dispatch failed for alert {alert_id}: {exc}")

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
                cutoff = critical_cutoff if ("fire_confirmed" in name or "intruder_unknown" in name) else regular_cutoff
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)
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
