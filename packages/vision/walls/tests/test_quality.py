"""Chất lượng đường lùi: IoU trung bình `classic_wall_mask` trên 10 seed đầu (B5-02 [8])."""

import logging
import statistics

import numpy as np
import pytest

from packages.ml_contracts.synthetic import EVAL_SET_SEEDS, render_plan
from packages.vision.preprocess.types import RgbImage
from packages.vision.walls.classic import classic_wall_mask, default_min_thickness_px
from packages.vision.walls.metrics import mask_iou

logger = logging.getLogger(__name__)

_MIN_MEAN_IOU = 0.80
_SEED_SAMPLE = 10
_MIN_WINDOW_RECALL = 0.95


def test_classic_wall_mask_mean_iou_on_eval_seeds() -> None:
    """IoU trung bình trên 10 seed đầu `EVAL_SET_SEEDS` phải ≥ 0,80; in từng số bằng logging."""
    seeds = list(EVAL_SET_SEEDS)[:_SEED_SAMPLE]
    scores = []
    for seed in seeds:
        plan = render_plan(seed)
        thickness = default_min_thickness_px(plan.pixels.shape[1], plan.pixels.shape[0])
        mask = classic_wall_mask(RgbImage(plan.pixels), min_thickness_px=thickness)
        iou = mask_iou(mask, plan.walls_mask)
        logger.info("seed=%d iou=%.4f", seed, iou)
        scores.append(iou)
    mean_iou = statistics.mean(scores)
    logger.info("mean_iou=%.4f", mean_iou)
    assert mean_iou >= _MIN_MEAN_IOU


def _window_recall(seed: int) -> float:
    """Tỉ lệ điểm tường đáp án trong hộp cửa sổ của `seed` mà mặt nạ cổ điển giữ được."""
    plan = render_plan(seed)
    thickness = default_min_thickness_px(plan.pixels.shape[1], plan.pixels.shape[0])
    mask = classic_wall_mask(RgbImage(plan.pixels), min_thickness_px=thickness)
    windows = np.zeros_like(plan.walls_mask)
    for detection in plan.detections:
        if detection.label == "window":
            box = detection.box
            windows[int(box.y_min) : int(box.y_max), int(box.x_min) : int(box.x_max)] = True
    truth = plan.walls_mask & windows
    return np.count_nonzero(mask & truth) / np.count_nonzero(truth)


@pytest.mark.parametrize("seed", EVAL_SET_SEEDS)
def test_classic_wall_mask__window_gap_stays_wall(seed: int) -> None:
    """Cửa sổ (3 nét mảnh song song trong khe tường) là tường trong đáp án: giữ ≥ 95 % điểm."""
    assert _window_recall(seed) >= _MIN_WINDOW_RECALL
