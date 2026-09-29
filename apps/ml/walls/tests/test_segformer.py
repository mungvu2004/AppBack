"""Test `apps.ml.walls.segformer`: ghép lát, kiểm hợp đồng ONNX, hiệu năng (khối [2], [8])."""

import logging
import time

import cv2
import numpy as np
import onnxruntime as ort  # type: ignore[import-untyped]  # onnxruntime 1.30 không có py.typed
import pytest
from numpy.typing import NDArray

from apps.ml.walls.segformer import SegformerOnnxSegmenter
from apps.ml.walls.spec import IMAGE_MEAN, IMAGE_STD, LOGITS_STRIDE, TILE_PX
from apps.ml.walls.tests.onnx_fixtures import (
    make_runtime_broken_segformer,
    make_threshold_segformer,
    make_two_input_segformer,
    make_wrong_input_segformer,
    make_wrong_output_segformer,
)
from packages.messaging.tasks import PermanentError
from packages.ml_contracts.synthetic import render_plan

_LOGGER = logging.getLogger(__name__)


def _session(data: bytes) -> ort.InferenceSession:
    return ort.InferenceSession(data, providers=["CPUExecutionProvider"])


def _segmenter() -> SegformerOnnxSegmenter:
    return SegformerOnnxSegmenter(_session(make_threshold_segformer()))


def _wall_image(height: int, width: int, thickness: int) -> tuple[NDArray[np.uint8], NDArray[np.bool_]]:
    """Nền sáng, một tường ngang tối `thickness` px giữa ảnh, cùng mặt nạ vẽ tham chiếu."""
    pixels = np.full((height, width, 3), 240, dtype=np.uint8)
    truth = np.zeros((height, width), dtype=np.bool_)
    y0 = (height // 2 - thickness // 2) // LOGITS_STRIDE * LOGITS_STRIDE
    pixels[y0 : y0 + thickness, :] = 20
    truth[y0 : y0 + thickness, :] = True
    return pixels, truth


def _reference_mask(pixels: NDArray[np.uint8]) -> NDArray[np.bool_]:
    """Cùng công thức ngưỡng của model tí hon, tính thẳng trên cả ảnh — không ghép lát."""
    mean = np.asarray(IMAGE_MEAN, dtype=np.float32)
    std = np.asarray(IMAGE_STD, dtype=np.float32)
    normalized = (pixels.astype(np.float32) / 255.0 - mean) / std
    channel_mean = normalized.mean(axis=2)
    height, width = channel_mean.shape
    pooled_h, pooled_w = height // LOGITS_STRIDE, width // LOGITS_STRIDE
    cropped = channel_mean[: pooled_h * LOGITS_STRIDE, : pooled_w * LOGITS_STRIDE]
    pooled = cropped.reshape(pooled_h, LOGITS_STRIDE, pooled_w, LOGITS_STRIDE).mean(axis=(1, 3))
    diff = -2.0 * pooled
    diff_full = cv2.resize(diff, (width, height), interpolation=cv2.INTER_LINEAR)
    return diff_full > 0.0


def test_segment__matches_reference_and_drawn_wall() -> None:
    pixels, truth = _wall_image(1900, 2500, 16)
    mask = _segmenter().segment(pixels)
    reference = _reference_mask(pixels)
    mismatch_ratio = np.count_nonzero(mask != reference) / mask.size
    assert mismatch_ratio <= 0.005
    union = np.count_nonzero(mask | truth)
    iou = np.count_nonzero(mask & truth) / union
    assert iou >= 0.9


def test_segment__small_image_matches_input_shape() -> None:
    pixels, _ = _wall_image(400, 600, 8)
    mask = _segmenter().segment(pixels)
    assert mask.shape == (400, 600)


def test_init__rejects_wrong_input_shape() -> None:
    with pytest.raises(PermanentError) as excinfo:
        SegformerOnnxSegmenter(_session(make_wrong_input_segformer()))
    assert excinfo.value.code == "MODEL_FORMAT_UNSUPPORTED"


def test_init__rejects_wrong_output_class_count() -> None:
    with pytest.raises(PermanentError) as excinfo:
        SegformerOnnxSegmenter(_session(make_wrong_output_segformer()))
    assert excinfo.value.code == "MODEL_FORMAT_UNSUPPORTED"


def test_init__rejects_two_inputs() -> None:
    with pytest.raises(PermanentError) as excinfo:
        SegformerOnnxSegmenter(_session(make_two_input_segformer()))
    assert excinfo.value.code == "MODEL_FORMAT_UNSUPPORTED"


def test_segment__maps_runtime_error_to_model_format_unsupported() -> None:
    segmenter = SegformerOnnxSegmenter(_session(make_runtime_broken_segformer()))
    with pytest.raises(PermanentError) as excinfo:
        segmenter.segment(np.full((TILE_PX, TILE_PX, 3), 128, dtype=np.uint8))
    assert excinfo.value.code == "MODEL_FORMAT_UNSUPPORTED"


@pytest.mark.perf
def test_segment__full_page_under_30_seconds() -> None:
    segmenter = _segmenter()
    warmup_start = time.perf_counter()
    segmenter.segment(np.full((TILE_PX, TILE_PX, 3), 200, dtype=np.uint8))
    _LOGGER.info("warmup_seconds=%.3f", time.perf_counter() - warmup_start)

    plan = render_plan(1, width_px=7745, height_px=5164)
    start = time.perf_counter()
    segmenter.segment(plan.pixels)
    elapsed = time.perf_counter() - start
    _LOGGER.info("segment_page_seconds=%.3f", elapsed)
    assert elapsed < 30.0
