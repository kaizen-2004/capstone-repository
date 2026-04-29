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
        self.smoke_class_index = 1 if self.fire_class_index == 0 else 0
        self._model_kind = "classifier"
        self._fire_min_box_area_ratio = 0.002
        self._fire_min_box_area_pixels = 700.0
        self._smoke_min_box_area_ratio = 0.01
        self._smoke_min_box_area_pixels = 1400.0
        self._smoke_max_box_area_ratio = 0.40
        self._smoke_confidence_floor = 0.65

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
                self._model_kind = "yolo_onnx"
            elif suffix == ".pb":
                net = cv2.dnn.readNetFromTensorflow(str(self.model_path))
                self._model_kind = "classifier"
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

    def _prepare_yolo_blob(
        self, frame_bgr: np.ndarray, candidate_size: int
    ) -> tuple[np.ndarray, float, float, float]:
        frame_h, frame_w = frame_bgr.shape[:2]
        if frame_h <= 0 or frame_w <= 0:
            raise ValueError("invalid_frame_shape")

        scale = min(
            float(candidate_size) / float(frame_w),
            float(candidate_size) / float(frame_h),
        )
        scaled_w = max(1, int(round(frame_w * scale)))
        scaled_h = max(1, int(round(frame_h * scale)))

        resized = cv2.resize(
            frame_bgr,
            (scaled_w, scaled_h),
            interpolation=cv2.INTER_LINEAR,
        )
        pad_w = candidate_size - scaled_w
        pad_h = candidate_size - scaled_h
        pad_left = max(0, pad_w // 2)
        pad_top = max(0, pad_h // 2)
        pad_right = max(0, pad_w - pad_left)
        pad_bottom = max(0, pad_h - pad_top)

        letterboxed = cv2.copyMakeBorder(
            resized,
            pad_top,
            pad_bottom,
            pad_left,
            pad_right,
            cv2.BORDER_CONSTANT,
            value=(114, 114, 114),
        )

        blob = cv2.dnn.blobFromImage(
            letterboxed,
            scalefactor=1.0 / 255.0,
            size=(candidate_size, candidate_size),
            mean=(0.0, 0.0, 0.0),
            swapRB=True,
            crop=False,
        )
        return blob, scale, float(pad_left), float(pad_top)

    @staticmethod
    def _decode_yolo_rows(output: Any) -> np.ndarray:
        rows = np.asarray(output, dtype=np.float32)
        if rows.size == 0:
            return np.empty((0, 0), dtype=np.float32)
        if rows.ndim == 3:
            rows = rows[0]
        if rows.ndim == 1:
            rows = rows.reshape(1, -1)
        if rows.ndim != 2:
            return np.empty((0, 0), dtype=np.float32)

        # Typical YOLO ONNX raw outputs are channels-first: (classes+4, N)
        if rows.shape[0] <= 16 and rows.shape[1] > rows.shape[0]:
            rows = rows.T
        return rows

    def _infer_yolo_detection(self, frame_bgr: np.ndarray) -> dict[str, Any] | None:
        if self._net is None:
            self._load_model()
        if self._net is None:
            raise RuntimeError(self._model_error or "fire_model_unavailable")

        frame_h, frame_w = frame_bgr.shape[:2]
        candidate_sizes: list[int] = [int(self._runtime_input_size)]
        if 640 not in candidate_sizes:
            candidate_sizes.append(640)
        if 224 not in candidate_sizes:
            candidate_sizes.append(224)

        last_exc: Exception | None = None
        for candidate_size in candidate_sizes:
            try:
                blob, scale, pad_left, pad_top = self._prepare_yolo_blob(
                    frame_bgr,
                    candidate_size,
                )
                with self._lock:
                    self._net.setInput(blob)
                    output = self._net.forward()
                rows = self._decode_yolo_rows(output)
                if rows.size == 0:
                    self._runtime_input_size = candidate_size
                    return None

                boxes: list[list[int]] = []
                scores: list[float] = []
                class_ids: list[int] = []
                for row in rows:
                    cols = int(row.shape[0])
                    if cols < 6:
                        continue

                    cx, cy, bw, bh = [float(v) for v in row[:4]]

                    if cols >= 7:
                        objectness = float(row[4])
                        class_scores = np.asarray(row[5:], dtype=np.float32)
                        class_id = int(np.argmax(class_scores))
                        confidence = float(objectness * float(class_scores[class_id]))
                    else:
                        class_scores = np.asarray(row[4:], dtype=np.float32)
                        class_id = int(np.argmax(class_scores))
                        confidence = float(class_scores[class_id])

                    if class_id != self.fire_class_index:
                        continue

                    if confidence < float(self.threshold):
                        continue

                    x1 = (cx - (bw / 2.0) - pad_left) / scale
                    y1 = (cy - (bh / 2.0) - pad_top) / scale
                    x2 = (cx + (bw / 2.0) - pad_left) / scale
                    y2 = (cy + (bh / 2.0) - pad_top) / scale

                    x1 = max(0.0, min(float(frame_w - 1), x1))
                    y1 = max(0.0, min(float(frame_h - 1), y1))
                    x2 = max(0.0, min(float(frame_w - 1), x2))
                    y2 = max(0.0, min(float(frame_h - 1), y2))

                    w = max(0, int(round(x2 - x1)))
                    h = max(0, int(round(y2 - y1)))
                    x = int(round(x1))
                    y = int(round(y1))
                    if w <= 1 or h <= 1:
                        continue

                    frame_area = float(frame_h * frame_w)
                    if class_id == self.fire_class_index:
                        frame_area = float(frame_h * frame_w)
                        min_fire_area = max(
                            float(self._fire_min_box_area_pixels),
                            frame_area * float(self._fire_min_box_area_ratio),
                        )
                        if float(w * h) < min_fire_area:
                            continue

                    boxes.append([x, y, w, h])
                    scores.append(confidence)
                    class_ids.append(class_id)
                if not boxes:
                    self._runtime_input_size = candidate_size
                    return None

                nms_indices = cv2.dnn.NMSBoxes(
                    bboxes=boxes,
                    scores=scores,
                    score_threshold=float(self.threshold),
                    nms_threshold=0.45,
                )
                if len(nms_indices) == 0:
                    self._runtime_input_size = candidate_size
                    return None

                best_index = -1
                best_score = -1.0
                for idx_value in np.array(nms_indices).reshape(-1):
                    idx = int(idx_value)
                    score = float(scores[idx])
                    if score > best_score:
                        best_score = score
                        best_index = idx

                if best_index < 0:
                    self._runtime_input_size = candidate_size
                    return None

                top_class_id = int(class_ids[best_index])
                self._runtime_input_size = candidate_size
                return {
                    "score": float(scores[best_index]),
                    "bbox": boxes[best_index],
                    "class_index": top_class_id,
                    "class_name": "fire",
                }
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
            "smoke_detected": False,
            "confidence": 0.0,
            "score": 0.0,
            "threshold": round(self.threshold, 4),
            "detector": "yolov8_onnx_opencv_dnn"
            if self._model_kind == "yolo_onnx"
            else "firenet_opencv_dnn",
            "model_path": str(self.model_path),
            "model_loaded": self._net is not None,
            "fire_class_index": int(self.fire_class_index),
            "detected_class": "none",
            "detected_class_index": -1,
            "input_size": int(self._runtime_input_size),
        }

        if frame_bgr is None or not hasattr(frame_bgr, "size") or frame_bgr.size == 0:
            return {**base_result, "error": "invalid_frame"}

        try:
            if self._model_kind == "yolo_onnx":
                top_detection = self._infer_yolo_detection(frame_bgr)
                if top_detection is None:
                    return {
                        **base_result,
                        "bbox": [],
                        "model_loaded": self._net is not None,
                        "error": "",
                    }

                score = float(top_detection.get("score") or 0.0)
                detected_class = str(top_detection.get("class_name") or "none").lower()
                class_index_raw = top_detection.get("class_index")
                detected_class_index = (
                    int(class_index_raw)
                    if isinstance(class_index_raw, (int, float, np.integer, np.floating))
                    else -1
                )
                if detected_class != "fire":
                    return {
                        **base_result,
                        "bbox": [],
                        "model_loaded": self._net is not None,
                        "error": "",
                    }
                bbox = top_detection.get("bbox")
                bbox_value = (
                    [int(value) for value in bbox]
                    if isinstance(bbox, list) and len(bbox) == 4
                    else []
                )
                flame = detected_class == "fire" and score >= self.threshold
                return {
                    **base_result,
                    "flame": bool(flame),
                    "smoke_detected": False,
                    "confidence": round(score * 100.0, 2),
                    "score": round(score, 5),
                    "bbox": bbox_value,
                    "detected_class": detected_class,
                    "detected_class_index": detected_class_index,
                    "model_loaded": self._net is not None,
                    "error": "",
                }

            score = self._infer_fire_probability(frame_bgr)
            flame = score >= self.threshold
            bbox_candidate = self._localize_flame_bbox(frame_bgr)
            return {
                **base_result,
                "flame": bool(flame),
                "confidence": round(score * 100.0, 2),
                "score": round(score, 5),
                "bbox": list(bbox_candidate) if (flame and bbox_candidate is not None) else [],
                "detected_class": "fire" if flame else "none",
                "detected_class_index": int(self.fire_class_index) if flame else -1,
                "model_loaded": self._net is not None,
                "error": "",
            }
        except Exception as exc:
            return {
                **base_result,
                "error": str(exc),
                "model_loaded": self._net is not None,
            }
