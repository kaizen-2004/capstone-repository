from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status

from ..core.auth import SESSION_COOKIE, get_current_user
from ..core.security import random_token
from ..db import store
from ..schemas.api import LoginRequest

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(payload: LoginRequest, response: Response) -> dict:
    user = store.authenticate_user(payload.username.strip(), payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = random_token()
    store.create_session(user_id=int(user["id"]), token=token)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=60 * 60 * 12,
        path="/",
    )
    return {"ok": True, "user": {"username": user["username"]}}


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
