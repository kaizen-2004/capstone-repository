from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode, urlparse, urlunparse

import cv2
import httpx
import numpy as np

from ..core.config import Settings
from ..db import store


@dataclass(frozen=True)
class CameraCommandResult:
    ok: bool
    detail: str
    endpoint: str
    payload: dict[str, Any] | None = None


class CameraHttpController:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _stream_url(self, node_id: str) -> str:
        normalized = node_id.strip().lower()
        if normalized == "cam_door":
            override = (store.get_setting("CAMERA_DOOR_STREAM_URL") or "").strip()
            if override:
                return override
        if normalized == "cam_indoor":
            override = (store.get_setting("CAMERA_INDOOR_STREAM_URL") or "").strip()
            if override:
                return override
        if normalized == "cam_door":
            return self.settings.camera_door_rtsp.strip()
        if normalized == "cam_indoor":
            return self.settings.camera_indoor_rtsp.strip()
        return ""

    def _base_url(self, node_id: str) -> str:
        stream_url = self._stream_url(node_id)
        if not stream_url:
            return ""

        parsed = urlparse(stream_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return ""

        port = parsed.port
        include_port = port is not None and port not in {80, 81, 443}
        netloc = parsed.hostname
        if include_port:
            netloc = f"{parsed.hostname}:{port}"

        return urlunparse((parsed.scheme, netloc, "", "", "", "")).rstrip("/")

    def capture_endpoint(self, node_id: str, flash: bool = False) -> str:
        base_url = self._base_url(node_id)
        if not base_url:
            return ""
        query = urlencode({"flash": "1"}) if flash else ""
        return urlunparse(urlparse(f"{base_url}/capture")._replace(query=query))

    def command_endpoint(self, node_id: str, command: str) -> str:
        base_url = self._base_url(node_id)
        if not base_url:
            return ""
        query = urlencode({"cmd": command})
        return urlunparse(urlparse(f"{base_url}/control")._replace(query=query))

    def capture_frame(
        self, node_id: str, flash: bool = False, timeout_seconds: float = 4.0
    ) -> tuple[np.ndarray | None, str]:
        endpoint = self.capture_endpoint(node_id, flash=flash)
        if not endpoint:
            return None, "camera HTTP capture endpoint is not configured"

        try:
            with httpx.Client(timeout=timeout_seconds) as client:
                response = client.get(endpoint)
            if response.status_code >= 400:
                return None, f"capture HTTP {response.status_code}"

            arr = np.frombuffer(response.content, dtype=np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is None:
                return None, "capture decode failed"
            return frame, endpoint
        except Exception as exc:
            return None, f"capture request failed: {exc}"

    def send_command(
        self, node_id: str, command: str, timeout_seconds: float = 3.0
    ) -> CameraCommandResult:
        endpoint = self.command_endpoint(node_id, command)
        if not endpoint:
            return CameraCommandResult(
                ok=False,
                detail="camera HTTP control endpoint is not configured",
                endpoint="",
            )

        try:
            with httpx.Client(timeout=timeout_seconds) as client:
                response = client.get(endpoint)
            if response.status_code >= 400:
                return CameraCommandResult(
                    ok=False,
                    detail=f"camera control HTTP {response.status_code}",
                    endpoint=endpoint,
                )
            payload = response.json() if response.content else {}
            return CameraCommandResult(
                ok=bool(payload.get("ok", True)),
                detail=str(payload.get("detail") or "camera control request completed"),
                endpoint=endpoint,
                payload=payload if isinstance(payload, dict) else None,
            )
        except Exception as exc:
            return CameraCommandResult(
                ok=False,
                detail=f"camera control request failed: {exc}",
                endpoint=endpoint,
            )
