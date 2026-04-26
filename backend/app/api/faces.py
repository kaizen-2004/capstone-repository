from __future__ import annotations

import base64
import re

import cv2
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from ..core.auth import get_current_user
from ..db import store
from ..schemas.api import (
    CaptureFaceFromNodeRequest,
    CaptureFaceRequest,
    CreateFaceRequest,
    EnrollCompleteRequest,
    EnrollStartRequest,
    UpdateFaceRequest,
)

router = APIRouter(tags=["faces"])

ENROLL_MIN_REQUIRED_SAMPLES = 40
ENROLL_TARGET_SAMPLES = 40


def _resolved_image_content_type(content_type: str, filename: str) -> str:
    resolved = str(content_type or "").strip().lower()
    if resolved.startswith("image/"):
        return resolved

    name = str(filename or "").strip().lower()
    if name.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if name.endswith(".png"):
        return "image/png"
    if name.endswith(".webp"):
        return "image/webp"
    if name.endswith(".bmp"):
        return "image/bmp"

    return resolved


def _guess_image_content_type(file_bytes: bytes) -> str:
    if file_bytes.startswith(b"\xFF\xD8\xFF"):
        return "image/jpeg"
    if file_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(file_bytes) >= 12 and file_bytes[:4] == b"RIFF" and file_bytes[8:12] == b"WEBP":
        return "image/webp"
    if file_bytes.startswith(b"BM"):
        return "image/bmp"
    return ""


def _enroll_user_code_key(user_code: str) -> str:
    return f"mobile_enroll_user_code:{user_code.strip().lower()}"


def _resolve_enroll_id(enroll_id: str | None, user_code: str | None) -> str:
    enroll_id_value = str(enroll_id or "").strip()
    if enroll_id_value:
        return enroll_id_value

    user_code_value = str(user_code or "").strip()
    if not user_code_value:
        raise ValueError("enroll_id or user_code is required")

    mapped = store.get_setting(_enroll_user_code_key(user_code_value))
    if mapped:
        return str(mapped).strip()
    return user_code_value


def _encode_enroll_id(face_id: int) -> str:
    return f"enroll-face-{int(face_id)}"


def _decode_enroll_id(enroll_id: str) -> int:
    match = re.fullmatch(r"enroll-face-(\d+)", enroll_id.strip())
    if not match:
        raise ValueError("invalid enroll_id")
    return int(match.group(1))


def _face_to_profile(row: dict) -> dict:
    note = str(row.get("note") or "").strip()
    return {
        "id": f"auth-{int(row['id']):03d}",
        "db_id": int(row["id"]),
        "label": str(row["name"]),
        "role": note or "Authorized",
        "note": note,
        "enrolled_at": str(row["created_ts"]),
        "sample_count": int(row.get("sample_count", 0)),
    }


