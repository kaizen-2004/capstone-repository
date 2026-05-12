from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np

try:
    from insightface.app import FaceAnalysis
except Exception as exc:  # pragma: no cover - exercised when dependency is absent.
    FaceAnalysis = None  # type: ignore[assignment]
    _FACE_ANALYSIS_IMPORT_ERROR = exc
else:
    _FACE_ANALYSIS_IMPORT_ERROR = None


class FaceIdentityService:
    def __init__(
        self,
        *,
        model_root: Path,
        model_name: str = "buffalo_l",
        det_size: tuple[int, int] = (640, 640),
        det_thresh: float = 0.60,
        authorized_threshold: float = 0.60,
        uncertain_threshold: float = 0.45,
        min_face_width: int = 60,
        min_face_height: int = 60,
        blur_threshold: float = 20.0,
    ) -> None:
        if FaceAnalysis is None:
            raise RuntimeError(f"insightface_unavailable:{_FACE_ANALYSIS_IMPORT_ERROR}")

        self.model_root = Path(model_root)
        self.model_name = model_name.strip() or "buffalo_l"
        self.local_model_dir = self.model_root / "models" / self.model_name
        self._validate_local_model_dir()

        self.app = FaceAnalysis(
            name=self.model_name,
            root=str(self.model_root),
            providers=["CPUExecutionProvider"],
        )

        self.app.prepare(
            ctx_id=0,
            det_size=det_size,
            det_thresh=float(det_thresh),
        )

        self.det_thresh = float(det_thresh)
        self.authorized_threshold = float(authorized_threshold)
        self.uncertain_threshold = float(uncertain_threshold)
        self.min_face_width = int(min_face_width)
        self.min_face_height = int(min_face_height)
        self.blur_threshold = float(blur_threshold)

    def _validate_local_model_dir(self) -> None:
        if not self.local_model_dir.exists() or not self.local_model_dir.is_dir():
            raise FileNotFoundError(f"insightface_model_not_found:{self.local_model_dir}")
        if not any(self.local_model_dir.glob("*.onnx")):
            raise FileNotFoundError(f"insightface_model_empty:{self.local_model_dir}")

    def detect_faces(self, frame: np.ndarray) -> list[Any]:
        if frame is None or frame.size == 0:
            return []
        return list(self.app.get(frame) or [])

    def get_embedding(self, frame: np.ndarray) -> np.ndarray | None:
        faces = self.detect_faces(frame)
        if not faces:
            return None

        face = self._select_largest_face(faces)
        if not self._is_good_quality_face(face, frame):
            return None

        return self._normalized_embedding(face)

    def recognize(
        self, frame: np.ndarray, enrolled_embeddings: dict[str, list[np.ndarray]]
    ) -> dict[str, Any]:
        verdicts = self.recognize_faces(frame, enrolled_embeddings, max_faces=1)
        if verdicts:
            return verdicts[0]
        return self._empty_result("NO_FACE", face_count=0)

    def recognize_faces(
        self,
        frame: np.ndarray,
        enrolled_embeddings: dict[str, list[np.ndarray]],
        max_faces: int = 5,
    ) -> list[dict[str, Any]]:
        faces = self.detect_faces(frame)
        if not faces:
            return []

        face_limit = max(1, min(20, int(max_faces)))
        ranked_faces = sorted(faces, key=self._face_area, reverse=True)
        face_count = len(faces)
        return [
            self._recognize_face(frame, face, enrolled_embeddings, face_count)
            for face in ranked_faces[:face_limit]
        ]

    def _recognize_face(
        self,
        frame: np.ndarray,
        face: Any,
        enrolled_embeddings: dict[str, list[np.ndarray]],
        face_count: int,
    ) -> dict[str, Any]:
        bbox = self._bbox_xyxy(face)
        if not self._is_good_quality_face(face, frame):
            return self._face_result(
                "FACE_UNCLEAR",
                None,
                0.0,
                face_count,
                bbox,
                face,
            )

        query_embedding = self._normalized_embedding(face)
        if query_embedding is None:
            return self._face_result(
                "FACE_UNCLEAR",
                None,
                0.0,
                face_count,
                bbox,
                face,
            )

        if not enrolled_embeddings:
            return self._face_result(
                "UNKNOWN_FACE",
                None,
                0.0,
                face_count,
                bbox,
                face,
            )

        best_name = None
        best_score = -1.0
        for name, embeddings in enrolled_embeddings.items():
            for known_embedding in embeddings:
                score = self._cosine_similarity(query_embedding, known_embedding)
                if score > best_score:
                    best_score = score
                    best_name = name

        if best_score >= self.authorized_threshold:
            status = "AUTHORIZED"
            recognized_name = best_name
        elif best_score >= self.uncertain_threshold:
            status = "FACE_UNCLEAR"
            recognized_name = None
        else:
            status = "UNKNOWN_FACE"
            recognized_name = None

        return self._face_result(
            status,
            recognized_name,
            best_score,
            face_count,
            bbox,
            face,
        )

    def _empty_result(self, status: str, face_count: int) -> dict[str, Any]:
        return {
            "face_status": status,
            "recognized_name": None,
            "similarity": 0.0,
            "face_count": int(face_count),
            "bbox": None,
            "bbox_xyxy": None,
            "model": "SCRFD + ArcFace",
        }

    def _face_result(
        self,
        status: str,
        recognized_name: str | None,
        similarity: float,
        face_count: int,
        bbox: list[float],
        face: Any,
    ) -> dict[str, Any]:
        return {
            "face_status": status,
            "recognized_name": recognized_name,
            "similarity": float(max(0.0, similarity)),
            "face_count": int(face_count),
            "bbox": bbox,
            "bbox_xyxy": bbox,
            "detector_score": round(float(getattr(face, "det_score", 0.0) or 0.0), 4),
            "model": "SCRFD + ArcFace",
        }

    def _select_largest_face(self, faces: list[Any]) -> Any:
        return max(faces, key=self._face_area)

    def _is_good_quality_face(self, face: Any, frame: np.ndarray | None = None) -> bool:
        x1, y1, x2, y2 = self._bbox_xyxy(face)
        width = x2 - x1
        height = y2 - y1

        if float(getattr(face, "det_score", 0.0) or 0.0) < self.det_thresh:
            return False
        if width < self.min_face_width or height < self.min_face_height:
            return False
        if frame is not None and self._blur_score(frame, [x1, y1, x2, y2]) < self.blur_threshold:
            return False
        return True

    def _normalized_embedding(self, face: Any) -> np.ndarray | None:
        embedding = getattr(face, "embedding", None)
        if embedding is None:
            return None
        vec = np.asarray(embedding, dtype=np.float32).reshape(-1)
        norm = float(np.linalg.norm(vec))
        if norm <= 1e-8:
            return None
        return vec / norm

    def _face_area(self, face: Any) -> float:
        x1, y1, x2, y2 = self._bbox_xyxy(face)
        return max(0.0, x2 - x1) * max(0.0, y2 - y1)

    def _bbox_xyxy(self, face: Any) -> list[float]:
        raw_bbox = getattr(face, "bbox", [0.0, 0.0, 0.0, 0.0])
        bbox = np.asarray(raw_bbox, dtype=np.float32).reshape(-1)
        if bbox.size < 4:
            return [0.0, 0.0, 0.0, 0.0]
        return [float(value) for value in bbox[:4].tolist()]

    def _blur_score(self, frame: np.ndarray, bbox: list[float]) -> float:
        height, width = frame.shape[:2]
        x1, y1, x2, y2 = [int(round(value)) for value in bbox]
        x1 = max(0, min(x1, max(0, width - 1)))
        y1 = max(0, min(y1, max(0, height - 1)))
        x2 = max(x1 + 1, min(x2, width))
        y2 = max(y1 + 1, min(y2, height))
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return 0.0
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        a = np.asarray(a, dtype=np.float32).reshape(-1)
        b = np.asarray(b, dtype=np.float32).reshape(-1)
        denom = np.linalg.norm(a) * np.linalg.norm(b)
        if denom == 0:
            return 0.0
        return float(np.dot(a, b) / denom)
