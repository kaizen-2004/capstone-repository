from __future__ import annotations

import base64
import json
import re
import threading
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from ..db import store
from ..services.face_identity_service import FaceIdentityService


ARCFACE_SAMPLE_SOURCE_PREFIX = "arcface:"
FACE_MODEL_LABEL = "SCRFD + ArcFace"


class FaceService:
    def __init__(
        self,
        sample_root: Path,
        model_root: Path,
        cosine_threshold: float = 0.60,
        uncertain_threshold: float = 0.45,
        insightface_model_root: Path | str | None = None,
        det_size: tuple[int, int] = (640, 640),
        detect_score_threshold: float = 0.60,
        min_face_width: int = 60,
        min_face_height: int = 60,
        blur_threshold: float = 20.0,
    ) -> None:
        self.sample_root = sample_root
        self.model_root = model_root
        self.cosine_threshold = float(cosine_threshold)
        self.uncertain_threshold = float(uncertain_threshold)
        self.insightface_model_root = (
            Path(insightface_model_root)
            if insightface_model_root is not None
            else self.model_root / "insightface"
        )
        self.det_size = det_size
        self.detect_score_threshold = float(detect_score_threshold)
        self.min_face_width = int(min_face_width)
        self.min_face_height = int(min_face_height)
        self.blur_threshold = float(blur_threshold)

        self.raw_root = self.sample_root / "raw"
        self.proc_root = self.sample_root / "processed"
        self.templates_path = self.model_root / "arcface_embeddings.json"

        self.raw_root.mkdir(parents=True, exist_ok=True)
        self.proc_root.mkdir(parents=True, exist_ok=True)
        self.model_root.mkdir(parents=True, exist_ok=True)
        self.insightface_model_root.mkdir(parents=True, exist_ok=True)

        self._model_lock = threading.RLock()
        self._identity_service: FaceIdentityService | None = None
        self._model_error = ""

        self._templates: dict[str, list[np.ndarray]] = {}
        self._template_sample_counts: dict[str, int] = {}
        self._load_models()
        self._load_templates()

    def _safe_name(self, value: str) -> str:
        out = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip())
        return out.strip("_") or "face"

    def _decode_data_url(self, image_data_url: str) -> np.ndarray:
        if "," in image_data_url:
            image_data_url = image_data_url.split(",", 1)[1]
        raw = base64.b64decode(image_data_url)
        arr = np.frombuffer(raw, dtype=np.uint8)
        image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Invalid image payload")
        return image

    def _set_model_error(self, message: str) -> None:
        self._identity_service = None
        self._model_error = message.strip() or "face_models_unavailable"

    def _load_models(self) -> None:
        try:
            identity_service = FaceIdentityService(
                model_root=self.insightface_model_root,
                det_size=self.det_size,
                det_thresh=self.detect_score_threshold,
                authorized_threshold=self.cosine_threshold,
                uncertain_threshold=self.uncertain_threshold,
                min_face_width=self.min_face_width,
                min_face_height=self.min_face_height,
                blur_threshold=self.blur_threshold,
            )
        except Exception as exc:
            self._set_model_error(f"face_model_load_failed:{exc}")
            return

        self._identity_service = identity_service
        self._model_error = ""

    def _ensure_models_ready(self) -> bool:
        if self._identity_service is None:
            self._load_models()
        return self._identity_service is not None

    def _sync_runtime_thresholds(self, threshold: float | None = None) -> None:
        if self._identity_service is None:
            return
        effective_threshold = self.cosine_threshold if threshold is None else float(threshold)
        self._identity_service.authorized_threshold = max(-1.0, min(1.0, effective_threshold))
        self._identity_service.uncertain_threshold = max(-1.0, min(1.0, self.uncertain_threshold))
        self._identity_service.det_thresh = max(0.01, min(1.0, self.detect_score_threshold))

    def _load_templates(self) -> None:
        self._templates = {}
        self._template_sample_counts = {}
        if not self.templates_path.exists():
            return

        try:
            payload = json.loads(self.templates_path.read_text(encoding="utf-8"))
        except Exception:
            return
        if not isinstance(payload, dict):
            return
        if str(payload.get("model") or "") != FACE_MODEL_LABEL:
            return
        identities = payload.get("identities")
        if not isinstance(identities, dict):
            return

        templates: dict[str, list[np.ndarray]] = {}
        sample_counts: dict[str, int] = {}
        for raw_name, raw_meta in identities.items():
            name = str(raw_name).strip()
            if not name or not isinstance(raw_meta, dict):
                continue

            embeddings_raw = raw_meta.get("embeddings")
            if not isinstance(embeddings_raw, list):
                continue

            vectors: list[np.ndarray] = []
            for embedding_raw in embeddings_raw:
                if not isinstance(embedding_raw, list) or len(embedding_raw) == 0:
                    continue
                try:
                    vectors.append(self._normalize_feature(np.asarray(embedding_raw)))
                except Exception:
                    continue

            if not vectors:
                continue
            templates[name] = vectors
            sample_counts[name] = max(0, int(raw_meta.get("sample_count") or len(vectors)))

        self._templates = templates
        self._template_sample_counts = sample_counts

    def _save_templates(self) -> None:
        identities: dict[str, dict[str, Any]] = {}
        for name, vectors in self._templates.items():
            identities[name] = {
                "embeddings": [
                    [float(v) for v in vector.tolist()]
                    for vector in vectors
                ],
                "sample_count": int(self._template_sample_counts.get(name, len(vectors))),
            }
        payload = {
            "version": 2,
            "model": FACE_MODEL_LABEL,
            "metric": "cosine",
            "authorized_threshold": float(self.cosine_threshold),
            "uncertain_threshold": float(self.uncertain_threshold),
            "identities": identities,
        }
        self.templates_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def remove_identity(self, person_name: str) -> None:
        name = str(person_name or "").strip()
        if not name:
            return
        changed = False
        if name in self._templates:
            self._templates.pop(name, None)
            changed = True
        if name in self._template_sample_counts:
            self._template_sample_counts.pop(name, None)
            changed = True
        if changed:
            self._save_templates()

    @staticmethod
    def _quality_score(image_bgr: np.ndarray) -> float:
        if image_bgr is None or image_bgr.size == 0:
            return 0.0
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())

    @staticmethod
    def _normalize_feature(feature: np.ndarray) -> np.ndarray:
        vec = np.asarray(feature, dtype=np.float32).reshape(-1)
        norm = float(np.linalg.norm(vec))
        if norm <= 1e-8:
            raise ValueError("invalid_feature_norm")
        return vec / norm

    @staticmethod
    def _bbox_xyxy_to_xywh(
        bbox_raw: Any,
        image_shape: tuple[int, int, int] | tuple[int, int],
    ) -> tuple[int, int, int, int]:
        height = int(image_shape[0])
        width = int(image_shape[1])
        bbox = np.asarray(bbox_raw, dtype=np.float32).reshape(-1)
        if bbox.size < 4:
            return 0, 0, 1, 1

        x1, y1, x2, y2 = [float(value) for value in bbox[:4].tolist()]
        x1 = max(0.0, min(x1, max(0.0, float(width - 1))))
        y1 = max(0.0, min(y1, max(0.0, float(height - 1))))
        x2 = max(x1 + 1.0, min(x2, float(width)))
        y2 = max(y1 + 1.0, min(y2, float(height)))
        return (
            int(round(x1)),
            int(round(y1)),
            max(1, int(round(x2 - x1))),
            max(1, int(round(y2 - y1))),
        )

    @staticmethod
    def _bbox_xywh_to_xyxy(bbox: tuple[int, int, int, int]) -> list[int]:
        x, y, w, h = bbox
        return [int(x), int(y), int(x + w), int(y + h)]

    def _crop_xyxy(self, image_bgr: np.ndarray, bbox_raw: Any) -> np.ndarray:
        x, y, w, h = self._bbox_xyxy_to_xywh(bbox_raw, image_bgr.shape)
        crop = image_bgr[y : y + h, x : x + w]
        return crop if crop.size else image_bgr

    def _face_dir(self, person_name: str) -> Path:
        return self.proc_root / self._safe_name(person_name)

    def _raw_counterpart_path(self, sample_path: Path) -> Path | None:
        try:
            rel = sample_path.relative_to(self.proc_root)
        except ValueError:
            return None

        raw_path = (self.raw_root / rel).with_suffix(".jpg")
        return raw_path if raw_path.exists() else None

    def _arcface_samples(self, face_id: int) -> list[dict[str, Any]]:
        return [
            sample
            for sample in store.list_face_samples(face_id)
            if str(sample.get("source") or "").startswith(ARCFACE_SAMPLE_SOURCE_PREFIX)
        ]

    def capture_sample(
        self, person_name: str, image_data_url: str, source: str = "phone_upload"
    ) -> dict[str, Any]:
        person_name = person_name.strip()
        if not person_name:
            raise ValueError("name is required")
        if not self._ensure_models_ready():
            raise ValueError(self._model_error or "face_models_unavailable")

        face = store.get_face_by_name(person_name)
        if face is None:
            face = store.create_face(person_name, "")

        image_bgr = self._decode_data_url(image_data_url)
        assert self._identity_service is not None
        self._sync_runtime_thresholds()

        verdict = self._identity_service.recognize(image_bgr, {})
        face_status = str(verdict.get("face_status") or "")
        if face_status == "NO_FACE":
            raise ValueError("no_face_detected")
        if face_status == "FACE_UNCLEAR":
            raise ValueError("face_unclear")

        embedding = self._identity_service.get_embedding(image_bgr)
        if embedding is None:
            raise ValueError("face_embedding_failed")

        stamp = time.strftime("%Y%m%d_%H%M%S")
        safe = self._safe_name(person_name)
        raw_dir = self.raw_root / safe
        raw_dir.mkdir(parents=True, exist_ok=True)
        proc_dir = self._face_dir(person_name)
        proc_dir.mkdir(parents=True, exist_ok=True)

        bbox_xyxy = verdict.get("bbox_xyxy") or verdict.get("bbox") or []
        crop = self._crop_xyxy(image_bgr, bbox_xyxy)
        quality = self._quality_score(crop)

        raw_path = raw_dir / f"{stamp}.jpg"
        proc_path = proc_dir / f"{stamp}.png"
        cv2.imwrite(str(raw_path), image_bgr)
        cv2.imwrite(str(proc_path), crop)

        rel_path = str(proc_path.relative_to(self.sample_root.parent))
        store.add_face_sample(
            int(face["id"]),
            rel_path,
            f"{ARCFACE_SAMPLE_SOURCE_PREFIX}{source}",
            quality,
        )
        store.set_face_updated(int(face["id"]))
        return self.training_status(person_name)

    def training_status(
        self, person_name: str, min_required: int = 40, target: int = 40
    ) -> dict[str, Any]:
        person_name = person_name.strip()
        face = store.get_face_by_name(person_name)
        count = 0 if face is None else len(self._arcface_samples(int(face["id"])))
        return {
            "ok": True,
            "name": person_name,
            "count": count,
            "arcface_sample_count": count,
            "min_required": min_required,
            "target": target,
            "remaining": max(0, target - count),
            "ready": count >= min_required,
            "target_reached": count >= target,
            "model": FACE_MODEL_LABEL,
        }

    def train(self) -> tuple[bool, str]:
        if not self._ensure_models_ready():
            return False, self._model_error or "face_models_unavailable"

        assert self._identity_service is not None
        self._sync_runtime_thresholds()
        faces = store.list_faces()
        embeddings_by_name: dict[str, list[np.ndarray]] = {}

        for row in faces:
            face_id = int(row["id"])
            person_name = str(row["name"])
            samples = self._arcface_samples(face_id)[:120]
            if not samples:
                continue

            vectors: list[np.ndarray] = []
            for sample in samples:
                rel = Path(str(sample["image_path"]))
                abs_path = self.sample_root.parent / rel
                candidates: list[Path] = []
                raw_counterpart = self._raw_counterpart_path(abs_path)
                if raw_counterpart is not None:
                    candidates.append(raw_counterpart)
                candidates.append(abs_path)

                vec: np.ndarray | None = None
                for candidate_path in candidates:
                    if not candidate_path.exists():
                        continue
                    image = cv2.imread(str(candidate_path), cv2.IMREAD_COLOR)
                    if image is None:
                        continue
                    try:
                        vec = self._identity_service.get_embedding(image)
                        if vec is not None:
                            break
                    except Exception:
                        continue

                if vec is not None:
                    vectors.append(self._normalize_feature(vec))

            if vectors:
                embeddings_by_name[person_name] = vectors

        if not embeddings_by_name:
            self._templates = {}
            self._template_sample_counts = {}
            self._save_templates()
            return False, "Not enough ArcFace face samples to build embedding templates"

        self._templates = embeddings_by_name
        self._template_sample_counts = {
            person_name: len(vectors)
            for person_name, vectors in embeddings_by_name.items()
        }
        self._save_templates()
        return True, "ArcFace embedding templates trained"

    def _to_legacy_verdict(
        self,
        identity_result: dict[str, Any],
        image_bgr: np.ndarray,
        threshold: float | None = None,
    ) -> dict[str, Any]:
        status = str(identity_result.get("face_status") or "UNKNOWN_FACE")
        similarity = float(identity_result.get("similarity") or 0.0)
        effective_threshold = float(self.cosine_threshold if threshold is None else threshold)
        effective_threshold = max(-1.0, min(1.0, effective_threshold))
        bbox_xyxy = identity_result.get("bbox_xyxy") or identity_result.get("bbox")

        legacy_bbox: list[int] | None = None
        legacy_bbox_xyxy: list[int] | None = None
        if isinstance(bbox_xyxy, list) and len(bbox_xyxy) == 4:
            xywh = self._bbox_xyxy_to_xywh(bbox_xyxy, image_bgr.shape)
            legacy_bbox = [int(value) for value in xywh]
            legacy_bbox_xyxy = self._bbox_xywh_to_xyxy(xywh)

        authorized = status == "AUTHORIZED"
        face_present = status != "NO_FACE"
        if authorized:
            classification = "AUTHORIZED"
            result = "authorized"
            reason = "matched"
        elif status == "FACE_UNCLEAR":
            classification = "FACE_UNCLEAR"
            result = "unknown"
            reason = "face_unclear"
        elif status == "NO_FACE":
            classification = "NO-FACE"
            result = "unknown"
            reason = "no_face_detected"
        else:
            classification = "NON-AUTHORIZED"
            result = "unknown"
            reason = "below_threshold"

        verdict: dict[str, Any] = {
            "result": result,
            "classification": classification,
            "confidence": round(max(0.0, min(100.0, similarity * 100.0)), 2),
            "face_present": face_present,
            "reason": reason,
            "similarity": round(similarity, 6),
            "distance": round(1.0 - similarity, 6),
            "threshold": round(effective_threshold, 6),
            "detector_score": identity_result.get("detector_score", 0.0),
            "face_status": status,
            "recognized_name": identity_result.get("recognized_name"),
            "face_count": int(identity_result.get("face_count") or 0),
            "model": FACE_MODEL_LABEL,
        }
        if legacy_bbox is not None:
            verdict["bbox"] = legacy_bbox
            verdict["bbox_xyxy"] = legacy_bbox_xyxy
        if authorized:
            name = str(identity_result.get("recognized_name") or "")
            verdict["name"] = name
            verdict["best_match"] = name
        return verdict

    def classify_faces_with_bbox(
        self,
        image_bgr: np.ndarray,
        threshold: float | None = None,
        max_faces: int = 5,
    ) -> list[dict[str, Any]]:
        if not self._ensure_models_ready():
            return []

        assert self._identity_service is not None
        self._sync_runtime_thresholds(threshold)
        with self._model_lock:
            identity_results = self._identity_service.recognize_faces(
                image_bgr,
                self._templates,
                max_faces=max_faces,
            )
        return [
            self._to_legacy_verdict(result, image_bgr, threshold)
            for result in identity_results
        ]

    def classify_frame_with_bbox(
        self, image_bgr: np.ndarray, threshold: float | None = None
    ) -> dict[str, Any]:
        if not self._ensure_models_ready():
            return {
                "result": "unknown",
                "classification": "NON-AUTHORIZED",
                "confidence": 0.0,
                "face_present": False,
                "reason": self._model_error or "face_models_unavailable",
                "face_status": "NO_FACE",
                "recognized_name": None,
                "similarity": 0.0,
                "face_count": 0,
                "model": FACE_MODEL_LABEL,
            }

        assert self._identity_service is not None
        self._sync_runtime_thresholds(threshold)
        with self._model_lock:
            identity_result = self._identity_service.recognize(image_bgr, self._templates)
        return self._to_legacy_verdict(identity_result, image_bgr, threshold)

    def classify_frame(
        self, image_bgr: np.ndarray, threshold: float | None = None
    ) -> dict[str, Any]:
        verdict = self.classify_frame_with_bbox(image_bgr, threshold)
        verdict.pop("bbox", None)
        verdict.pop("bbox_xyxy", None)
        return verdict

    def model_status(self) -> dict[str, Any]:
        ready = self._identity_service is not None
        return {
            "loaded": bool(ready),
            "model": FACE_MODEL_LABEL,
            "model_name": "buffalo_l",
            "model_root": str(self.insightface_model_root),
            "local_model_dir": str(self.insightface_model_root / "models" / "buffalo_l"),
            "embeddings_path": str(self.templates_path),
            "error": "" if ready else (self._model_error or "face_models_unavailable"),
        }
