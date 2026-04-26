from __future__ import annotations

import json
from typing import Any, Callable, cast

from ..core.config import Settings
from ..db import store
from .remote_access import LinkResolver

try:
    from pywebpush import WebPushException, webpush  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    WebPushException = Exception  # type: ignore
    webpush = None


def _parse_bool(raw: str | None, default: bool = False) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "enabled"}


def _safe_json(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


class NotificationDispatcher:
    def __init__(
        self,
        settings: Settings,
        link_resolver: LinkResolver | None = None,
    ) -> None:
        self.settings = settings
        self.vapid_public_key = settings.webpush_vapid_public_key
        self.vapid_private_key = settings.webpush_vapid_private_key
        self.vapid_subject = settings.webpush_vapid_subject or "mailto:admin@localhost"

        self.link_resolver = link_resolver

    def apply_runtime_setting(self, key: str, value: str) -> None:
        normalized_key = key.strip().upper()
        if normalized_key == "WEBPUSH_VAPID_PUBLIC_KEY":
            self.vapid_public_key = str(value or "").strip()
            return
        if normalized_key == "WEBPUSH_VAPID_PRIVATE_KEY":
            self.vapid_private_key = str(value or "").strip()
            return
        if normalized_key == "WEBPUSH_VAPID_SUBJECT":
            self.vapid_subject = str(value or "").strip() or "mailto:admin@localhost"
            return

    @property
    def push_available(self) -> bool:
        return bool(webpush and self.vapid_public_key and self.vapid_private_key)

    def _build_push_payload(self, alert: dict[str, Any]) -> dict[str, Any]:
        details = _safe_json(alert.get("details_json"))
        alert_id = int(alert.get("id") or 0)
        title = str(details.get("title") or alert.get("type") or "Alert").strip()
        if not title:
            title = "Security alert"

        description = str(details.get("description") or "Please review the latest alert.")
        description = description.strip() or "Please review the latest alert."
        location = str(details.get("location") or "")
        source_node = str(details.get("source_node") or "system")

        if location:
            body = f"{description} Location: {location}. Open Alerts to review."
        else:
            body = f"{description} Open Alerts to review."

        return {
            "title": title,
            "body": body,
            "url": "/dashboard/remote/mobile",
            "tag": f"alert-{alert_id}",
            "data": {
                "alert_id": alert_id,
                "alert_type": str(alert.get("type") or "ALERT"),
                "severity": str(alert.get("severity") or "info"),
                "source_node": source_node,
                "location": location,
            },
        }

    def _mobile_push_enabled(self) -> bool:
        return _parse_bool(store.get_setting("mobile_push_enabled"), default=True)

    def _resolve_access_links(self) -> dict[str, Any]:
        if not self.link_resolver:
            return {
                "preferred_url": "/dashboard/remote/mobile",
                "tailscale_url": "",
                "lan_url": "",
                "mdns_url": "",
                "route": "/dashboard/remote/mobile",
                "host_label": "windows-host",
                "port": self.settings.backend_port,
                "fingerprint": "static-route-only",
            }
        return self.link_resolver.resolve_links().to_dict()

    def send_access_links(
        self,
        reason: str = "manual",
        force: bool = False,
        links: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        _ = force
        links_payload = links or self._resolve_access_links()
        return {
            "sent": False,
            "status": "disabled",
            "detail": "Telegram notifications are disabled.",
            "reason": reason,
            "links": links_payload,
        }

    def send_startup_access_links(self) -> dict[str, Any]:
        return self.send_access_links(reason="startup", force=False)

    def poll_access_link_changes(self) -> dict[str, Any]:
        return {
            "sent": False,
            "status": "disabled",
            "detail": "Telegram notifications are disabled.",
            "reason": "endpoint_change",
            "links": self._resolve_access_links(),
        }

    def dispatch_alert_by_id(self, alert_id: int) -> None:
        alert = store.get_alert(alert_id)
        if not alert:
            return
        self.dispatch_alert(alert)

    def dispatch_alert(self, alert: dict[str, Any]) -> None:
        alert_id = int(alert.get("id") or 0) or None
        devices = store.list_mobile_devices(enabled_only=True)
        if not devices:
            store.create_notification_delivery_log(
                "push",
                "skipped",
                "No active mobile devices registered.",
                alert_id=alert_id,
            )
            return

        if not self._mobile_push_enabled():
            store.create_notification_delivery_log(
                "push",
                "disabled",
                "Mobile push disabled by configuration.",
                alert_id=alert_id,
            )
            return

        payload = self._build_push_payload(alert)

        for device in devices:
            user_id = int(device.get("user_id") or 0)
            prefs = store.get_notification_prefs(user_id)

            if not prefs.get("push_enabled", True):
                store.create_notification_delivery_log(
                    "push",
                    "skipped",
                    f"Push disabled in preferences for user_id={user_id}.",
                    alert_id=alert_id,
                )
                continue

            subscription = _safe_json(device.get("push_subscription_json"))
            if not subscription:
                store.create_notification_delivery_log(
                    "push",
                    "skipped",
                    f"Missing push subscription for device_id={device.get('device_id')}.",
                    alert_id=alert_id,
                )
                continue

            if not self.push_available:
                store.create_notification_delivery_log(
                    "push",
                    "unavailable",
                    "Web push dependency or VAPID keys are missing.",
                    alert_id=alert_id,
                )
                continue

            try:
                push_sender = cast(Callable[..., Any], webpush)
                push_sender(
                    subscription_info=subscription,
                    data=json.dumps(payload, separators=(",", ":")),
                    vapid_private_key=self.vapid_private_key,
                    vapid_claims={"sub": self.vapid_subject},
                    ttl=60,
                )
                store.create_notification_delivery_log(
                    "push",
                    "sent",
                    f"Delivered to device_id={device.get('device_id')}.",
                    alert_id=alert_id,
                )
            except WebPushException as exc:
                store.create_notification_delivery_log(
                    "push",
                    "failed",
                    f"device_id={device.get('device_id')} error={exc}",
                    alert_id=alert_id,
                )
            except Exception as exc:
                store.create_notification_delivery_log(
                    "push",
                    "failed",
                    f"device_id={device.get('device_id')} unexpected={exc}",
                    alert_id=alert_id,
                )
