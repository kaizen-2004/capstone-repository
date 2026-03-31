from __future__ import annotations

import os

from fastapi import APIRouter, Request

from ..core.auth import get_current_user
from ..db import store
from ..schemas.api import (
    MobileDeviceRegisterRequest,
    MobileDeviceUnregisterRequest,
    MobileNotificationPreferencesRequest,
    MobileRemoteConfigRequest,
)

router = APIRouter(tags=["integrations"])

MOBILE_REMOTE_SETTING_KEY = "mobile_remote_enabled"
MOBILE_PUSH_SETTING_KEY = "mobile_push_enabled"
TELEGRAM_FALLBACK_SETTING_KEY = "mobile_telegram_fallback_enabled"
MOBILE_REMOTE_ROUTE = "/dashboard/remote/mobile"


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "enabled"}


def _mobile_remote_enabled() -> bool:
    stored_value = store.get_setting(MOBILE_REMOTE_SETTING_KEY)
    if stored_value is not None:
        return _parse_bool(stored_value, default=False)
    return _parse_bool(os.environ.get("ENABLE_MOBILE_REMOTE"), default=False)


def _mobile_push_enabled() -> bool:
    stored_value = store.get_setting(MOBILE_PUSH_SETTING_KEY)
    if stored_value is not None:
        return _parse_bool(stored_value, default=True)
    return _parse_bool(os.environ.get("ENABLE_MOBILE_PUSH"), default=True)


def _telegram_fallback_enabled() -> bool:
    stored_value = store.get_setting(TELEGRAM_FALLBACK_SETTING_KEY)
    if stored_value is not None:
        return _parse_bool(stored_value, default=True)
    return True


def _resolve_lan_base_url(request: Request) -> str:
    resolver = getattr(request.app.state, "link_resolver", None)
    if resolver:
        return resolver.resolve_lan_base_url(request=request)
    settings = request.app.state.settings
    if settings.lan_base_url:
        return settings.lan_base_url
    return f"{request.url.scheme}://{request.headers.get('host', '127.0.0.1:8765')}"


def _resolve_access_links_payload(request: Request) -> dict:
    resolver = getattr(request.app.state, "link_resolver", None)
    if resolver:
        return resolver.resolve_links(request=request).to_dict()
    return {
        "preferred_url": MOBILE_REMOTE_ROUTE,
        "tailscale_url": "",
        "lan_url": _resolve_lan_base_url(request),
        "mdns_url": "",
        "route": MOBILE_REMOTE_ROUTE,
        "host_label": "windows-host",
        "port": int(getattr(request.app.state.settings, "backend_port", 8765)),
        "fingerprint": "static-route-only",
    }


def _extract_base_url(url: str, route: str = MOBILE_REMOTE_ROUTE) -> str:
    text = (url or "").strip()
    if not text:
        return ""
    if text.endswith(route):
        return text[: -len(route)] or ""
    return text


@router.get("/api/integrations/telegram/status")
def telegram_status(request: Request) -> dict:
    get_current_user(request)
    dispatcher = getattr(request.app.state, "notification_dispatcher", None)
    notifier = getattr(dispatcher, "telegram_notifier", None)
    enabled = _telegram_fallback_enabled()
    configured = bool(notifier and notifier.enabled)
    return {
        "ok": True,
        "enabled": enabled,
        "configured": configured,
        "link_notifications_enabled": bool(request.app.state.settings.telegram_link_notifications_enabled),
        "phase": "phase_3",
        "detail": (
            "Telegram fallback and link notifications are active."
            if (enabled and configured)
            else "Telegram fallback is enabled but bot token/chat id is not configured."
            if enabled
            else "Telegram fallback is disabled."
        ),
    }


@router.post("/api/integrations/telegram/test")
def telegram_test(request: Request) -> dict:
    get_current_user(request)
    dispatcher = getattr(request.app.state, "notification_dispatcher", None)
    if dispatcher:
        result = dispatcher.send_access_links(reason="manual_test", force=True)
        return {
            "ok": True,
            "enabled": _telegram_fallback_enabled(),
            **result,
        }
    return {
        "ok": True,
        "enabled": _telegram_fallback_enabled(),
        "sent": False,
        "status": "unavailable",
        "detail": "Notification dispatcher is unavailable in app state.",
    }


@router.post("/api/integrations/telegram/send-access-link")
def telegram_send_access_link(request: Request) -> dict:
    get_current_user(request)
    dispatcher = getattr(request.app.state, "notification_dispatcher", None)
    if not dispatcher:
        return {
            "ok": False,
            "sent": False,
            "status": "unavailable",
            "detail": "Notification dispatcher is unavailable in app state.",
        }
    result = dispatcher.send_access_links(reason="manual", force=True)
    return {
        "ok": True,
        **result,
    }


@router.get("/api/remote/tailscale/status")
def tailscale_status(request: Request) -> dict:
    get_current_user(request)
    settings = request.app.state.settings
    enabled = bool(settings.tailscale_base_url)
    return {
        "ok": True,
        "enabled": enabled,
        "phase": "phase_3",
        "detail": (
            f"Tailscale remote route configured at {settings.tailscale_base_url}."
            if enabled
            else "Tailscale remote access is scaffolded and currently not configured."
        ),
    }


@router.get("/api/integrations/mdns/status")
def mdns_status(request: Request) -> dict:
    get_current_user(request)
    mdns = getattr(request.app.state, "mdns_publisher", None)
    if mdns:
        return mdns.status()
    return {
        "ok": False,
        "enabled": bool(request.app.state.settings.mdns_enabled),
        "available": False,
        "published": False,
        "service_name": request.app.state.settings.mdns_service_name,
        "hostname": "",
        "port": int(request.app.state.settings.backend_port),
        "bound_ip": "",
        "mdns_base_url": "",
        "detail": "mDNS publisher is unavailable in app state.",
    }


