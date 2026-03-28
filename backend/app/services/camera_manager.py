from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from ..db import store


@dataclass
class CameraConfig:
    node_id: str
    label: str
    location: str
    rtsp_url: str
    fps_target: int


class CameraWorker:
    def __init__(self, config: CameraConfig) -> None:
        self.config = config
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._capture: cv2.VideoCapture | None = None
        self._last_frame: np.ndarray | None = None
        self._last_seen = 0.0
        self._status = "offline"
        self._last_error = "not started"

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name=f"camera-{self.config.node_id}", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.5)
        self._release_capture()

    def _release_capture(self) -> None:
        cap = self._capture
        self._capture = None
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass

    def _connect(self) -> bool:
        self._release_capture()
        if not self.config.rtsp_url:
            self._status = "offline"
            self._last_error = "RTSP URL not configured"
            store.set_camera_runtime(self.config.node_id, "offline", self._last_error)
            return False
        cap = cv2.VideoCapture(self.config.rtsp_url)
        if not cap.isOpened():
            self._status = "offline"
            self._last_error = "unable to open stream"
            store.set_camera_runtime(self.config.node_id, "offline", self._last_error)
            try:
                cap.release()
            except Exception:
                pass
            return False
        self._capture = cap
        self._status = "online"
        self._last_error = ""
        store.set_camera_runtime(self.config.node_id, "online", "")
        return True

    def _run(self) -> None:
        reconnect_wait = 4.0
        frame_period = 1.0 / max(1, int(self.config.fps_target))
        while not self._stop.is_set():
            if self._capture is None and not self._connect():
                self._stop.wait(reconnect_wait)
                continue

            try:
                ok, frame = self._capture.read() if self._capture is not None else (False, None)
            except Exception as exc:
                ok = False
                frame = None
                self._last_error = f"read failed: {exc}"

            if not ok or frame is None:
                self._status = "offline"
                store.set_camera_runtime(self.config.node_id, "offline", self._last_error or "read failed")
                self._release_capture()
                self._stop.wait(reconnect_wait)
                continue

            with self._lock:
                self._last_frame = frame
                self._last_seen = time.time()
                self._status = "online"
                self._last_error = ""
            store.set_camera_runtime(self.config.node_id, "online", "")
            self._stop.wait(frame_period)

        self._release_capture()

    def snapshot(self) -> np.ndarray | None:
        with self._lock:
            if self._last_frame is None:
                return None
            return self._last_frame.copy()

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "node_id": self.config.node_id,
                "label": self.config.label,
                "location": self.config.location,
                "status": self._status,
                "last_seen": self._last_seen,
                "last_error": self._last_error,
            }


class CameraManager:
    def __init__(self, storage_snapshot_root: Path) -> None:
        self._workers: dict[str, CameraWorker] = {}
        self._snapshot_root = storage_snapshot_root
        self._snapshot_root.mkdir(parents=True, exist_ok=True)

    def configure(self, camera_configs: list[CameraConfig]) -> None:
        next_map: dict[str, CameraWorker] = {}
        for cfg in camera_configs:
            existing = self._workers.get(cfg.node_id)
            if existing and existing.config.rtsp_url == cfg.rtsp_url and existing.config.fps_target == cfg.fps_target:
                next_map[cfg.node_id] = existing
                continue
            if existing:
                existing.stop()
            worker = CameraWorker(cfg)
            next_map[cfg.node_id] = worker

        for node_id, worker in list(self._workers.items()):
            if node_id not in next_map:
                worker.stop()

        self._workers = next_map

    def start(self) -> None:
        for worker in self._workers.values():
            worker.start()

    def stop(self) -> None:
        for worker in self._workers.values():
            worker.stop()

    def snapshot_frame(self, node_id: str) -> np.ndarray | None:
        worker = self._workers.get(node_id)
        if not worker:
            return None
        return worker.snapshot()

    def save_snapshot(self, node_id: str, frame: np.ndarray, prefix: str) -> str:
        date_part = time.strftime("%Y-%m-%d")
        target_dir = self._snapshot_root / date_part
        target_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%H%M%S")
        file_name = f"{prefix}_{node_id}_{stamp}.jpg"
        abs_path = target_dir / file_name
        cv2.imwrite(str(abs_path), frame)
        return str(abs_path.relative_to(self._snapshot_root.parent))

    def live_status(self) -> list[dict[str, Any]]:
        return [worker.status() for worker in self._workers.values()]
