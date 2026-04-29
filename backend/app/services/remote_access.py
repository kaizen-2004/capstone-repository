from __future__ import annotations

import hashlib
import ipaddress
import re
import socket
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from fastapi import Request

from ..core.config import Settings
from ..db import store

try:
    from zeroconf import IPVersion, ServiceInfo, Zeroconf  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    IPVersion = None  # type: ignore
    ServiceInfo = None  # type: ignore
    Zeroconf = None  # type: ignore


MOBILE_ROUTE = "/dashboard/remote/mobile"
MDNS_SERVICE_TYPE = "_http._tcp.local."


@dataclass(frozen=True)
class RemoteAccessLinks:
    preferred_url: str
    tailscale_url: str
    lan_url: str
    mdns_url: str
    route: str
    host_label: str
    port: int
    fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "preferred_url": self.preferred_url,
            "tailscale_url": self.tailscale_url,
            "lan_url": self.lan_url,
            "mdns_url": self.mdns_url,
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

    @staticmethod
    def sanitize_mdns_hostname(raw: str) -> str:
        text = raw.strip().lower()
        if not text:
            text = "thesis-monitor"
        text = re.sub(r"[^a-z0-9-]", "-", text)
        text = re.sub(r"-+", "-", text).strip("-")
        return text or "thesis-monitor"

    def mdns_hostname(self) -> str:
        configured = self.settings.mdns_hostname.strip()
        if configured:
            return self.sanitize_mdns_hostname(configured)
        return self.sanitize_mdns_hostname(socket.gethostname())

    def resolve_mdns_base_url(self) -> str:
        if not self.settings.mdns_enabled:
            return ""
        if not (Zeroconf and ServiceInfo and IPVersion):
            return ""
        if not self.detect_lan_ip():
            return ""
        hostname = self.mdns_hostname()
        return f"http://{hostname}.local:{self.backend_port}"

    def resolve_links(self, request: Request | None = None) -> RemoteAccessLinks:
        tailscale_base = self.resolve_tailscale_base_url()
        lan_base = self.resolve_lan_base_url(request=request)
        mdns_base = self.resolve_mdns_base_url()

        tailscale_url = self._join(tailscale_base, self.mobile_route)
        lan_url = self._join(lan_base, self.mobile_route)
        mdns_url = self._join(mdns_base, self.mobile_route)

        preferred_url = tailscale_url or mdns_url or lan_url

        fingerprint_input = "|".join(
            [preferred_url, tailscale_url, mdns_url, lan_url, str(self.backend_port)]
        )
        fingerprint = hashlib.sha256(fingerprint_input.encode("utf-8")).hexdigest()[:16]

        return RemoteAccessLinks(
            preferred_url=preferred_url,
            tailscale_url=tailscale_url,
            lan_url=lan_url,
            mdns_url=mdns_url,
            route=self.mobile_route,
            host_label=socket.gethostname(),
            port=self.backend_port,
            fingerprint=fingerprint,
        )


class MdnsPublisher:
    def __init__(self, settings: Settings, resolver: LinkResolver) -> None:
        self.settings = settings
        self.resolver = resolver

        self._zc: Zeroconf | None = None
        self._service_info: ServiceInfo | None = None
        self._published = False
        self._detail = "mDNS publisher has not started."
        self._bound_ip = ""

    @property
    def available(self) -> bool:
        return bool(Zeroconf and ServiceInfo and IPVersion)

    def start(self) -> None:
        if not self.settings.mdns_enabled:
            self._published = False
            self._detail = "mDNS is disabled by configuration."
            return

        if not self.available:
            self._published = False
            self._detail = "zeroconf dependency is unavailable; mDNS publish skipped."
            return

        address = self.resolver.detect_lan_ip()
        if not address:
            self._published = False
            self._detail = "Unable to resolve LAN IPv4 address for mDNS publishing."
            return

        hostname = self.resolver.mdns_hostname()
        service_name = self.settings.mdns_service_name.strip() or "thesis-monitor"
        full_service_name = f"{service_name}.{MDNS_SERVICE_TYPE}"

        try:
            zc = Zeroconf(ip_version=IPVersion.V4Only)
            info = ServiceInfo(
                type_=MDNS_SERVICE_TYPE,
                name=full_service_name,
                addresses=[socket.inet_aton(address)],
                port=self.settings.backend_port,
                properties={
                    b"path": MOBILE_ROUTE.encode("utf-8"),
                    b"service": b"thesis-monitor",
                },
                server=f"{hostname}.local.",
            )
            zc.register_service(info, allow_name_change=True)
            self._zc = zc
            self._service_info = info
            self._published = True
            self._bound_ip = address
            self._detail = f"Published {service_name}.local on {address}:{self.settings.backend_port}."
        except Exception as exc:
            self._published = False
            self._detail = f"mDNS publish failed: {exc}"
            self.stop()

    def stop(self) -> None:
        if self._zc and self._service_info:
            try:
                self._zc.unregister_service(self._service_info)
            except Exception:
                pass
        if self._zc:
            try:
                self._zc.close()
            except Exception:
                pass

        self._zc = None
        self._service_info = None
        self._published = False
        self._bound_ip = ""

    def status(self) -> dict[str, Any]:
        hostname = self.resolver.mdns_hostname()
        mdns_url = self.resolver.resolve_mdns_base_url()
        return {
            "ok": True,
            "enabled": self.settings.mdns_enabled,
            "available": self.available,
            "published": self._published,
            "service_name": self.settings.mdns_service_name,
            "hostname": f"{hostname}.local",
            "port": self.settings.backend_port,
            "bound_ip": self._bound_ip,
            "mdns_base_url": mdns_url,
            "detail": self._detail,
        }
