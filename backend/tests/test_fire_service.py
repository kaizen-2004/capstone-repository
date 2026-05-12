import numpy as np

from backend.app.modules.fire_service import FireService


def _dummy_frame() -> np.ndarray:
    return np.zeros((120, 160, 3), dtype=np.uint8)


def _fire_like_frame() -> np.ndarray:
    frame = _dummy_frame()
    frame[14:50, 10:54] = np.array([0, 80, 220], dtype=np.uint8)
    frame[20:42, 24:42] = np.array([0, 220, 255], dtype=np.uint8)
    frame[26:36, 30:38] = np.array([240, 240, 240], dtype=np.uint8)
    return frame


class _FakeNet:
    def __init__(self, output: np.ndarray) -> None:
        self.output = output

    def setInput(self, _blob: np.ndarray) -> None:
        pass

    def forward(self) -> np.ndarray:
        return self.output


def _yolo_output(
    *detections: tuple[float, float, float, float, float, float],
) -> np.ndarray:
    output = np.zeros((1, 6, 8400), dtype=np.float32)
    for index, detection in enumerate(detections):
        output[0, :, index] = np.asarray(detection, dtype=np.float32)
    return output


def test_detect_flame_yolo_fire_triggers_flame(monkeypatch) -> None:
    service = FireService(enabled=False)
    service._model_kind = "yolo_onnx"
    service.threshold = 0.5

    monkeypatch.setattr(
        service,
        "_infer_yolo_detection",
        lambda _frame: {
            "score": 0.91,
            "bbox": [10, 14, 44, 36],
            "class_index": 0,
            "class_name": "fire",
        },
    )

    result = service.detect_flame(_dummy_frame())

    assert result["flame"] is True
    assert result["smoke_detected"] is False
    assert result["detected_class"] == "fire"
    assert result["detected_class_index"] == 0
    assert result["bbox"] == [10, 14, 44, 36]
    assert float(result["score"]) >= 0.9


def test_detect_flame_yolo_smoke_is_reported(monkeypatch) -> None:
    service = FireService(enabled=False)
    service._model_kind = "yolo_onnx"
    service.threshold = 0.5

    monkeypatch.setattr(
        service,
        "_infer_yolo_detection",
        lambda _frame: {
            "score": 0.74,
            "bbox": [20, 18, 40, 22],
            "class_index": 1,
            "class_name": "smoke",
        },
    )

    result = service.detect_flame(_dummy_frame())

    assert result["flame"] is False
    assert result["smoke_detected"] is True
    assert result["detected_class"] == "smoke"
    assert result["detected_class_index"] == 1
    assert result["bbox"] == [20, 18, 40, 22]
    assert float(result["score"]) >= 0.7


def test_detect_flame_yolo_rejects_flat_orange_bbox(monkeypatch) -> None:
    service = FireService(enabled=False)
    service._model_kind = "yolo_onnx"
    service.threshold = 0.5
    frame = _dummy_frame()
    frame[14:50, 10:54] = np.array([0, 170, 255], dtype=np.uint8)

    monkeypatch.setattr(
        service,
        "_infer_yolo_detection",
        lambda _frame: {
            "score": 0.91,
            "bbox": [10, 14, 44, 36],
            "class_index": 0,
            "class_name": "fire",
        },
    )

    result = service.detect_flame(frame)

    assert result["flame"] is False
    assert result["smoke_detected"] is False
    assert result["detected_class"] == "none"
    assert result["detected_class_index"] == -1
    assert result["bbox"] == []
    assert result["rejected_class"] == "fire"
    assert result["rejection_reason"] == "flat_bright_color_region"


def test_detect_flame_yolo_keeps_varied_fire_like_bbox(monkeypatch) -> None:
    service = FireService(enabled=False)
    service._model_kind = "yolo_onnx"
    service.threshold = 0.5

    monkeypatch.setattr(
        service,
        "_infer_yolo_detection",
        lambda _frame: {
            "score": 0.91,
            "bbox": [10, 14, 44, 36],
            "class_index": 0,
            "class_name": "fire",
        },
    )

    result = service.detect_flame(_fire_like_frame())

    assert result["flame"] is True
    assert result["detected_class"] == "fire"
    assert result["bbox"] == [10, 14, 44, 36]


def test_detect_flame_classifier_rejects_flat_orange_region(monkeypatch) -> None:
    service = FireService(enabled=False)
    service._model_kind = "classifier"
    service.threshold = 0.5
    frame = np.zeros((120, 160, 3), dtype=np.uint8)
    frame[:] = np.array([0, 170, 255], dtype=np.uint8)

    monkeypatch.setattr(service, "_infer_fire_probability", lambda _frame: 0.93)

    result = service.detect_flame(frame)

    assert result["flame"] is False
    assert result["detected_class"] == "none"
    assert result["bbox"] == []
    assert result["rejected_class"] == "fire"
    assert result["rejection_reason"] == "flat_bright_color_region"


def test_infer_yolo_detection_decodes_smoke_candidate() -> None:
    service = FireService(enabled=False)
    service._model_kind = "yolo_onnx"
    service._runtime_input_size = 640
    service.threshold = 0.1
    service._net = _FakeNet(
        _yolo_output((320.0, 320.0, 160.0, 160.0, 0.05, 0.74))
    )

    result = service._infer_yolo_detection(_dummy_frame())

    assert result is not None
    assert result["class_name"] == "smoke"
    assert result["class_index"] == 1
    assert float(result["score"]) >= 0.7


def test_detect_flame_yolo_no_detection_defaults_to_none(monkeypatch) -> None:
    service = FireService(enabled=False)
    service._model_kind = "yolo_onnx"

    monkeypatch.setattr(service, "_infer_yolo_detection", lambda _frame: None)

    result = service.detect_flame(_dummy_frame())

    assert result["flame"] is False
    assert result["smoke_detected"] is False
    assert result["detected_class"] == "none"
    assert result["detected_class_index"] == -1
    assert result["bbox"] == []
