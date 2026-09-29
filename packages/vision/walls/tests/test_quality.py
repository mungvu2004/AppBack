"""Chất lượng đường lùi: IoU trung bình `classic_wall_mask` trên 10 seed đầu (B5-02 [8])."""

import logging
import statistics

from packages.ml_contracts.synthetic import EVAL_SET_SEEDS, render_plan
from packages.vision.preprocess.types import RgbImage
from packages.vision.walls.classic import classic_wall_mask, default_min_thickness_px
from packages.vision.walls.metrics import mask_iou

logger = logging.getLogger(__name__)

_MIN_MEAN_IOU = 0.80
_SEED_SAMPLE = 10


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