@router.get("/api/remote/access/links")
def remote_access_links(request: Request) -> dict:
    get_current_user(request)
    links = _resolve_access_links_payload(request)
    return {
        "ok": True,
        **links,
    }


@router.get("/api/remote/mobile/status")
def mobile_remote_status(request: Request) -> dict:
    get_current_user(request)
    enabled = _mobile_remote_enabled()
    dispatcher = getattr(request.app.state, "notification_dispatcher", None)
    return {
        "ok": True,
        "enabled": enabled,
        "phase": "phase_2",
        "route": MOBILE_REMOTE_ROUTE,
        "local_only": True,
        "push_available": bool(dispatcher and dispatcher.push_available),
        "push_enabled": _mobile_push_enabled(),
        "telegram_fallback_enabled": _telegram_fallback_enabled(),
        "detail": (
            "Mobile remote interface is enabled for local network session access."
            if enabled
            else "Mobile remote interface is scaffolded and disabled by default."
        ),
    }


@router.post("/api/remote/mobile/config")
def mobile_remote_config(payload: MobileRemoteConfigRequest, request: Request) -> dict:
    user = get_current_user(request)
    store.upsert_setting(MOBILE_REMOTE_SETTING_KEY, "true" if payload.enabled else "false")
    return {
        "ok": True,
        "enabled": payload.enabled,
        "updated_by": user["username"],
        "detail": "Mobile remote interface configuration updated.",
    }


@router.get("/api/mobile/bootstrap")
def mobile_bootstrap(request: Request) -> dict:
    user = get_current_user(request)
    settings = request.app.state.settings
    dispatcher = getattr(request.app.state, "notification_dispatcher", None)
    access_links = _resolve_access_links_payload(request)
    return {
        "ok": True,
        "user": {"username": user["username"]},
        "mobile_remote_enabled": _mobile_remote_enabled(),
        "route": MOBILE_REMOTE_ROUTE,
        "lan_base_url": _resolve_lan_base_url(request),
        "tailscale_base_url": settings.tailscale_base_url,
        "mdns_base_url": _extract_base_url(str(access_links.get("mdns_url", ""))),
        "preferred_base_url": _extract_base_url(str(access_links.get("preferred_url", ""))),
        "network_modes": ["auto", "lan", "tailscale"],
        "push_available": bool(dispatcher and dispatcher.push_available),
        "push_enabled": _mobile_push_enabled(),
        "telegram_fallback_enabled": _telegram_fallback_enabled(),
        "vapid_public_key": settings.webpush_vapid_public_key,
    }


@router.post("/api/mobile/device/register")
def register_mobile_device(payload: MobileDeviceRegisterRequest, request: Request) -> dict:
    user = get_current_user(request)
    normalized_mode = payload.network_mode.strip().lower()
    if normalized_mode not in {"auto", "lan", "tailscale"}:
        normalized_mode = "auto"
    row = store.upsert_mobile_device(
        user_id=int(user["id"]),
        device_id=payload.device_id,
        platform=payload.platform.strip().lower() or "web_pwa",
        network_mode=normalized_mode,
        push_token=payload.push_token,
        push_subscription=payload.push_subscription,
        enabled=True,
    )
    return {
        "ok": True,
        "device_id": str(row.get("device_id") or payload.device_id),
        "platform": str(row.get("platform") or payload.platform),
        "network_mode": str(row.get("network_mode") or normalized_mode),
        "enabled": bool(int(row.get("enabled") or 1)),
        "updated_ts": str(row.get("updated_ts") or ""),
    }


@router.post("/api/mobile/device/unregister")
def unregister_mobile_device(payload: MobileDeviceUnregisterRequest, request: Request) -> dict:
    user = get_current_user(request)
    disabled = store.disable_mobile_device(int(user["id"]), payload.device_id)
    return {
        "ok": True,
        "device_id": payload.device_id,
        "disabled": disabled,
    }


@router.get("/api/mobile/notifications/preferences")
def mobile_notification_preferences(request: Request) -> dict:
    user = get_current_user(request)
    prefs = store.get_notification_prefs(int(user["id"]))
    return {
        "ok": True,
        "push_enabled": prefs["push_enabled"],
        "telegram_fallback_enabled": prefs["telegram_fallback_enabled"],
        "quiet_hours": prefs["quiet_hours"],
        "updated_ts": prefs["updated_ts"],
    }


@router.post("/api/mobile/notifications/preferences")
def update_mobile_notification_preferences(payload: MobileNotificationPreferencesRequest, request: Request) -> dict:
    user = get_current_user(request)
    prefs = store.upsert_notification_prefs(
        int(user["id"]),
        push_enabled=payload.push_enabled,
        telegram_fallback_enabled=payload.telegram_fallback_enabled,
        quiet_hours=payload.quiet_hours,
    )
    if payload.telegram_fallback_enabled is not None:
        store.upsert_setting(
            TELEGRAM_FALLBACK_SETTING_KEY,
            "true" if payload.telegram_fallback_enabled else "false",
        )
    return {
        "ok": True,
        "push_enabled": prefs["push_enabled"],
        "telegram_fallback_enabled": prefs["telegram_fallback_enabled"],
        "quiet_hours": prefs["quiet_hours"],
        "updated_ts": prefs["updated_ts"],
    }
