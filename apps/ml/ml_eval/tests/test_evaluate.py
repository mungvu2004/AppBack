"""Test `evaluate.evaluate_family` (khối [8] "Số đo")."""

import dataclasses
from collections.abc import Sequence

import numpy as np
import pytest
from numpy.typing import NDArray

from apps.ml.ml_eval.evaluate import evaluate_family
from packages.ml_contracts import synthetic
from packages.ml_contracts.artifacts import BoxPx, DetectionPx
from packages.ml_contracts.fakes import FakeObjectDetector, FakeTextReader, FakeWallSegmenter


def test_evaluate_family_wall_segmentation_fake_adapter_is_perfect() -> None:
    """Bộ giả trả đúng đáp án trên 3 seed → `iou == 1.0`, đúng một khoá `iou`."""
    result = evaluate_family("wallSegmentation", FakeWallSegmenter(), seeds=[100, 101, 102])
    assert result == {"iou": 1.0}


def test_evaluate_family_object_detection_fake_adapter_is_perfect() -> None:
    """Bộ giả trả đúng đáp án trên 3 seed → `map50 == 0.995`, đúng một khoá `map50`."""
    result = evaluate_family("openingAndFurnitureDetection", FakeObjectDetector(), seeds=[100, 101, 102])
    assert result == {"map50": pytest.approx(0.995)}


def test_evaluate_family_text_reading_fake_adapter_is_perfect() -> None:
    """Bộ giả trả đúng đáp án trên 3 seed → `cer == 0.0`, đúng một khoá `cer`."""
    result = evaluate_family("dimensionReading", FakeTextReader(), seeds=[100, 101, 102])
    assert result == {"cer": 0.0}


def _door(x: float, y: float, confidence: float) -> DetectionPx:
    """Hộp vuông cạnh 10, nhãn `other` với góc trên-trái `(x, y)`."""
    return DetectionPx(label="other", box=BoxPx(x_min=x, y_min=y, x_max=x + 10, y_max=y + 10), confidence=confidence)


class _ScriptedDetector:
    """`ObjectDetector` trả lần lượt từng danh sách đã định sẵn, mỗi ảnh (mỗi seed) một danh sách."""

    def __init__(self, replies: Sequence[tuple[DetectionPx, ...]]) -> None:
        """Nhớ các danh sách trả lời theo thứ tự seed."""
        self._replies = iter(replies)

    def detect(self, _image: NDArray[np.uint8]) -> tuple[DetectionPx, ...]:
        """Danh sách của seed kế tiếp."""
        return next(self._replies)


def test_evaluate_family_object_detection_matches_hand_computed_ap(monkeypatch: pytest.MonkeyPatch) -> None:
    """Một nhãn, 3 hộp đáp án trên 2 seed; adapter trúng 2, thêm 1 hộp sai (conf thấp nhất), bỏ sót 1.

    Sắp theo confidence: TP, TP, FP → recall `[1/3, 2/3, 2/3]`, precision `[1, 1, 2/3]`. Sau bao lồi
    precision là 1 cho tới recall 2/3 rồi 0; lưới 101 điểm của AP cho 66 khoảng đầy + nửa khoảng
    `0.66→0.67` = `0.66 + 0.005 = 0.665` (số tính tay, không gọi lại `map50`).
    """
    truth = {100: (_door(0, 0, 1.0),), 101: (_door(0, 0, 1.0), _door(20, 20, 1.0))}
    real_render_plan = synthetic.render_plan
    monkeypatch.setattr(
        synthetic, "render_plan", lambda seed: dataclasses.replace(real_render_plan(seed), detections=truth[seed])
    )
    detector = _ScriptedDetector([(_door(0, 0, 0.9),), (_door(0, 0, 0.8), _door(100, 100, 0.7))])
    result = evaluate_family("openingAndFurnitureDetection", detector, seeds=[100, 101])
    assert result == {"map50": pytest.approx(0.665, abs=1e-6)}


def test_evaluate_family_spies_render_plan_called_with_seeds_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    """`synthetic.render_plan` được gọi đúng seed theo thứ tự (spy M06)."""
    seen: list[int] = []
    real_render_plan = synthetic.render_plan

    def _spy(seed: int) -> object:
        """Ghi lại seed rồi gọi hàm thật."""
        seen.append(seed)
        return real_render_plan(seed)

    monkeypatch.setattr(synthetic, "render_plan", _spy)
    evaluate_family("wallSegmentation", FakeWallSegmenter(), seeds=[105, 103, 110])
    assert seen == [105, 103, 110]
