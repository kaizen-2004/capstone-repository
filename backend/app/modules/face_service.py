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


class FaceService:
    def __init__(
        self,
        sample_root: Path,
        model_root: Path,
        cosine_threshold: float = 0.52,
        detector_model_path: Path | str | None = None,
        recognizer_model_path: Path | str | None = None,
        detect_score_threshold: float = 0.90,
        detect_nms_threshold: float = 0.30,
        detect_top_k: int = 5000,
    ) -> None:
        self.sample_root = sample_root
        self.model_root = model_root
        self.cosine_threshold = float(cosine_threshold)
        self.detector_model_path = (
            Path(detector_model_path)
            if detector_model_path is not None
            else self.model_root / "face" / "face_detection_yunet_2023mar.onnx"
        )
        self.recognizer_model_path = (
            Path(recognizer_model_path)
            if recognizer_model_path is not None
            else self.model_root / "face" / "face_recognition_sface_2021dec.onnx"
        )
        self.detect_score_threshold = float(detect_score_threshold)
        self.detect_nms_threshold = float(detect_nms_threshold)
        self.detect_top_k = int(detect_top_k)

        self.raw_root = self.sample_root / "raw"
        self.proc_root = self.sample_root / "processed"
        self.templates_path = self.model_root / "sface_embeddings.json"

        self.raw_root.mkdir(parents=True, exist_ok=True)
        self.proc_root.mkdir(parents=True, exist_ok=True)
        self.model_root.mkdir(parents=True, exist_ok=True)
        self.detector_model_path.parent.mkdir(parents=True, exist_ok=True)
        self.recognizer_model_path.parent.mkdir(parents=True, exist_ok=True)

        self._model_lock = threading.RLock()
        self._detector: Any | None = None
        self._recognizer: Any | None = None
        self._model_error = ""

        self._templates: dict[str, np.ndarray] = {}
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
        self._detector = None
        self._recognizer = None
        self._model_error = message.strip() or "face_models_unavailable"

    def _load_models(self) -> None:
        if not self.detector_model_path.exists():
            self._set_model_error(f"detector_model_not_found:{self.detector_model_path}")
            return
        if not self.recognizer_model_path.exists():
            self._set_model_error(
                f"recognizer_model_not_found:{self.recognizer_model_path}"
            )
            return

        try:
            detector = cv2.FaceDetectorYN_create(
                str(self.detector_model_path),
                "",
                (320, 320),
                self.detect_score_threshold,
                self.detect_nms_threshold,
                self.detect_top_k,
            )
            recognizer = cv2.FaceRecognizerSF_create(
                str(self.recognizer_model_path), ""
            )
        except Exception as exc:
            self._set_model_error(f"face_model_load_failed:{exc}")
            return

        self._detector = detector
        self._recognizer = recognizer
        self._model_error = ""

    def _ensure_models_ready(self) -> bool:
        if self._detector is None or self._recognizer is None:
            self._load_models()
        return self._detector is not None and self._recognizer is not None

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
        identities = payload.get("identities")
        if not isinstance(identities, dict):
            return

        templates: dict[str, np.ndarray] = {}
        sample_counts: dict[str, int] = {}
        for raw_name, raw_meta in identities.items():
            name = str(raw_name).strip()
            if not name:
                continue

            vector_raw: Any
            sample_count = 0
            if isinstance(raw_meta, dict):
                vector_raw = raw_meta.get("embedding", raw_meta.get("centroid", []))
                sample_count = int(raw_meta.get("sample_count") or 0)
            else:
                vector_raw = raw_meta

            if not isinstance(vector_raw, list) or len(vector_raw) == 0:
                continue

            vec = np.asarray(vector_raw, dtype=np.float32).reshape(-1)
            norm = float(np.linalg.norm(vec))
            if norm <= 1e-8:
                continue
            vec = vec / norm
            templates[name] = vec
            sample_counts[name] = max(0, sample_count)

        self._templates = templates
        self._template_sample_counts = sample_counts

    def _save_templates(self) -> None:
        identities: dict[str, dict[str, Any]] = {}
        for name, vec in self._templates.items():
            identities[name] = {
                "embedding": [float(v) for v in vec.tolist()],
                "sample_count": int(self._template_sample_counts.get(name, 0)),
            }
        payload = {
            "version": 1,
            "metric": "cosine",
            "threshold": float(self.cosine_threshold),
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
    def _face_score(face_row: np.ndarray) -> float:
        if face_row.size < 15:
            return 0.0
        return float(face_row[14])

    @staticmethod
    def _bbox_from_face(
        face_row: np.ndarray, image_shape: tuple[int, int, int] | tuple[int, int]
    ) -> tuple[int, int, int, int]:
        height = int(image_shape[0])
        width = int(image_shape[1])

        x = int(round(float(face_row[0])))
        y = int(round(float(face_row[1])))
        w = int(round(float(face_row[2])))
        h = int(round(float(face_row[3])))

        x = max(0, min(x, max(0, width - 1)))
        y = max(0, min(y, max(0, height - 1)))
        w = max(1, min(w, max(1, width - x)))
        h = max(1, min(h, max(1, height - y)))
        return x, y, w, h

    @staticmethod
    def _quality_score(image_bgr: np.ndarray) -> float:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())

    @staticmethod
    def _normalize_feature(feature: np.ndarray) -> np.ndarray:
        vec = np.asarray(feature, dtype=np.float32).reshape(-1)
        norm = float(np.linalg.norm(vec))
        if norm <= 1e-8:
            raise ValueError("invalid_feature_norm")
        return vec / norm

    def _detect_faces(self, image_bgr: np.ndarray) -> list[np.ndarray]:
        if image_bgr is None or image_bgr.size == 0:
            return []
        if not self._ensure_models_ready():
            return []

        height, width = image_bgr.shape[:2]
        if width <= 0 or height <= 0:
            return []

        with self._model_lock:
            assert self._detector is not None
            self._detector.setInputSize((int(width), int(height)))
            _, faces = self._detector.detect(image_bgr)

        if faces is None:
            return []

        arr = np.asarray(faces, dtype=np.float32)
        if arr.size == 0:
            return []
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        return [row for row in arr if row.size >= 15]

    def _pick_primary_face(self, faces: list[np.ndarray]) -> np.ndarray | None:
        if not faces:
            return None

        def _rank(face_row: np.ndarray) -> tuple[float, float]:
            score = self._face_score(face_row)
            area = max(0.0, float(face_row[2]) * float(face_row[3]))
            return score, area

        return max(faces, key=_rank)

    def _align_face(self, image_bgr: np.ndarray, face_row: np.ndarray) -> np.ndarray:
        if not self._ensure_models_ready():
            raise ValueError(self._model_error or "face_models_unavailable")

        with self._model_lock:
            assert self._recognizer is not None
            aligned = self._recognizer.alignCrop(image_bgr, face_row)
        if aligned is None or aligned.size == 0:
            raise ValueError("face_alignment_failed")
        return aligned

    def _feature_from_aligned(self, aligned_bgr: np.ndarray) -> np.ndarray:
        if not self._ensure_models_ready():
            raise ValueError(self._model_error or "face_models_unavailable")

        with self._model_lock:
            assert self._recognizer is not None
            feature = self._recognizer.feature(aligned_bgr)
        return self._normalize_feature(feature)

    def _extract_primary_face(
        self, image_bgr: np.ndarray
    ) -> tuple[np.ndarray, float, tuple[int, int, int, int], float]:
        faces = self._detect_faces(image_bgr)
        primary = self._pick_primary_face(faces)
        if primary is None:
            raise ValueError("no_face_detected")

        aligned = self._align_face(image_bgr, primary)
        quality = self._quality_score(aligned)
        if quality < 20.0:
            raise ValueError("image_too_blurry")
        bbox = self._bbox_from_face(primary, image_bgr.shape)
        score = self._face_score(primary)
        return aligned, quality, bbox, score

    def _embedding_from_training_image(
        self, image_bgr: np.ndarray, *, allow_resize_fallback: bool = True
    ) -> np.ndarray:
        faces = self._detect_faces(image_bgr)
        primary = self._pick_primary_face(faces)

        if primary is not None:
            aligned = self._align_face(image_bgr, primary)
        else:
            if not allow_resize_fallback:
                raise ValueError("no_face_detected")
            if image_bgr is None or image_bgr.size == 0:
                raise ValueError("invalid_sample_image")
            aligned = cv2.resize(image_bgr, (112, 112), interpolation=cv2.INTER_AREA)

        return self._feature_from_aligned(aligned)

    def _raw_counterpart_path(self, sample_path: Path) -> Path | None:
        try:
            rel = sample_path.relative_to(self.proc_root)
        except ValueError:
            return None

        raw_path = (self.raw_root / rel).with_suffix(".jpg")
        return raw_path if raw_path.exists() else None

    def _face_dir(self, person_name: str) -> Path:
        return self.proc_root / self._safe_name(person_name)

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
        aligned, quality, _, _ = self._extract_primary_face(image_bgr)

        stamp = time.strftime("%Y%m%d_%H%M%S")
        safe = self._safe_name(person_name)
        raw_dir = self.raw_root / safe
        raw_dir.mkdir(parents=True, exist_ok=True)
        proc_dir = self._face_dir(person_name)
        proc_dir.mkdir(parents=True, exist_ok=True)

        raw_path = raw_dir / f"{stamp}.jpg"
        proc_path = proc_dir / f"{stamp}.png"
        cv2.imwrite(str(raw_path), image_bgr)
        cv2.imwrite(str(proc_path), aligned)

        rel_path = str(proc_path.relative_to(self.sample_root.parent))
        store.add_face_sample(int(face["id"]), rel_path, source, quality)
        store.set_face_updated(int(face["id"]))

        return self.training_status(person_name)

    def training_status(
        self, person_name: str, min_required: int = 40, target: int = 40
    ) -> dict[str, Any]:
        person_name = person_name.strip()
        face = store.get_face_by_name(person_name)
        if face is None:
            count = 0
        else:
            count = store.count_face_samples(int(face["id"]))

        return {
            "ok": True,
            "name": person_name,
            "count": count,
            "min_required": min_required,
            "target": target,
            "remaining": max(0, target - count),
            "ready": count >= min_required,
            "target_reached": count >= target,
        }

    def train(self) -> tuple[bool, str]:
        if not self._ensure_models_ready():
            return False, self._model_error or "face_models_unavailable"

        faces = store.list_faces()
        embeddings_by_name: dict[str, list[np.ndarray]] = {}

        for row in faces:
            face_id = int(row["id"])
            person_name = str(row["name"])
            samples = store.list_face_samples(face_id)
            samples = samples[:120]
            if not samples:
                continue

            vectors: list[np.ndarray] = []
            for sample in samples:
                rel = Path(str(sample["image_path"]))
                abs_path = self.sample_root.parent / rel
                if not abs_path.exists():
                    continue
                candidates: list[tuple[Path, bool]] = []
                raw_counterpart = self._raw_counterpart_path(abs_path)
                if raw_counterpart is not None:
                    candidates.append((raw_counterpart, False))
                candidates.append((abs_path, True))

                vec: np.ndarray | None = None
                for candidate_path, allow_resize_fallback in candidates:
                    image = cv2.imread(str(candidate_path), cv2.IMREAD_COLOR)
                    if image is None:
                        continue
                    try:
                        vec = self._embedding_from_training_image(
                            image,
                            allow_resize_fallback=allow_resize_fallback,
                        )
                        break
                    except Exception:
                        continue

                if vec is None:
                    continue
                vectors.append(vec)

            if vectors:
                embeddings_by_name[person_name] = vectors

        if not embeddings_by_name:
            self._templates = {}
            self._template_sample_counts = {}
            self._save_templates()
            return False, "Not enough face samples to build embedding templates"

        templates: dict[str, np.ndarray] = {}
        counts: dict[str, int] = {}

        for person_name, vectors in embeddings_by_name.items():
            matrix = np.stack(vectors, axis=0)
            centroid = np.mean(matrix, axis=0)
            try:
                centroid = self._normalize_feature(centroid)
            except Exception:
                continue
            templates[person_name] = centroid
            counts[person_name] = len(vectors)

        if not templates:
            return False, "Unable to compute stable embedding templates"

        self._templates = templates
        self._template_sample_counts = counts
        self._save_templates()
        return True, "Face embedding templates trained"

    def _best_match(
        self, query_vector: np.ndarray
    ) -> tuple[str, float] | tuple[None, None]:
        if not self._templates:
            return None, None

        best_name = ""
        best_score = -1.0
        for person_name, template in self._templates.items():
            score = float(np.dot(query_vector, template))
            if score > best_score:
                best_name = person_name
                best_score = score
        return best_name, best_score

    def _classify_face_row(
        self,
        image_bgr: np.ndarray,
        face_row: np.ndarray,
        threshold: float | None = None,
    ) -> dict[str, Any]:
        bbox = self._bbox_from_face(face_row, image_bgr.shape)
        detector_score = self._face_score(face_row)

        try:
            aligned = self._align_face(image_bgr, face_row)
            quality = self._quality_score(aligned)
            embedding = self._feature_from_aligned(aligned)
        except Exception as exc:
            return {
                "result": "unknown",
                "classification": "NON-AUTHORIZED",
                "confidence": 0.0,
                "face_present": True,
                "reason": str(exc),
                "bbox": list(bbox),
                "detector_score": round(detector_score, 4),
            }

        best_name, best_similarity = self._best_match(embedding)
        if best_name is None or best_similarity is None:
            return {
                "result": "unknown",
                "classification": "NON-AUTHORIZED",
                "confidence": 0.0,
                "face_present": True,
                "reason": "model_not_trained",
                "quality": quality,
                "bbox": list(bbox),
                "detector_score": round(detector_score, 4),
                "similarity": 0.0,
            }

        effective_threshold = float(
            self.cosine_threshold if threshold is None else threshold
        )
        effective_threshold = max(-1.0, min(1.0, effective_threshold))

        authorized = best_similarity >= effective_threshold
        confidence = max(0.0, min(100.0, best_similarity * 100.0))

        return {
            "result": "authorized" if authorized else "unknown",
            "classification": "AUTHORIZED" if authorized else "NON-AUTHORIZED",
            "confidence": round(confidence, 2),
            "face_present": True,
            "quality": quality,
            "similarity": round(float(best_similarity), 6),
            "distance": round(1.0 - float(best_similarity), 6),
            "threshold": round(effective_threshold, 6),
            "bbox": list(bbox),
            "detector_score": round(detector_score, 4),
            "name": best_name if authorized else "",
            "best_match": best_name,
            "reason": "matched" if authorized else "below_threshold",
        }

    def classify_faces_with_bbox(
        self,
        image_bgr: np.ndarray,
        threshold: float | None = None,
        max_faces: int = 5,
    ) -> list[dict[str, Any]]:
        if not self._ensure_models_ready():
            return []

        faces = self._detect_faces(image_bgr)
        if not faces:
            return []

        face_limit = max(1, min(20, int(max_faces)))

        def _rank(face_row: np.ndarray) -> tuple[float, float]:
            score = self._face_score(face_row)
            area = max(0.0, float(face_row[2]) * float(face_row[3]))
            return score, area

        ranked_faces = sorted(faces, key=_rank, reverse=True)
        return [
            self._classify_face_row(image_bgr, row, threshold)
            for row in ranked_faces[:face_limit]
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
            }

        faces = self._detect_faces(image_bgr)
        primary = self._pick_primary_face(faces)
        if primary is None:
            return {
                "result": "unknown",
                "classification": "NO-FACE",
                "confidence": 0.0,
                "face_present": False,
                "reason": "no_face_detected",
            }
        return self._classify_face_row(image_bgr, primary, threshold)

    def classify_frame(
        self, image_bgr: np.ndarray, threshold: float | None = None
    ) -> dict[str, Any]:
        verdict = self.classify_frame_with_bbox(image_bgr, threshold)
        verdict.pop("bbox", None)
        return verdict

    def model_status(self) -> dict[str, Any]:
        ready = self._detector is not None and self._recognizer is not None
        return {
            "loaded": bool(ready),
            "detector_model_path": str(self.detector_model_path),
            "recognizer_model_path": str(self.recognizer_model_path),
            "error": "" if ready else (self._model_error or "face_models_unavailable"),
        }
