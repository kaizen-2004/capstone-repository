import numpy as np

from backend.app.modules.fire_service import FireService


def _dummy_frame() -> np.ndarray:
    return np.zeros((120, 160, 3), dtype=np.uint8)


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


def test_detect_flame_yolo_smoke_is_ignored(monkeypatch) -> None:
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
    assert result["smoke_detected"] is False
    assert result["detected_class"] == "none"
    assert result["detected_class_index"] == -1
    assert result["bbox"] == []
    assert float(result["score"]) == 0.0


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
