from __future__ import annotations

import math
import threading
from pathlib import Path
from typing import Any

import cv2
import numpy as np


class FireService:
    def __init__(
        self,
        *,
        enabled: bool = True,
        model_path: Path | str | None = None,
        threshold: float = 0.60,
        input_size: int = 224,
        fire_class_index: int = 0,
    ) -> None:
        self.enabled = bool(enabled)
        self.model_path = Path(model_path) if model_path is not None else Path()
        self.threshold = max(0.01, min(0.99, float(threshold)))
        self.input_size = max(64, min(640, int(input_size)))
        self._runtime_input_size = self.input_size
        self.fire_class_index = max(0, int(fire_class_index))

        self._lock = threading.Lock()
        self._net: Any | None = None
        self._model_error = ""
        self._load_model()

    def _set_model_error(self, message: str) -> None:
        self._net = None
        self._model_error = message.strip() or "fire_model_error"

    def _load_model(self) -> None:
        if not self.enabled:
            self._set_model_error("model_disabled")
            return

        if not self.model_path:
            self._set_model_error("missing_model_path")
            return

        if not self.model_path.exists():
            self._set_model_error(f"model_not_found:{self.model_path}")
            return

        suffix = self.model_path.suffix.lower()
        try:
            if suffix == ".onnx":
                net = cv2.dnn.readNet(str(self.model_path))
            elif suffix == ".pb":
                net = cv2.dnn.readNetFromTensorflow(str(self.model_path))
            else:
                self._set_model_error(
                    f"unsupported_model_format:{self.model_path.suffix or 'none'}"
                )
                return

            net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
            self._net = net
            self._model_error = ""
        except Exception as exc:
            self._set_model_error(f"model_load_failed:{exc}")

    @staticmethod
    def _softmax(logits: np.ndarray) -> np.ndarray:
        shifted = logits - float(np.max(logits))
        exps = np.exp(shifted)
        total = float(np.sum(exps))
        if total <= 0.0:
            raise ValueError("invalid_softmax_total")
        return exps / total

    def _fire_probability_from_output(self, output: Any) -> float:
        flat = np.asarray(output, dtype=np.float32).reshape(-1)
        if flat.size == 0:
            raise ValueError("empty_model_output")

        if flat.size == 1:
            raw = float(flat[0])
            if 0.0 <= raw <= 1.0:
                return raw
            return 1.0 / (1.0 + math.exp(-raw))

        probabilities: np.ndarray
        probs_like = (
            np.all(flat >= 0.0)
            and np.all(flat <= 1.0)
            and abs(float(np.sum(flat)) - 1.0) <= 0.15
        )
        if probs_like:
            total = float(np.sum(flat))
            if total <= 0.0:
                raise ValueError("invalid_probability_total")
            probabilities = flat / total
        else:
            probabilities = self._softmax(flat)

        class_index = min(self.fire_class_index, int(probabilities.size - 1))
        return float(probabilities[class_index])

    def _infer_fire_probability(self, frame_bgr: np.ndarray) -> float:
        if self._net is None:
            self._load_model()
        if self._net is None:
            raise RuntimeError(self._model_error or "fire_model_unavailable")

        candidate_sizes: list[int] = [int(self._runtime_input_size)]
        if 224 not in candidate_sizes:
            candidate_sizes.append(224)

        last_exc: Exception | None = None
        for candidate_size in candidate_sizes:
            blob = cv2.dnn.blobFromImage(
                frame_bgr,
                scalefactor=1.0,
                size=(candidate_size, candidate_size),
                mean=(0.0, 0.0, 0.0),
                swapRB=False,
                crop=False,
            )
            try:
                with self._lock:
                    self._net.setInput(blob)
                    output = self._net.forward()
                probability = self._fire_probability_from_output(output)
                self._runtime_input_size = candidate_size
                return max(0.0, min(1.0, probability))
            except Exception as exc:
                last_exc = exc
                continue

        if last_exc is None:
            raise RuntimeError("fire_inference_failed")
        raise last_exc

    @staticmethod
    def _localize_flame_bbox(frame_bgr: np.ndarray) -> tuple[int, int, int, int] | None:
        try:
            hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
            gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        except Exception:
            return None

        warm_low = np.array([0, 80, 120], dtype=np.uint8)
        warm_high = np.array([35, 255, 255], dtype=np.uint8)
        warm_mask = cv2.inRange(hsv, warm_low, warm_high)

        red_low = np.array([160, 80, 120], dtype=np.uint8)
        red_high = np.array([179, 255, 255], dtype=np.uint8)
        red_mask = cv2.inRange(hsv, red_low, red_high)

        bright_mask = cv2.inRange(gray, 160, 255)
        mask = cv2.bitwise_and(cv2.bitwise_or(warm_mask, red_mask), bright_mask)

        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        frame_area = float(frame_bgr.shape[0] * frame_bgr.shape[1])
        min_area = max(80.0, frame_area * 0.0008)

        best = None
        best_area = 0.0
        for contour in contours:
            area = float(cv2.contourArea(contour))
            if area < min_area:
                continue
            if area > best_area:
                best_area = area
                best = contour

        if best is None:
            return None

        x, y, w, h = cv2.boundingRect(best)
        return int(x), int(y), int(w), int(h)

    def detect_flame(self, frame_bgr: np.ndarray) -> dict[str, Any]:
        base_result: dict[str, Any] = {
            "flame": False,
            "confidence": 0.0,
            "score": 0.0,
            "threshold": round(self.threshold, 4),
            "detector": "firenet_opencv_dnn",
            "model_path": str(self.model_path),
            "model_loaded": self._net is not None,
            "fire_class_index": int(self.fire_class_index),
            "input_size": int(self._runtime_input_size),
        }

        if frame_bgr is None or not hasattr(frame_bgr, "size") or frame_bgr.size == 0:
            return {**base_result, "error": "invalid_frame"}

        try:
            score = self._infer_fire_probability(frame_bgr)
        except Exception as exc:
            return {
                **base_result,
                "error": str(exc),
                "model_loaded": self._net is not None,
            }

        flame = score >= self.threshold
        bbox_candidate = self._localize_flame_bbox(frame_bgr)
        return {
            **base_result,
            "flame": bool(flame),
            "confidence": round(score * 100.0, 2),
            "score": round(score, 5),
            "bbox": list(bbox_candidate) if (flame and bbox_candidate is not None) else [],
            "model_loaded": self._net is not None,
            "error": "",
        }
