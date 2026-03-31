from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any

import httpx

from ..core.config import Settings


def _safe_text(value: Any, fallback: str = "") -> str:
    text = str(value or fallback).strip()
    return text


class TelegramNotifier:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.bot_token = settings.telegram_bot_token.strip()
        self.chat_id = settings.telegram_chat_id.strip()
        self._endpoint = (
            f"https://api.telegram.org/bot{self.bot_token}/sendMessage" if self.bot_token else ""
        )

    @property
    def enabled(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def format_access_links_message(self, links: dict[str, Any], reason: str) -> str:
        reason_map = {
            "startup": "Backend startup",
            "endpoint_change": "Network endpoint changed",
            "manual": "Manual send",
            "manual_test": "Manual test",
        }
        reason_label = reason_map.get(reason, reason.replace("_", " ").title())

        preferred = _safe_text(links.get("preferred_url"))
        tailscale = _safe_text(links.get("tailscale_url"))
        mdns_url = _safe_text(links.get("mdns_url"))
        lan_url = _safe_text(links.get("lan_url"))
        host_label = _safe_text(links.get("host_label"), "Windows host")

        lines = [
            "<b>Condo Monitoring Remote Access</b>",
            f"Reason: {html.escape(reason_label)}",
            f"Host: {html.escape(host_label)}",
            "",
        ]

        if preferred:
            lines.append(f"Preferred: <a href=\"{html.escape(preferred)}\">Open mobile dashboard</a>")
        if tailscale:
            lines.append(f"Tailscale: <a href=\"{html.escape(tailscale)}\">{html.escape(tailscale)}</a>")
        if mdns_url:
            lines.append(f"mDNS (LAN): <a href=\"{html.escape(mdns_url)}\">{html.escape(mdns_url)}</a>")
        if lan_url:
            lines.append(f"LAN fallback: <a href=\"{html.escape(lan_url)}\">{html.escape(lan_url)}</a>")

        lines.extend(
            [
                "",
                "Note: login is still required on this web interface.",
                f"Updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')}",
            ]
        )
        return "\n".join(lines)

    def format_alert_fallback_message(self, alert: dict[str, Any], reason: str, links: dict[str, Any]) -> str:
        severity = _safe_text(alert.get("severity"), "info").upper()
        title = _safe_text(alert.get("title"), _safe_text(alert.get("type"), "Alert"))
        location = _safe_text(alert.get("location"), "System")
        description = _safe_text(alert.get("description"), "Monitoring alert detected.")
        preferred = _safe_text(links.get("preferred_url"))

        lines = [
            f"<b>[{html.escape(severity)}] {html.escape(title)}</b>",
            f"Location: {html.escape(location)}",
            f"Detail: {html.escape(description)}",
            f"Fallback reason: {html.escape(reason)}",
        ]

        if preferred:
            lines.append(f"Open dashboard: <a href=\"{html.escape(preferred)}\">{html.escape(preferred)}</a>")

        lines.append(f"Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')}")
        return "\n".join(lines)

    def send_message(self, text: str, disable_web_page_preview: bool = True) -> tuple[bool, str]:
        if not self.enabled:
            return False, "Telegram bot token/chat id not configured."

        try:
            with httpx.Client(timeout=8.0) as client:
                response = client.post(
                    self._endpoint,
                    json={
                        "chat_id": self.chat_id,
                        "text": text,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": disable_web_page_preview,
                    },
                )

            if response.status_code >= 400:
                body = response.text.strip()
                return False, f"Telegram API HTTP {response.status_code}: {body[:280]}"

            payload = response.json() if response.content else {}
            if not bool(payload.get("ok")):
                return False, f"Telegram API returned ok=false: {payload}"

            return True, "Delivered through Telegram bot API."
        except Exception as exc:
            return False, f"Telegram delivery error: {exc}"
