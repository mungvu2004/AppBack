"""Test `evaluate.evaluate_family` (khối [8] "Số đo")."""

import numpy as np
import pytest
from numpy.typing import NDArray

from apps.ml.ml_eval.evaluate import evaluate_family
from packages.ml_contracts.artifacts import DetectionPx
from packages.ml_contracts.fakes import FakeObjectDetector, FakeTextReader, FakeWallSegmenter
from packages.ml_contracts.synthetic import render_plan


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


class _DropOneBoxDetector:
    """`ObjectDetector` tiêm lỗi: bỏ một hộp ở seed đầu tiên nó thấy."""

    def __init__(self) -> None:
        """Nhớ đã bỏ hộp chưa — chỉ bỏ đúng một lần."""
        self._dropped = False

    def detect(self, image: NDArray[np.uint8]) -> tuple[DetectionPx, ...]:
        """Đáp án đúng, trừ seed đầu bị bỏ một hộp (nếu có hộp nào)."""
        from packages.ml_contracts.fakes import answer_for

        plan = answer_for(image)
        if plan is None:
            return ()
        if not self._dropped and plan.detections:
            self._dropped = True
            return plan.detections[1:]
        return plan.detections


def test_evaluate_family_adapter_drops_one_box_matches_hand_computed() -> None:
    """Adapter bỏ một hộp ở một seed → `map50` giảm, khớp tính tay bằng gọi `map50` trực tiếp."""
    from apps.ml.ml_eval.metrics import map50

    seeds = [100, 101, 102]
    samples = []
    for seed in seeds:
        plan = render_plan(seed)
        dets = plan.detections[1:] if seed == seeds[0] and plan.detections else plan.detections
        samples.append((dets, plan.detections))
    expected = map50(samples)
    result = evaluate_family("openingAndFurnitureDetection", _DropOneBoxDetector(), seeds=seeds)
    assert result == {"map50": pytest.approx(expected, abs=1e-6)}


def test_evaluate_family_spies_render_plan_called_with_seeds_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    """`synthetic.render_plan` được gọi đúng seed theo thứ tự (spy M06)."""
    from packages.ml_contracts import synthetic

    seen: list[int] = []
    real_render_plan = synthetic.render_plan

    def _spy(seed: int) -> object:
        """Ghi lại seed rồi gọi hàm thật."""
        seen.append(seed)
        return real_render_plan(seed)

    monkeypatch.setattr(synthetic, "render_plan", _spy)
    evaluate_family("wallSegmentation", FakeWallSegmenter(), seeds=[105, 103, 110])
    assert seen == [105, 103, 110]
