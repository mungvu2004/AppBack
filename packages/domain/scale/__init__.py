"""Tỉ lệ bản vẽ thuần: gương `src/domain/units/scale.ts` và `outliers.ts` FE, cùng phép tính số thực.

Ngưỡng, trung vị và MAD, suy tỉ lệ (không bao giờ tỉ lệ mặc định, K19), so với
ước lượng AI, đổi tỉ lệ cho mục chưa duyệt (#35, N19).
"""

from packages.domain.scale.infer import (
    ScaleAiDeviation,
    ScaleResult,
    ScaleSample,
    classify_scale_range,
    compare_scale_to_ai_estimate,
    infer_scale,
)
from packages.domain.scale.outliers import OutlierSplit, median, split_outliers
from packages.domain.scale.rescale import RescaleError, rescale_dimensions, rescale_unreviewed
from packages.domain.scale.thresholds import SCALE_THRESHOLDS

__all__ = [
    "SCALE_THRESHOLDS",
    "OutlierSplit",
    "RescaleError",
    "ScaleAiDeviation",
    "ScaleResult",
    "ScaleSample",
    "classify_scale_range",
    "compare_scale_to_ai_estimate",
    "infer_scale",
    "median",
    "rescale_dimensions",
    "rescale_unreviewed",
    "split_outliers",
]
