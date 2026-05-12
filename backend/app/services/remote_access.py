from __future__ import annotations

import hashlib
import ipaddress
import socket
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from fastapi import Request

from ..core.config import Settings
from ..db import store

MOBILE_ROUTE = "/dashboard/remote/mobile"


@dataclass(frozen=True)
class RemoteAccessLinks:
    preferred_url: str
    tailscale_url: str
    lan_url: str
    route: str
    host_label: str
    port: int
    fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "preferred_url": self.preferred_url,
            "tailscale_url": self.tailscale_url,
            "lan_url": self.lan_url,
            "route": self.route,
            "host_label": self.host_label,
            "port": self.port,
            "fingerprint": self.fingerprint,
        }


class LinkResolver:
    def __init__(self, settings: Settings, mobile_route: str = MOBILE_ROUTE) -> None:
        self.settings = settings
        self.mobile_route = mobile_route
        self.backend_port = settings.backend_port

    @staticmethod
    def _normalize_base_url(raw: str) -> str:
        text = raw.strip()
        if not text:
            return ""
        if "://" not in text:
            text = f"http://{text}"
        parsed = urlparse(text)
        if not parsed.netloc:
            return ""
        path = parsed.path.rstrip("/")
        return f"{parsed.scheme}://{parsed.netloc}{path}"

    def _runtime_base_url(self, key: str, fallback: str) -> str:
        try:
            stored = store.get_setting(key)
        except Exception:
            stored = None
        return self._normalize_base_url(str(stored) if stored is not None else fallback)

    def configured_lan_base_url(self) -> str:
        return self._runtime_base_url("LAN_BASE_URL", self.settings.lan_base_url)

    def resolve_tailscale_base_url(self) -> str:
        return self._runtime_base_url("TAILSCALE_BASE_URL", self.settings.tailscale_base_url)

    def _join(self, base_url: str, route: str) -> str:
        if not base_url:
            return ""
        return f"{base_url.rstrip('/')}{route}"

    def _safe_host_from_request(self, request: Request | None) -> str:
        if request is None:
            return ""
        host_header = request.headers.get("host", "").strip()
        if not host_header:
            return ""
        if ":" in host_header:
            host = host_header.rsplit(":", 1)[0]
        else:
            host = host_header
        host = host.strip("[]")
        return host

    @staticmethod
    def _is_non_loopback_ipv4(value: str) -> bool:
        try:
            ip = ipaddress.ip_address(value)
        except ValueError:
            return False
        return bool(ip.version == 4 and not ip.is_loopback and not ip.is_unspecified)

    def detect_lan_ip(self, request: Request | None = None) -> str:
        explicit_lan = self.configured_lan_base_url()
        if explicit_lan:
            parsed = urlparse(explicit_lan)
            host = (parsed.hostname or "").strip()
            if self._is_non_loopback_ipv4(host):
                return host

        host_from_request = self._safe_host_from_request(request)
        if self._is_non_loopback_ipv4(host_from_request):
            return host_from_request

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                probe.connect(("8.8.8.8", 80))
                candidate = str(probe.getsockname()[0])
                if self._is_non_loopback_ipv4(candidate):
                    return candidate
        except Exception:
            pass

        try:
            candidate = str(socket.gethostbyname(socket.gethostname()))
            if self._is_non_loopback_ipv4(candidate):
                return candidate
        except Exception:
            pass

        return ""

    def resolve_lan_base_url(self, request: Request | None = None) -> str:
        explicit_lan = self.configured_lan_base_url()
        if explicit_lan:
            return explicit_lan
        detected_ip = self.detect_lan_ip(request=request)
        if detected_ip:
            return f"http://{detected_ip}:{self.backend_port}"
        return f"http://127.0.0.1:{self.backend_port}"

    def resolve_links(self, request: Request | None = None) -> RemoteAccessLinks:
        tailscale_base = self.resolve_tailscale_base_url()
        lan_base = self.resolve_lan_base_url(request=request)

        tailscale_url = self._join(tailscale_base, self.mobile_route)
        lan_url = self._join(lan_base, self.mobile_route)

        preferred_url = lan_url or tailscale_url

        fingerprint_input = "|".join(
            [preferred_url, lan_url, tailscale_url, str(self.backend_port)]
        )
        fingerprint = hashlib.sha256(fingerprint_input.encode("utf-8")).hexdigest()[:16]

        return RemoteAccessLinks(
            preferred_url=preferred_url,
            tailscale_url=tailscale_url,
            lan_url=lan_url,
            route=self.mobile_route,
            host_label=socket.gethostname(),
            port=self.backend_port,
            fingerprint=fingerprint,
        )
