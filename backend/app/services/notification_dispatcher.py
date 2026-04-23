from __future__ import annotations

import html
import json
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, cast

import cv2

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

    def apply_runtime_setting(self, key: str, value: str) -> None:
        normalized_key = key.strip().upper()
        if normalized_key == "TELEGRAM_BOT_TOKEN":
            self.telegram_notifier.apply_credentials(value, self.telegram_notifier.chat_id)
            return
        if normalized_key == "TELEGRAM_CHAT_ID":
            self.telegram_notifier.apply_credentials(
                self.telegram_notifier.bot_token, value
            )
            return
        if normalized_key == "WEBPUSH_VAPID_PUBLIC_KEY":
            self.vapid_public_key = str(value or "").strip()
            return
        if normalized_key == "WEBPUSH_VAPID_PRIVATE_KEY":
            self.vapid_private_key = str(value or "").strip()
            return
        if normalized_key == "WEBPUSH_VAPID_SUBJECT":
            self.vapid_subject = str(value or "").strip() or "mailto:admin@localhost"
            return

    def _telegram_snapshot_cooldown_seconds(self) -> int:
        raw = store.get_setting("TELEGRAM_SNAPSHOT_COOLDOWN_SECONDS")
        if raw is None:
            return self.telegram_snapshot_cooldown_seconds
        try:
            parsed = int(str(raw).strip())
        except ValueError:
            return self.telegram_snapshot_cooldown_seconds
        return max(0, parsed)

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
        stored_value = store.get_setting("TELEGRAM_LINK_NOTIFICATIONS_ENABLED")
        if stored_value is not None:
            return _parse_bool(stored_value, default=True)
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

    def _is_snapshot_alert(self, alert: dict[str, Any]) -> bool:
        if self._is_face_snapshot_alert(alert):
            return True
        snapshot_path = str(alert.get("snapshot_path") or "").strip()
        return bool(snapshot_path)

    def _format_snapshot_caption(self, alert_payload: dict[str, Any]) -> str:
        details = (
            alert_payload.get("details")
            if isinstance(alert_payload.get("details"), dict)
            else {}
        )
        if isinstance(details.get("face"), dict):
            return self.telegram_notifier.format_face_snapshot_caption(alert_payload)

        severity = str(alert_payload.get("severity") or "info").upper()
        title = str(alert_payload.get("title") or alert_payload.get("type") or "Alert")
        location = str(alert_payload.get("location") or "System")
        source_node = str(alert_payload.get("source_node") or "system")

        raw_ts = str(alert_payload.get("ts") or "").strip()
        timestamp_label = raw_ts
        if raw_ts:
            normalized = raw_ts.replace("Z", "+00:00")
            try:
                dt = datetime.fromisoformat(normalized)
            except ValueError:
                timestamp_label = raw_ts
            else:
                timestamp_label = dt.astimezone(timezone.utc).strftime(
                    "%Y-%m-%d %H:%M:%SZ"
                )
        else:
            timestamp_label = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

        lines = [
            f"<b>[{html.escape(severity)}] {html.escape(title)}</b>",
            f"Location: {html.escape(location)}",
            f"Source Node: <code>{html.escape(source_node)}</code>",
            f"Timestamp: {html.escape(timestamp_label)}",
        ]
        return "\n".join(lines)

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

    @staticmethod
    def _face_overlays_from_alert_payload(
        alert_payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        details = (
            alert_payload.get("details")
            if isinstance(alert_payload.get("details"), dict)
            else {}
        )

        raw_faces = details.get("faces")
        face_rows: list[dict[str, Any]] = []
        if isinstance(raw_faces, list):
            face_rows.extend(item for item in raw_faces if isinstance(item, dict))

        single_face = details.get("face")
        if isinstance(single_face, dict):
            face_rows.append(single_face)

        overlays: list[dict[str, Any]] = []
        seen_boxes: set[tuple[int, int, int, int]] = set()

        for face in face_rows:
            bbox = face.get("bbox")
            if not (isinstance(bbox, list) and len(bbox) == 4):
                continue
            try:
                x, y, w, h = [int(float(value)) for value in bbox]
            except Exception:
                continue

            box_key = (x, y, w, h)
            if box_key in seen_boxes:
                continue
            seen_boxes.add(box_key)

            classification = str(face.get("classification") or "").strip().upper()
            if not classification:
                result = str(face.get("result") or "").strip().lower()
                classification = "AUTHORIZED" if result == "authorized" else "NON-AUTHORIZED"

            try:
                confidence = float(face.get("confidence") or 0.0)
            except Exception:
                confidence = 0.0

            label = f"{classification} {confidence:.1f}%"
            color = (50, 205, 50) if classification == "AUTHORIZED" else (0, 165, 255)

            overlays.append(
                {
                    "bbox": (x, y, w, h),
                    "label": label,
                    "color": color,
                }
            )

        return overlays

    def _build_annotated_snapshot(
        self, snapshot_file: Path, alert_payload: dict[str, Any]
    ) -> tuple[Path, Path | None]:
        overlays = self._face_overlays_from_alert_payload(alert_payload)
        if not overlays:
            return snapshot_file, None

        image = cv2.imread(str(snapshot_file), cv2.IMREAD_COLOR)
        if image is None:
            return snapshot_file, None

        frame_h, frame_w = image.shape[:2]
        for overlay in overlays:
            x, y, w, h = overlay["bbox"]
            color = overlay["color"]
            label = overlay["label"]

            x = max(0, min(x, max(0, frame_w - 1)))
            y = max(0, min(y, max(0, frame_h - 1)))
            w = max(1, min(w, max(1, frame_w - x)))
            h = max(1, min(h, max(1, frame_h - y)))

            cv2.rectangle(image, (x, y), (x + w, y + h), color, 2)
            text_x = max(4, x)
            text_y = max(20, y - 8)
            cv2.putText(
                image,
                label,
                (text_x, text_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                color,
                2,
                cv2.LINE_AA,
            )

        temp_root = self.settings.storage_root / "temp"
        temp_root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="wb",
            suffix=".jpg",
            prefix="telegram_bbox_",
            delete=False,
            dir=str(temp_root),
        ) as temp_file:
            temp_path = Path(temp_file.name)

        encoded_ok = cv2.imwrite(str(temp_path), image)
        if not encoded_ok:
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass
            return snapshot_file, None

        return temp_path, temp_path

    def _snapshot_cooldown_key(self, alert: dict[str, Any]) -> str:
        source_node = str(alert.get("source_node") or "system").strip().lower()
        alert_type = str(alert.get("type") or "ALERT").strip().upper()
        return f"{source_node}:{alert_type}"

    def _should_suppress_snapshot(self, alert: dict[str, Any]) -> tuple[bool, float]:
        cooldown_seconds = float(self._telegram_snapshot_cooldown_seconds())
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
        caption = self._format_snapshot_caption(alert_payload)

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
            send_file, cleanup_file = self._build_annotated_snapshot(
                snapshot_file, alert_payload
            )
            ok, detail = self.telegram_notifier.send_photo(
                str(send_file), caption=caption
            )
            if cleanup_file is not None:
                try:
                    cleanup_file.unlink(missing_ok=True)
                except Exception:
                    pass
            if ok:
                store.create_notification_delivery_log(
                    "telegram",
                    "sent",
                    f"face_snapshot photo={send_file.name}; {detail}",
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
        is_snapshot_alert = self._is_snapshot_alert(alert)
        if is_snapshot_alert:
            self._dispatch_telegram_face_snapshot(alert)

        devices = store.list_mobile_devices(enabled_only=True)
        if not devices:
            store.create_notification_delivery_log(
                "push",
                "skipped",
                "No active mobile devices registered.",
                alert_id=alert_id,
            )
            if not is_snapshot_alert:
                self._dispatch_telegram_fallback(alert_id, "no_mobile_devices")
            return

        if not self._mobile_push_enabled():
            store.create_notification_delivery_log(
                "push",
                "disabled",
                "Mobile push disabled by configuration.",
                alert_id=alert_id,
            )
            if not is_snapshot_alert:
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

        if not any_sent and any_fallback_enabled and not is_snapshot_alert:
            self._dispatch_telegram_fallback(
                alert_id, "all_push_attempts_failed_or_skipped"
            )
