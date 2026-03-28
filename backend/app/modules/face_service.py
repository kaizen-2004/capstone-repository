from __future__ import annotations

import base64
import json
import re
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from ..db import store


class FaceService:
    def __init__(self, sample_root: Path, model_root: Path) -> None:
        self.sample_root = sample_root
        self.model_root = model_root
        self.raw_root = self.sample_root / "raw"
        self.proc_root = self.sample_root / "processed"
        self.model_path = self.model_root / "lbph.yml"
        self.labels_path = self.model_root / "labels.json"

        self.raw_root.mkdir(parents=True, exist_ok=True)
        self.proc_root.mkdir(parents=True, exist_ok=True)
        self.model_root.mkdir(parents=True, exist_ok=True)

        self._cascade = cv2.CascadeClassifier(str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"))
        self._recognizer: Any | None = None
        self._label_to_name: dict[int, str] = {}
        self._load_model()

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

    def _extract_face(self, image_bgr: np.ndarray) -> tuple[np.ndarray, float]:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        faces = self._cascade.detectMultiScale(gray, scaleFactor=1.15, minNeighbors=5, minSize=(72, 72))
        if len(faces) == 0:
            raise ValueError("No face detected")
        x, y, w, h = max(faces, key=lambda item: item[2] * item[3])
        roi = gray[y : y + h, x : x + w]
        roi = cv2.equalizeHist(roi)
        roi = cv2.resize(roi, (120, 120), interpolation=cv2.INTER_AREA)
        quality = float(cv2.Laplacian(roi, cv2.CV_64F).var())
        if quality < 35.0:
            raise ValueError("Image too blurry")
        return roi, quality

    def _face_dir(self, person_name: str) -> Path:
        return self.proc_root / self._safe_name(person_name)

    def capture_sample(self, person_name: str, image_data_url: str, source: str = "phone_upload") -> dict[str, Any]:
        person_name = person_name.strip()
        if not person_name:
            raise ValueError("name is required")

        face = store.get_face_by_name(person_name)
        if face is None:
            face = store.create_face(person_name, "")

        image_bgr = self._decode_data_url(image_data_url)
        face_roi, quality = self._extract_face(image_bgr)

        stamp = time.strftime("%Y%m%d_%H%M%S")
        safe = self._safe_name(person_name)
        raw_dir = self.raw_root / safe
        raw_dir.mkdir(parents=True, exist_ok=True)
        proc_dir = self._face_dir(person_name)
        proc_dir.mkdir(parents=True, exist_ok=True)

        raw_path = raw_dir / f"{stamp}.jpg"
        proc_path = proc_dir / f"{stamp}.png"
        cv2.imwrite(str(raw_path), image_bgr)
        cv2.imwrite(str(proc_path), face_roi)

        rel_path = str(proc_path.relative_to(self.sample_root.parent))
        store.add_face_sample(int(face["id"]), rel_path, source, quality)
        store.set_face_updated(int(face["id"]))

        return self.training_status(person_name)

    def training_status(self, person_name: str, min_required: int = 8, target: int = 20) -> dict[str, Any]:
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
        faces = store.list_faces()
        images: list[np.ndarray] = []
        labels: list[int] = []
        label_to_name: dict[int, str] = {}

        next_label = 1
        for row in faces:
            face_id = int(row["id"])
            samples = store.list_face_samples(face_id)
            if not samples:
                continue
            label = next_label
            next_label += 1
            label_to_name[label] = str(row["name"])
            for sample in samples:
                rel = Path(str(sample["image_path"]))
                abs_path = self.sample_root.parent / rel
                if not abs_path.exists():
                    continue
                image = cv2.imread(str(abs_path), cv2.IMREAD_GRAYSCALE)
                if image is None:
                    continue
                image = cv2.resize(image, (120, 120), interpolation=cv2.INTER_AREA)
                images.append(image)
                labels.append(label)

        if len(images) < 2:
            return False, "Not enough face samples to train model"

        if not hasattr(cv2, "face") or not hasattr(cv2.face, "LBPHFaceRecognizer_create"):
            return False, "opencv-contrib-python with cv2.face is required"

        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.train(images, np.array(labels))
        recognizer.save(str(self.model_path))
        self.labels_path.write_text(json.dumps(label_to_name, indent=2), encoding="utf-8")

        self._recognizer = recognizer
        self._label_to_name = label_to_name
        return True, "Face model trained"

    def _load_model(self) -> None:
        if not self.model_path.exists() or not self.labels_path.exists():
            self._recognizer = None
            self._label_to_name = {}
            return
        if not hasattr(cv2, "face") or not hasattr(cv2.face, "LBPHFaceRecognizer_create"):
            self._recognizer = None
            self._label_to_name = {}
            return

        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.read(str(self.model_path))
        try:
            labels_raw = json.loads(self.labels_path.read_text(encoding="utf-8"))
        except Exception:
            labels_raw = {}
        self._recognizer = recognizer
        self._label_to_name = {int(k): str(v) for k, v in labels_raw.items()}

    def classify_frame(self, image_bgr: np.ndarray, threshold: float = 68.0) -> dict[str, Any]:
        if self._recognizer is None:
            self._load_model()
        if self._recognizer is None:
            return {"result": "unknown", "name": "Unknown", "confidence": 0.0, "reason": "model_not_trained"}

        try:
            roi, quality = self._extract_face(image_bgr)
        except Exception as exc:
            return {"result": "unknown", "name": "Unknown", "confidence": 0.0, "reason": str(exc)}

        label, distance = self._recognizer.predict(roi)
        name = self._label_to_name.get(int(label), "Unknown")
        confidence = max(0.0, min(100.0, 100.0 - float(distance)))
        authorized = distance <= float(threshold)
        return {
            "result": "authorized" if authorized else "unknown",
            "name": name if authorized else "Unknown",
            "confidence": confidence,
            "quality": quality,
            "distance": float(distance),
        }
