from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

import cv2
import httpx
import numpy as np

from ..db import store


@dataclass
class CameraConfig:
    node_id: str
    label: str
    location: str
    rtsp_url: str
    fps_target: int
    source_mode: str = "rtsp"
    webcam_index: int | None = None
    webcam_fallback_index: int | None = None


class CameraWorker:
    def __init__(self, config: CameraConfig) -> None:
        self.config = config
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._capture: cv2.VideoCapture | None = None
        self._http_client: httpx.Client | None = None
        self._last_frame: np.ndarray | None = None
        self._last_seen = 0.0
        self._status = "offline"
        self._last_error = "not started"

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name=f"camera-{self.config.node_id}", daemon=True
        )
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

        client = self._http_client
        self._http_client = None
        if client is not None:
            try:
                client.close()
            except Exception:
                pass

    def _connect(self) -> bool:
        self._release_capture()
        if self.config.source_mode == "webcam":
            return self._connect_webcam()
        return self._connect_rtsp()

    def _http_snapshot_url(self) -> str:
        if self.config.source_mode != "rtsp":
            return ""

        source = (self.config.rtsp_url or "").strip()
        if not source:
            return ""

        parsed = urlparse(source)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return ""

        path = parsed.path or ""
        if not path.endswith("/stream"):
            return ""

        # ESP32-CAM stream is usually :81/stream while capture is on :80 (/capture).
        port = parsed.port
        include_port = port not in {None, 80, 81, 443}
        netloc = parsed.hostname if not include_port else f"{parsed.hostname}:{port}"
        return urlunparse((parsed.scheme, netloc, "/capture", "", "", ""))

    def _capture_http_snapshot(self, snapshot_url: str) -> np.ndarray | None:
        client = self._http_client
        if client is None:
            client = httpx.Client(
                timeout=httpx.Timeout(3.0, connect=1.0),
                limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
            )
            self._http_client = client

        try:
            response = client.get(snapshot_url)
        except Exception:
            try:
                client.close()
            except Exception:
                pass
            client = httpx.Client(
                timeout=httpx.Timeout(3.0, connect=1.0),
                limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
            )
            self._http_client = client
            response = client.get(snapshot_url)

        if response.status_code >= 400:
            self._last_error = f"http snapshot status={response.status_code}"
            return None

        arr = np.frombuffer(response.content, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            self._last_error = "http snapshot decode failed"
            return None
        return frame

    def _connect_rtsp(self) -> bool:
        if not self.config.rtsp_url:
            self._status = "offline"
            self._last_error = "RTSP URL not configured"
            store.set_camera_runtime(self.config.node_id, "offline", self._last_error)
            return False

        source_url = (self.config.rtsp_url or "").strip()
        parsed = urlparse(source_url)
        open_url = source_url
        if parsed.scheme == "rtsp":
            query = parsed.query
            if "rtsp_transport=" not in query:
                query = f"{query}&rtsp_transport=tcp" if query else "rtsp_transport=tcp"
            if "fflags=" not in query:
                query = f"{query}&fflags=nobuffer" if query else "fflags=nobuffer"
            if "max_delay=" not in query:
                query = f"{query}&max_delay=0" if query else "max_delay=0"
            open_url = urlunparse(parsed._replace(query=query))

        cap = cv2.VideoCapture(open_url, cv2.CAP_FFMPEG)
        if not cap.isOpened() and open_url != source_url:
            cap.release()
            cap = cv2.VideoCapture(source_url, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            cap.release()
            cap = cv2.VideoCapture(source_url)
        if not cap.isOpened():
            self._status = "offline"
            self._last_error = "unable to open RTSP stream"
            store.set_camera_runtime(self.config.node_id, "offline", self._last_error)
            try:
                cap.release()
            except Exception:
                pass
            return False

        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass

        self._capture = cap
        self._status = "online"
        self._last_error = ""
        store.set_camera_runtime(self.config.node_id, "online", "")
        return True

    def _connect_webcam(self) -> bool:
        requested_index = self.config.webcam_index
        fallback_index = self.config.webcam_fallback_index

        webcam_indices: list[int] = []
        if requested_index is not None:
            webcam_indices.append(int(requested_index))
        if fallback_index is not None and fallback_index not in webcam_indices:
            webcam_indices.append(int(fallback_index))

        if not webcam_indices:
            self._status = "offline"
            self._last_error = "webcam index not configured"
            store.set_camera_runtime(self.config.node_id, "offline", self._last_error)
            return False

        errors: list[str] = []
        for webcam_index in webcam_indices:
            cap = cv2.VideoCapture(webcam_index)
            if not cap.isOpened():
                errors.append(f"index {webcam_index} unavailable")
                try:
                    cap.release()
                except Exception:
                    pass
                continue

            self._capture = cap
            self._status = "online"
            self._last_error = ""
            store.set_camera_runtime(self.config.node_id, "online", "")
            return True

        self._capture = None
        self._status = "offline"
        self._last_error = (
            ", ".join(errors) if errors else "unable to open webcam source"
        )
        store.set_camera_runtime(self.config.node_id, "offline", self._last_error)
        return False

    def _run(self) -> None:
        reconnect_wait = 4.0
        frame_period = 1.0 / max(1, int(self.config.fps_target))
        snapshot_url = self._http_snapshot_url()

        while not self._stop.is_set():
            if snapshot_url:
                started_at = time.perf_counter()
                try:
                    frame = self._capture_http_snapshot(snapshot_url)
                except Exception as exc:
                    frame = None
                    self._last_error = f"http snapshot failed: {exc}"

                if frame is None:
                    self._status = "offline"
                    store.set_camera_runtime(
                        self.config.node_id,
                        "offline",
                        self._last_error or "http snapshot failed",
                    )
                    self._stop.wait(min(reconnect_wait, frame_period * 2.0))
                    continue

                with self._lock:
                    self._last_frame = frame
                    self._last_seen = time.time()
                    self._status = "online"
                    self._last_error = ""
                store.set_camera_runtime(self.config.node_id, "online", "")
                elapsed = time.perf_counter() - started_at
                remaining_wait = max(0.0, frame_period - elapsed)
                self._stop.wait(remaining_wait)
                continue

            if self._capture is None and not self._connect():
                self._stop.wait(reconnect_wait)
                continue

            try:
                if self._capture is None:
                    ok, frame = (False, None)
                else:
                    if self.config.source_mode == "rtsp":
                        # Drop queued frames aggressively to keep latency low.
                        for _ in range(2):
                            if not self._capture.grab():
                                break
                    ok, frame = self._capture.read()
            except Exception as exc:
                ok = False
                frame = None
                self._last_error = f"read failed: {exc}"

            if not ok or frame is None:
                self._status = "offline"
                store.set_camera_runtime(
                    self.config.node_id, "offline", self._last_error or "read failed"
                )
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
            if existing and (
                existing.config.source_mode == cfg.source_mode
                and existing.config.rtsp_url == cfg.rtsp_url
                and existing.config.webcam_index == cfg.webcam_index
                and existing.config.webcam_fallback_index == cfg.webcam_fallback_index
                and existing.config.fps_target == cfg.fps_target
            ):
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
        frame = worker.snapshot() if worker else None
        if frame is not None:
            return frame

        fallback_node = {
            "cam_door": "cam_indoor",
            "cam_indoor": "cam_door",
        }.get(node_id)
        if fallback_node is not None:
            fallback_worker = self._workers.get(fallback_node)
            if fallback_worker is not None:
                return fallback_worker.snapshot()

        return None

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
