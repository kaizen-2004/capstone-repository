from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..core.auth import get_current_user
from ..db import store
from ..schemas.api import CaptureFaceRequest, CreateFaceRequest

router = APIRouter(tags=["faces"])


def _face_to_profile(row: dict) -> dict:
    return {
        "id": f"auth-{int(row['id']):03d}",
        "db_id": int(row["id"]),
        "label": str(row["name"]),
        "role": "Authorized",
        "enrolled_at": str(row["created_ts"]),
        "sample_count": int(row.get("sample_count", 0)),
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
    if not store.delete_face(face_id):
        raise HTTPException(status_code=404, detail="face not found")
    return {"ok": True}


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
