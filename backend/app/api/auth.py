from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse

from ..core.auth import SESSION_COOKIE, get_current_user
from ..core.security import random_token
from ..db import store
from ..schemas.api import (
    ChangePasswordRequest,
    LoginRequest,
    ResetPasswordWithRecoveryCodeRequest,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(payload: LoginRequest, request: Request, response: Response) -> dict:
    user = store.authenticate_user(payload.username.strip(), payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = random_token()
    store.create_session(user_id=int(user["id"]), token=token)
    settings = request.app.state.settings
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=int(settings.session_ttl_seconds),
        path="/",
    )
    return {
        "ok": True,
        "token": token,
        "expires_in_seconds": int(settings.session_ttl_seconds),
        "user": {"username": user["username"]},
    }


@router.post("/logout")
def logout(request: Request, response: Response) -> dict:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        store.delete_session(token)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(request: Request) -> dict:
    user = get_current_user(request)
    return {"ok": True, "authenticated": True, "user": {"username": user["username"]}}


@router.get("/mobile/webview-session")
def mobile_webview_session(
    request: Request,
    token: str = Query(min_length=8, max_length=512),
    next_path: str = Query(default="/dashboard/remote/mobile", alias="next"),
) -> Response:
    user = store.get_session_user(token.strip())
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    target = next_path.strip() or "/dashboard/remote/mobile"
    if not target.startswith("/"):
        target = "/dashboard/remote/mobile"

    response = RedirectResponse(url=target, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    settings = request.app.state.settings
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token.strip(),
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=int(settings.session_ttl_seconds),
        path="/",
    )
    return response


@router.post("/change-password")
def change_password(payload: ChangePasswordRequest, request: Request, response: Response) -> dict:
    user = get_current_user(request)
    auth_user = store.authenticate_user(user["username"], payload.current_password)
    if auth_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect")

    store.update_admin_password(int(user["id"]), payload.new_password)
    store.delete_sessions_for_user(int(user["id"]))
    token = random_token()
    store.create_session(user_id=int(user["id"]), token=token)
    settings = request.app.state.settings
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=int(settings.session_ttl_seconds),
        path="/",
    )
    return {"ok": True, "message": "Password updated."}


@router.post("/recovery-code/regenerate")
def regenerate_recovery_code(request: Request) -> dict:
    user = get_current_user(request)
    recovery_code = random_token()[:24]
    store.set_admin_recovery_code(int(user["id"]), recovery_code)
    return {
        "ok": True,
        "recovery_code": recovery_code,
        "message": "Save this recovery code now. It will not be shown again.",
    }


@router.post("/reset-password")
def reset_password_with_recovery_code(
    payload: ResetPasswordWithRecoveryCodeRequest,
) -> dict:
    user = store.get_single_admin_user()
    if user is None or payload.username.strip() != user["username"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not store.verify_admin_recovery_code(int(user["id"]), payload.recovery_code):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Recovery code is invalid")

    store.update_admin_password(int(user["id"]), payload.new_password)
    store.delete_sessions_for_user(int(user["id"]))
    return {"ok": True, "message": "Password reset successfully."}