@router.post("/api/enroll/start")
def enroll_start(payload: EnrollStartRequest, request: Request) -> dict:
    get_current_user(request)
    name = str(payload.name or payload.full_name or payload.user_code or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    user_code = str(payload.user_code or "").strip()

    face = store.get_face_by_name(name)
    if face is None:
        face = store.create_face(name=name, note=payload.role.strip())

    enroll_id = _encode_enroll_id(int(face["id"]))
    if user_code:
        store.upsert_setting(_enroll_user_code_key(user_code), enroll_id)

    status = request.app.state.face_service.training_status(
        name,
        min_required=ENROLL_MIN_REQUIRED_SAMPLES,
        target=ENROLL_TARGET_SAMPLES,
    )
    return {
        "ok": True,
        "enroll_id": enroll_id,
        "user_code": user_code,
        "face_id": int(face["id"]),
        "name": name,
        "role": payload.role.strip() or "Authorized",
        "capture_source": payload.capture_source.strip() or "mobile_app",
        **status,
    }


@router.post("/api/enroll/upload")
async def enroll_upload(
    request: Request,
    enroll_id: str = Form(""),
    user_code: str = Form(""),
    capture_source: str = Form("mobile_app"),
    sample_index: str = Form(""),
    timestamp: str = Form(""),
    image: UploadFile = File(...),
) -> dict:
    get_current_user(request)

    try:
        resolved_enroll_id = _resolve_enroll_id(enroll_id, user_code)
        face_id = _decode_enroll_id(resolved_enroll_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    face = store.get_face(face_id)
    if face is None:
        raise HTTPException(status_code=404, detail="enrollment profile not found")

    file_bytes = await image.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="empty image payload")

    content_type = _resolved_image_content_type(
        image.content_type or "",
        image.filename or "",
    )
    if not content_type.startswith("image/"):
        guessed = _guess_image_content_type(file_bytes)
        if not guessed.startswith("image/"):
            raise HTTPException(status_code=400, detail="image file is required")
        content_type = guessed

    b64 = base64.b64encode(file_bytes).decode("ascii")
    image_data_url = f"data:{content_type};base64,{b64}"

    try:
        status = request.app.state.face_service.capture_sample(
            str(face.get("name") or ""),
            image_data_url,
            source=f"mobile_enroll:{capture_source.strip() or 'mobile_app'}",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "ok": True,
        "enroll_id": resolved_enroll_id,
        "user_code": user_code.strip(),
        "capture_source": capture_source.strip() or "mobile_app",
        "sample_index": sample_index.strip(),
        "timestamp": timestamp.strip(),
        **status,
    }


@router.post("/api/enroll/complete")
def enroll_complete(payload: EnrollCompleteRequest, request: Request) -> dict:
    get_current_user(request)

    try:
        resolved_enroll_id = _resolve_enroll_id(payload.enroll_id, payload.user_code)
        face_id = _decode_enroll_id(resolved_enroll_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    face = store.get_face(face_id)
    if face is None:
        raise HTTPException(status_code=404, detail="enrollment profile not found")

    name = str(face.get("name") or "").strip()
    status = request.app.state.face_service.training_status(
        name,
        min_required=ENROLL_MIN_REQUIRED_SAMPLES,
        target=ENROLL_TARGET_SAMPLES,
    )
    if not bool(status.get("ready")):
        raise HTTPException(
            status_code=400,
            detail=f"minimum samples not met; remaining={int(status.get('remaining') or 0)}",
        )

    trained = True
    message = "enrollment completed"
    if payload.trigger_train:
        trained, message = request.app.state.face_service.train()

    return {
        "ok": bool(trained),
        "enroll_id": resolved_enroll_id,
        "user_code": str(payload.user_code or "").strip(),
        "trained": bool(trained),
        "message": message,
        "profile": _face_to_profile({**face, "sample_count": int(status.get("count") or 0)}),
        "status": status,
    }


@router.get("/api/faces")
def list_faces(request: Request) -> dict:
    get_current_user(request)
    faces = store.list_faces()
    return {"ok": True, "faces": [_face_to_profile(row) for row in faces]}


@router.post("/api/faces")
def create_face(payload: CreateFaceRequest, request: Request) -> dict:
    get_current_user(request)
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    existing = store.get_face_by_name(name)
    if existing is not None:
        return {"ok": True, "face": _face_to_profile(existing)}
    row = store.create_face(name=name, note=payload.note.strip())
    row["sample_count"] = 0
    return {"ok": True, "face": _face_to_profile(row)}


@router.delete("/api/faces/{face_id}")
def delete_face(face_id: int, request: Request) -> dict:
    get_current_user(request)
    face = store.get_face(face_id)
    if face is None:
        raise HTTPException(status_code=404, detail="face not found")

    if not store.delete_face(face_id):
        raise HTTPException(status_code=404, detail="face not found")

    face_service = request.app.state.face_service
    face_service.remove_identity(str(face.get("name") or ""))

    return {"ok": True}


@router.patch("/api/faces/{face_id}")
def update_face(face_id: int, payload: UpdateFaceRequest, request: Request) -> dict:
    get_current_user(request)
    existing = store.get_face(face_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="face not found")

    next_name: str | None = None
    next_note: str | None = None

    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="name is required")
        duplicate = store.get_face_by_name(name)
        if duplicate is not None and int(duplicate["id"]) != int(face_id):
            raise HTTPException(status_code=400, detail="name already exists")
        next_name = name

    if payload.note is not None:
        next_note = payload.note.strip()

    if next_name is None and next_note is None:
        raise HTTPException(status_code=400, detail="nothing to update")

    updated = store.update_face(face_id, name=next_name, note=next_note)
    if updated is None:
        raise HTTPException(status_code=404, detail="face not found")

    face_service = request.app.state.face_service
    try:
        face_service.train()
    except Exception:
        pass

    status = face_service.training_status(str(updated.get("name") or ""))
    updated_with_status = {
        **updated,
        "sample_count": int(status.get("count") or 0),
    }
    return {"ok": True, "face": _face_to_profile(updated_with_status)}


@router.get("/api/training/face/status")
def face_status(name: str, request: Request) -> dict:
    get_current_user(request)
    return request.app.state.face_service.training_status(name)


@router.post("/api/training/face/capture")
def face_capture(payload: CaptureFaceRequest, request: Request) -> dict:
    get_current_user(request)
    try:
        status = request.app.state.face_service.capture_sample(payload.name, payload.image, source="phone_upload")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return status


@router.post("/api/training/face/capture-node")
def face_capture_from_node(payload: CaptureFaceFromNodeRequest, request: Request) -> dict:
    get_current_user(request)
    node_id = str(payload.node_id or "").strip().lower()
    if not node_id:
        raise HTTPException(status_code=400, detail="node_id is required")

    frame = request.app.state.camera_manager.snapshot_frame(node_id)
    if frame is None:
        raise HTTPException(status_code=404, detail="camera frame unavailable")

    ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
    if not ok:
        raise HTTPException(status_code=500, detail="failed to encode camera frame")

    image_data = base64.b64encode(encoded.tobytes()).decode("ascii")
    image_data_url = f"data:image/jpeg;base64,{image_data}"

    try:
        status = request.app.state.face_service.capture_sample(
            payload.name,
            image_data_url,
            source=f"camera_node:{node_id}",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return status


@router.post("/api/faces/enroll/upload")
def face_enroll_upload(payload: CaptureFaceRequest, request: Request) -> dict:
    get_current_user(request)
    try:
        status = request.app.state.face_service.capture_sample(payload.name, payload.image, source="mobile_enroll")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, **status}


@router.post("/api/training/face/train")
def face_train(request: Request) -> dict:
    get_current_user(request)
    ok, message = request.app.state.face_service.train()
    return {"ok": ok, "message": message}


@router.post("/api/faces/enrich/start")
def face_enrich_start(request: Request) -> dict:
    get_current_user(request)
    return {"ok": True, "enabled": False, "detail": "Camera enrichment trigger is scaffolded and disabled by default."}


@router.post("/api/faces/enrich/stop")
def face_enrich_stop(request: Request) -> dict:
    get_current_user(request)
    return {"ok": True, "enabled": False, "detail": "Camera enrichment trigger is scaffolded and disabled by default."}
