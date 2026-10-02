"""Test `metrics.evaluate_iou`, `metrics.guarded` (khối [6])."""

import logging
import time
from pathlib import Path

import cv2
import numpy as np
import pytest
from numpy.typing import NDArray

from apps.ml.training_runner.errors import TrainingStopped
from apps.ml.training_segformer import metrics as segformer_metrics
from apps.ml.training_segformer.data import read_sample, sample_dirs
from apps.ml.training_segformer.tests.support import RecordingReporter, write_split
from apps.ml.walls.spec import LOGITS_STRIDE, TILE_PX, WALL_CLASS
from packages.ml_contracts.artifacts import encode_mask, encode_rgb_png

_BLANK_SIZE_PX: int = 64


def test_evaluate_iou_empty_split_returns_none(tmp_path: Path) -> None:
    """Split không có mẫu nào (thư mục không tồn tại) → `None`."""

    def _run_tile(_tile: NDArray[np.float32]) -> NDArray[np.float32]:
        """Không được gọi: split rỗng phải trả `None` trước khi chạy bất kỳ lát nào."""
        raise AssertionError("không mẫu nào thì không được chạy lát")

    assert segformer_metrics.evaluate_iou(_run_tile, tmp_path / "validation") is None


def test_evaluate_iou_oracle_run_tile_is_one(tmp_path: Path) -> None:
    """Run-tile "tiên tri" dựng logit từ chính mặt nạ thật (nén qua `LOGITS_STRIDE` rồi phóng lại
    như `stitch_mask`) → IoU tích luỹ gần 1.0 (sai số chỉ do làm tròn mép lúc nén/phóng)."""
    write_split(tmp_path, "validation", 2, seed=1000)
    logits_px = TILE_PX // LOGITS_STRIDE
    queue: list[NDArray[np.float32]] = []
    for sample_dir in sample_dirs(tmp_path / "validation"):
        _pixels, truth = read_sample(sample_dir)
        height, width = truth.shape
        padded = np.zeros((TILE_PX, TILE_PX), dtype=np.float32)
        padded[:height, :width] = truth.astype(np.float32)
        small = cv2.resize(padded, (logits_px, logits_px), interpolation=cv2.INTER_NEAREST)
        queue.append((small * 2.0 - 1.0) * 10.0)

    def _oracle_tile(_tile: NDArray[np.float32]) -> NDArray[np.float32]:
        """Logit dựng từ mặt nạ thật đã nén (thứ tự gọi theo thứ tự mẫu của `sample_dirs`)."""
        signed = queue.pop(0)
        out = np.zeros((1, 2, logits_px, logits_px), dtype=np.float32)
        out[0, WALL_CLASS] = signed
        out[0, 1 - WALL_CLASS] = -signed
        return out

    start = time.monotonic()
    iou = segformer_metrics.evaluate_iou(_oracle_tile, tmp_path / "validation")
    logging.getLogger(__name__).info("oracle iou=%.4f thời gian=%.3fs", iou or -1.0, time.monotonic() - start)
    assert iou is not None
    assert iou > 0.85


def test_evaluate_iou_union_zero_is_one(tmp_path: Path) -> None:
    """Hợp = 0 trên toàn split: mẫu thật trên đĩa (ảnh trắng + mặt nạ rỗng) → `1.0` như `mask_iou`."""
    logits_px = TILE_PX // LOGITS_STRIDE
    sample_dir = tmp_path / "validation" / "s0000"
    sample_dir.mkdir(parents=True)
    pixels = np.full((_BLANK_SIZE_PX, _BLANK_SIZE_PX, 3), 255, dtype=np.uint8)
    empty_mask = np.zeros((_BLANK_SIZE_PX, _BLANK_SIZE_PX), dtype=np.bool_)
    (sample_dir / "image.png").write_bytes(encode_rgb_png(pixels))
    (sample_dir / "walls.png").write_bytes(encode_mask(empty_mask))

    def _empty_tile(_tile: NDArray[np.float32]) -> NDArray[np.float32]:
        """Logit luôn khai nền (không tường): dự đoán rỗng khớp mặt nạ rỗng thật."""
        out = np.zeros((1, 2, logits_px, logits_px), dtype=np.float32)
        out[0, 1 - WALL_CLASS] = 1.0
        return out

    assert segformer_metrics.evaluate_iou(_empty_tile, tmp_path / "validation") == pytest.approx(1.0)


def test_guarded_raises_training_stopped_before_next_tile() -> None:
    """`guarded` hỏi `reporter.cancelled()` trước lát kế; đúng ngay lần đầu → `TrainingStopped`."""
    reporter = RecordingReporter(cancel_when=lambda calls: calls >= 1)

    def _run_tile(_tile: NDArray[np.float32]) -> NDArray[np.float32]:
        """Không được gọi: `guarded` phải huỷ trước khi chạy lát kế."""
        raise AssertionError("không được chạy lát khi đã huỷ")

    wrapped = segformer_metrics.guarded(_run_tile, reporter)
    with pytest.raises(TrainingStopped):
        wrapped(np.zeros((1, 3, TILE_PX, TILE_PX), dtype=np.float32))
    assert reporter.cancel_checks == 1
