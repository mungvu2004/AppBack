"""Trần thời gian lát + suy luận trang lớn nhất hợp đồng (K28, BE-00 §12).

Lớp bọc mỏng chuyển tiếp tới phiên `onnxruntime` thật (không mock ORT, K23) để đếm đúng
`len(tile_windows(...))` lượt `session.run`. Phần độ phủ đường mã này đã có
`test_detector.py::test_detect__page_coordinates_correct_at_every_tile` (không `perf`) gánh.
"""

import logging
import time
from typing import Any

import numpy as np
import onnxruntime as ort  # type: ignore[import-untyped]  # onnxruntime 1.30 không có py.typed
import pytest

from apps.ml.objects.detector import MAX_DETECTIONS, YoloOnnxDetector, _Candidates, merge_candidates
from apps.ml.objects.tests.onnx_models import make_const_yolo, yolo_output
from apps.ml.objects.tiles import overlap_for, tile_windows

_LOGGER = logging.getLogger(__name__)
BIG_W, BIG_H = 7745, 5164
BUDGET_S = 60.0
MERGE_BUDGET_S = 2.0


class _CountingSession:
    """Bọc phiên `onnxruntime` thật, chỉ đếm lượt `run` — không thay hành vi suy luận."""

    def __init__(self, inner: ort.InferenceSession) -> None:
        """Bọc `inner`; `run_count` bắt đầu ở 0."""
        self._inner = inner
        self.run_count = 0

    def get_inputs(self) -> Any:
        """Uỷ quyền thẳng cho phiên thật (dùng lúc `YoloOnnxDetector.__init__` kiểm hình dạng)."""
        return self._inner.get_inputs()

    def get_outputs(self) -> Any:
        """Uỷ quyền thẳng cho phiên thật."""
        return self._inner.get_outputs()

    def run(self, output_names: Any, input_feed: Any) -> Any:
        """Đếm rồi uỷ quyền `run` cho phiên thật, không đổi kết quả."""
        self.run_count += 1
        return self._inner.run(output_names, input_feed)


@pytest.mark.perf
def test_detect__runs_once_per_tile_under_budget() -> None:
    """Trang 7745x5164, model hằng `S=640`: đúng một lượt `run` mỗi lát, tổng < 60s."""
    output = yolo_output([], nc=1)
    real_session = ort.InferenceSession(make_const_yolo(output), providers=["CPUExecutionProvider"])
    counting = _CountingSession(real_session)
    detector = YoloOnnxDetector(counting, ("door",))

    warmup_start = time.perf_counter()
    detector.detect(np.zeros((640, 640, 3), dtype=np.uint8))
    _LOGGER.info("warmup_seconds=%.3f", time.perf_counter() - warmup_start)
    counting.run_count = 0

    image = np.zeros((BIG_H, BIG_W, 3), dtype=np.uint8)
    overlap_px = overlap_for(detector.input_px)
    expected_calls = len(tile_windows(BIG_W, BIG_H, tile_px=detector.input_px, overlap_px=overlap_px))

    started = time.perf_counter()
    detector.detect(image)
    elapsed = time.perf_counter() - started
    _LOGGER.info("detect_page_seconds=%.3f lát=%d", elapsed, counting.run_count)
    assert counting.run_count == expected_calls
    assert elapsed < BUDGET_S


def _random_candidates(n: int, *, seed: int) -> _Candidates:
    """`n` ứng viên ngẫu nhiên tất định, nhiều nhãn/lát, cho trần hiệu năng `merge_candidates`."""
    rng = np.random.default_rng(seed)
    tiles_grid = np.array([(tx * 480.0, ty * 480.0, 640.0, 640.0) for ty in range(4) for tx in range(4)])
    tile_idx = rng.integers(0, tiles_grid.shape[0], size=n)
    tiles = tiles_grid[tile_idx]
    x1 = tiles[:, 0] + rng.uniform(0, 600, size=n)
    y1 = tiles[:, 1] + rng.uniform(0, 600, size=n)
    boxes = np.stack([x1, y1, x1 + rng.uniform(5, 40, size=n), y1 + rng.uniform(5, 40, size=n)], axis=1)
    classes = rng.integers(0, 8, size=n).astype(np.int64)
    scores = rng.uniform(0.25, 1.0, size=n)
    return _Candidates(boxes=boxes, scores=scores, classes=classes, tiles=tiles)


@pytest.mark.perf
def test_merge_candidates__three_thousand_candidates_under_budget() -> None:
    """~3000 ứng viên ngẫu nhiên tất định (seed cố định), nhiều nhãn/lát: `merge_candidates` < 2s.

    Phần độ phủ đường mã này đã có test không-`perf` của `test_detector_postprocess.py` gánh.
    """
    candidates = _random_candidates(3000, seed=42)
    started = time.perf_counter()
    result = merge_candidates(candidates, page_w=2400, page_h=2400)
    elapsed = time.perf_counter() - started
    _LOGGER.info("merge_candidates_seconds=%.3f n_in=%d n_out=%d", elapsed, 3000, len(result))
    assert elapsed < MERGE_BUDGET_S
    assert len(result) <= MAX_DETECTIONS
