from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from backend.app.services import face_identity_service as identity_module
from backend.app.services.face_identity_service import FaceIdentityService


def _textured_frame() -> np.ndarray:
    rng = np.random.default_rng(1234)
    return rng.integers(0, 255, size=(220, 220, 3), dtype=np.uint8)


def _blurred_frame() -> np.ndarray:
    return np.full((220, 220, 3), 120, dtype=np.uint8)


def _face(
    bbox: list[float],
    embedding: list[float],
    det_score: float = 0.91,
) -> SimpleNamespace:
    return SimpleNamespace(
        bbox=np.asarray(bbox, dtype=np.float32),
        embedding=np.asarray(embedding, dtype=np.float32),
        det_score=det_score,
    )


def _service(tmp_path, monkeypatch, faces: list[SimpleNamespace]) -> FaceIdentityService:
    model_root = tmp_path / "insightface"
    model_dir = model_root / "models" / "buffalo_l"
    model_dir.mkdir(parents=True)
    (model_dir / "det_10g.onnx").write_bytes(b"fake")

    class FakeFaceAnalysis:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def prepare(self, *args, **kwargs) -> None:
            pass

        def get(self, _frame: np.ndarray) -> list[SimpleNamespace]:
            return faces

    monkeypatch.setattr(identity_module, "FaceAnalysis", FakeFaceAnalysis)
    return FaceIdentityService(
        model_root=model_root,
        authorized_threshold=0.60,
        uncertain_threshold=0.45,
        min_face_width=60,
        min_face_height=60,
        blur_threshold=20.0,
    )


def test_authorized_clear_face_returns_authorized(tmp_path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch, [_face([20, 20, 130, 140], [1.0, 0.0])])

    result = service.recognize(
        _textured_frame(),
        {"Steve": [np.asarray([1.0, 0.0], dtype=np.float32)]},
    )

    assert result["face_status"] == "AUTHORIZED"
    assert result["recognized_name"] == "Steve"
    assert result["similarity"] >= 0.99


def test_unknown_clear_face_returns_unknown(tmp_path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch, [_face([20, 20, 130, 140], [0.0, 1.0])])

    result = service.recognize(
        _textured_frame(),
        {"Steve": [np.asarray([1.0, 0.0], dtype=np.float32)]},
    )

    assert result["face_status"] == "UNKNOWN_FACE"
    assert result["recognized_name"] is None


def test_no_face_returns_no_face(tmp_path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch, [])

    result = service.recognize(_textured_frame(), {})

    assert result["face_status"] == "NO_FACE"
    assert result["face_count"] == 0


def test_top_of_head_only_returns_no_face(tmp_path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch, [])

    result = service.recognize(_textured_frame(), {"Steve": [np.asarray([1.0, 0.0])]})

    assert result["face_status"] == "NO_FACE"


def test_blurry_face_returns_unclear(tmp_path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch, [_face([20, 20, 130, 140], [1.0, 0.0])])

    result = service.recognize(
        _blurred_frame(),
        {"Steve": [np.asarray([1.0, 0.0], dtype=np.float32)]},
    )

    assert result["face_status"] == "FACE_UNCLEAR"
    assert result["recognized_name"] is None


def test_small_distant_face_returns_unclear(tmp_path, monkeypatch) -> None:
    service = _service(tmp_path, monkeypatch, [_face([20, 20, 50, 50], [1.0, 0.0])])

    result = service.recognize(
        _textured_frame(),
        {"Steve": [np.asarray([1.0, 0.0], dtype=np.float32)]},
    )

    assert result["face_status"] == "FACE_UNCLEAR"


def test_multiple_faces_selects_largest_face(tmp_path, monkeypatch) -> None:
    faces = [
        _face([10, 10, 80, 80], [1.0, 0.0]),
        _face([20, 20, 180, 180], [0.0, 1.0]),
    ]
    service = _service(tmp_path, monkeypatch, faces)

    result = service.recognize(
        _textured_frame(),
        {"Steve": [np.asarray([1.0, 0.0], dtype=np.float32)]},
    )

    assert result["face_status"] == "UNKNOWN_FACE"
    assert result["bbox"] == [20.0, 20.0, 180.0, 180.0]
    assert result["face_count"] == 2
