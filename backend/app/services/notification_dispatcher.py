from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, cast

from ..core.config import Settings
from ..db import store
from .remote_access import LinkResolver
from .telegram_notifier import TelegramNotifier

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
        telegram_notifier: TelegramNotifier | None = None,
    ) -> None:
        self.settings = settings
        self.vapid_public_key = settings.webpush_vapid_public_key
        self.vapid_private_key = settings.webpush_vapid_private_key
        self.vapid_subject = settings.webpush_vapid_subject or "mailto:admin@localhost"

        self.link_resolver = link_resolver
        self.telegram_notifier = telegram_notifier or TelegramNotifier(settings)
        self.access_link_cooldown_seconds = 300
        self.telegram_snapshot_cooldown_seconds = max(
            0, int(settings.telegram_snapshot_cooldown_seconds)
        )
        self._last_access_fingerprint = ""
        self._last_access_sent_at = 0.0
        self._last_access_observed_fingerprint = ""
        self._last_snapshot_sent_at_by_key: dict[str, float] = {}

    @property
    def push_available(self) -> bool:
        return bool(webpush and self.vapid_public_key and self.vapid_private_key)

    def _build_push_payload(self, alert: dict[str, Any]) -> dict[str, Any]:
        details = _safe_json(alert.get("details_json"))
        alert_id = int(alert.get("id") or 0)
        severity = str(alert.get("severity") or "info").upper()
        title = str(details.get("title") or alert.get("type") or "Alert")
        description = str(details.get("description") or "Monitoring alert detected.")
        location = str(details.get("location") or "")
        source_node = str(details.get("source_node") or "system")

        return {
            "title": f"[{severity}] {title}",
            "body": description if not location else f"{description} ({location})",
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

    def _access_link_notifications_enabled(self) -> bool:
        return bool(self.settings.telegram_link_notifications_enabled)

    def send_access_links(
        self,
        reason: str = "manual",
        force: bool = False,
        links: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        links_payload = links or self._resolve_access_links()
        fingerprint = str(links_payload.get("fingerprint") or "")
        now = time.time()

        if (
            not force
            and fingerprint
            and fingerprint == self._last_access_fingerprint
            and (now - self._last_access_sent_at) < self.access_link_cooldown_seconds
        ):
            return {
                "sent": False,
                "status": "suppressed",
                "detail": "Access link notification suppressed by cooldown.",
                "reason": reason,
                "links": links_payload,
            }

        if not self.telegram_notifier.enabled:
            detail = "Telegram bot token/chat id not configured."
            store.create_notification_delivery_log(
                "telegram",
                "skipped",
                f"access_links reason={reason}; {detail}",
            )
            self._last_access_fingerprint = fingerprint
            self._last_access_observed_fingerprint = fingerprint
            self._last_access_sent_at = now
            return {
                "sent": False,
                "status": "skipped",
                "detail": detail,
                "reason": reason,
                "links": links_payload,
            }

        message = self.telegram_notifier.format_access_links_message(
            links_payload, reason
        )
        ok, detail = self.telegram_notifier.send_message(message)
        status = "sent" if ok else "failed"

        store.create_notification_delivery_log(
            "telegram",
            status,
            f"access_links reason={reason}; {detail}",
        )

        self._last_access_fingerprint = fingerprint
        self._last_access_observed_fingerprint = fingerprint
        self._last_access_sent_at = now

        return {
            "sent": ok,
            "status": status,
            "detail": detail,
            "reason": reason,
            "links": links_payload,
        }

    def send_startup_access_links(self) -> dict[str, Any]:
        if not self._access_link_notifications_enabled():
            return {
                "sent": False,
                "status": "disabled",
                "detail": "Telegram access link notifications are disabled by configuration.",
                "reason": "startup",
                "links": self._resolve_access_links(),
            }
        return self.send_access_links(reason="startup", force=False)

    def poll_access_link_changes(self) -> dict[str, Any]:
        links_payload = self._resolve_access_links()
        fingerprint = str(links_payload.get("fingerprint") or "")

        if not fingerprint:
            return {
                "sent": False,
                "status": "invalid",
                "detail": "Access links fingerprint is empty.",
                "reason": "endpoint_change",
                "links": links_payload,
            }

        if not self._last_access_observed_fingerprint:
            self._last_access_observed_fingerprint = fingerprint
            return {
                "sent": False,
                "status": "baseline",
                "detail": "Initial access endpoint baseline captured.",
                "reason": "endpoint_change",
                "links": links_payload,
            }

        if fingerprint == self._last_access_observed_fingerprint:
            return {
                "sent": False,
                "status": "unchanged",
                "detail": "Access endpoint unchanged.",
                "reason": "endpoint_change",
                "links": links_payload,
            }

        self._last_access_observed_fingerprint = fingerprint

        if not self._access_link_notifications_enabled():
            return {
                "sent": False,
                "status": "disabled",
                "detail": "Endpoint changed but Telegram access link notifications are disabled.",
                "reason": "endpoint_change",
                "links": links_payload,
            }

        return self.send_access_links(
            reason="endpoint_change", force=False, links=links_payload
        )

    def _dispatch_telegram_fallback(self, alert_id: int | None, reason: str) -> None:
        if not self.telegram_notifier.enabled:
            store.create_notification_delivery_log(
                "telegram",
                "skipped",
                f"fallback reason={reason}; Telegram bot token/chat id not configured.",
                alert_id=alert_id,
            )
            return

        alert_payload = store.get_alert(alert_id) if alert_id else {}
        links_payload = self._resolve_access_links()
        text = self.telegram_notifier.format_alert_fallback_message(
            alert_payload or {}, reason, links_payload
        )
        ok, detail = self.telegram_notifier.send_message(text)

        store.create_notification_delivery_log(
            "telegram",
            "sent" if ok else "failed",
            f"fallback reason={reason}; {detail}",
            alert_id=alert_id,
        )

    def _is_face_snapshot_alert(self, alert: dict[str, Any]) -> bool:
        alert_type = str(alert.get("type") or "").upper()
        if alert_type not in {"AUTHORIZED_ENTRY", "INTRUDER"}:
            return False
        details = _safe_json(alert.get("details_json"))
        return isinstance(details.get("face"), dict)

    def _resolve_snapshot_file_path(self, snapshot_path: str | None) -> Path | None:
        raw = str(snapshot_path or "").strip()
        if not raw:
            return None

        try:
            path = Path(raw)
            resolved = (
                path.resolve()
                if path.is_absolute()
                else (self.settings.storage_root / raw.lstrip("/")).resolve()
            )
            storage_root = self.settings.storage_root.resolve()
            if resolved != storage_root and storage_root not in resolved.parents:
                return None
            if not resolved.exists() or not resolved.is_file():
                return None
            return resolved
        except Exception:
            return None

    def _snapshot_cooldown_key(self, alert: dict[str, Any]) -> str:
        source_node = str(alert.get("source_node") or "system").strip().lower()
        alert_type = str(alert.get("type") or "ALERT").strip().upper()
        return f"{source_node}:{alert_type}"

    def _should_suppress_snapshot(self, alert: dict[str, Any]) -> tuple[bool, float]:
        cooldown_seconds = float(self.telegram_snapshot_cooldown_seconds)
        if cooldown_seconds <= 0.0:
            return False, 0.0

        key = self._snapshot_cooldown_key(alert)
        now = time.time()
        last_sent_at = self._last_snapshot_sent_at_by_key.get(key)
        if last_sent_at is not None:
            elapsed = now - last_sent_at
            if elapsed < cooldown_seconds:
                return True, max(0.0, cooldown_seconds - elapsed)

        self._last_snapshot_sent_at_by_key[key] = now
        return False, 0.0

    def _dispatch_telegram_face_snapshot(self, alert: dict[str, Any]) -> None:
        alert_id = int(alert.get("id") or 0) or None
        details = _safe_json(alert.get("details_json"))
        alert_payload = {
            **alert,
            "details": details,
        }
        caption = self.telegram_notifier.format_face_snapshot_caption(alert_payload)

        suppressed, remaining_seconds = self._should_suppress_snapshot(alert)
        if suppressed:
            store.create_notification_delivery_log(
                "telegram",
                "suppressed",
                f"face_snapshot cooldown_active remaining={remaining_seconds:.1f}s",
                alert_id=alert_id,
            )
            return

        if not self.telegram_notifier.enabled:
            store.create_notification_delivery_log(
                "telegram",
                "skipped",
                "face_snapshot; Telegram bot token/chat id not configured.",
                alert_id=alert_id,
            )
            return

        snapshot_file = self._resolve_snapshot_file_path(alert.get("snapshot_path"))
        if snapshot_file is not None:
            ok, detail = self.telegram_notifier.send_photo(
                str(snapshot_file), caption=caption
            )
            if ok:
                store.create_notification_delivery_log(
                    "telegram",
                    "sent",
                    f"face_snapshot photo={snapshot_file.name}; {detail}",
                    alert_id=alert_id,
                )
                return

            fallback_ok, fallback_detail = self.telegram_notifier.send_message(caption)
            status = "sent" if fallback_ok else "failed"
            store.create_notification_delivery_log(
                "telegram",
                status,
                f"face_snapshot photo_failed={detail}; caption_fallback={fallback_detail}",
                alert_id=alert_id,
            )
            return

        ok, detail = self.telegram_notifier.send_message(caption)
        store.create_notification_delivery_log(
            "telegram",
            "sent" if ok else "failed",
            f"face_snapshot no_photo; {detail}",
            alert_id=alert_id,
        )

    def dispatch_alert_by_id(self, alert_id: int) -> None:
        alert = store.get_alert(alert_id)
        if not alert:
            return
        self.dispatch_alert(alert)

    def dispatch_alert(self, alert: dict[str, Any]) -> None:
        alert_id = int(alert.get("id") or 0) or None
        is_face_snapshot_alert = self._is_face_snapshot_alert(alert)
        if is_face_snapshot_alert:
            self._dispatch_telegram_face_snapshot(alert)

        devices = store.list_mobile_devices(enabled_only=True)
        if not devices:
            store.create_notification_delivery_log(
                "push",
                "skipped",
                "No active mobile devices registered.",
                alert_id=alert_id,
            )
            if not is_face_snapshot_alert:
                self._dispatch_telegram_fallback(alert_id, "no_mobile_devices")
            return

        if not self._mobile_push_enabled():
            store.create_notification_delivery_log(
                "push",
                "disabled",
                "Mobile push disabled by configuration.",
                alert_id=alert_id,
            )
            if not is_face_snapshot_alert:
                self._dispatch_telegram_fallback(alert_id, "push_disabled")
            return

        payload = self._build_push_payload(alert)
        any_sent = False
        any_fallback_enabled = False

        for device in devices:
            user_id = int(device.get("user_id") or 0)
            prefs = store.get_notification_prefs(user_id)
            if prefs.get("telegram_fallback_enabled"):
                any_fallback_enabled = True

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
                any_sent = True
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

        if not any_sent and any_fallback_enabled and not is_face_snapshot_alert:
            self._dispatch_telegram_fallback(
                alert_id, "all_push_attempts_failed_or_skipped"
            )
