from __future__ import annotations

from typing import Any

import cv2
import numpy as np


class FireService:
    def detect_flame(self, frame_bgr: np.ndarray) -> dict[str, Any]:
        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
        lower = np.array([0, 70, 120], dtype=np.uint8)
        upper = np.array([35, 255, 255], dtype=np.uint8)
        mask = cv2.inRange(hsv, lower, upper)

        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, kernel, iterations=1)

        ratio = float(np.count_nonzero(mask)) / float(mask.size) if mask.size > 0 else 0.0
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        largest_area = 0.0
        for contour in contours:
            area = float(cv2.contourArea(contour))
            if area > largest_area:
                largest_area = area

        flame = ratio >= 0.015 and largest_area >= 200.0
        confidence = min(100.0, max(0.0, (ratio * 1800.0) + (largest_area / 60.0)))

        return {
            "flame": bool(flame),
            "confidence": round(confidence, 2),
            "ratio": round(ratio, 5),
            "largest_area": round(largest_area, 2),
        }
