from __future__ import annotations

from fastapi import APIRouter, Request

from ..core.auth import get_current_user

router = APIRouter(tags=["integrations"])


@router.get("/api/integrations/telegram/status")
def telegram_status(request: Request) -> dict:
    get_current_user(request)
    return {
        "ok": True,
        "enabled": False,
        "phase": "phase_2",
        "detail": "Telegram integration is scaffolded and disabled until enabled in enhancement phase.",
    }


@router.post("/api/integrations/telegram/test")
def telegram_test(request: Request) -> dict:
    get_current_user(request)
    return {
        "ok": False,
        "enabled": False,
        "detail": "Telegram test is unavailable while integration is disabled.",
    }


@router.get("/api/remote/tailscale/status")
def tailscale_status(request: Request) -> dict:
    get_current_user(request)
    return {
        "ok": True,
        "enabled": False,
        "phase": "phase_3",
        "detail": "Tailscale remote access is scaffolded and disabled in core phase.",
    }
