"""Ba họ model ML và bảng tra theo họ (HOP-DONG-MOI §8, BE-00 §9).

Id họ trùng id bước pipeline của FE (`src/lib/realtime/pipeline.ts:48-55`): một bước
suy luận chạy đúng một họ, nên kết quả bước và phiên bản model nói cùng một tên.

**Chỉ thư viện chuẩn**: `pinned.py` nhập module này và chạy lúc build ảnh `ml`, trước
khi có numpy hay pydantic. Vì thế bước (`FAMILY_STEP`) khai bằng `str`, không nhập
`packages.core.pipeline`; test so hai bảng với nhau.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final, Literal

ModelFamily = Literal["wallSegmentation", "openingAndFurnitureDetection", "dimensionReading"]
TrainableFamily = Literal["wallSegmentation", "openingAndFurnitureDetection"]
MetricName = Literal["iou", "map50", "cer"]

MODEL_FAMILIES: Final[tuple[ModelFamily, ...]] = (
    "wallSegmentation",
    "openingAndFurnitureDetection",
    "dimensionReading",
)
TRAINABLE_FAMILIES: Final[tuple[TrainableFamily, ...]] = ("wallSegmentation", "openingAndFurnitureDetection")

FAMILY_STEP: Final[Mapping[ModelFamily, str]] = MappingProxyType({family: family for family in MODEL_FAMILIES})
"""Họ → id bước pipeline chạy nó (cùng chuỗi)."""

BASE_MODELS: Final[Mapping[TrainableFamily, tuple[str, ...]]] = MappingProxyType(
    {
        "wallSegmentation": ("mitB0", "mitB1"),
        "openingAndFurnitureDetection": ("yolov8n", "yolov8s"),
    }
)
"""Model gốc huấn luyện được theo họ (`TRAINING_BASE_MODELS`, HOP-DONG-MOI §8)."""

FAMILY_METRIC: Final[Mapping[ModelFamily, MetricName]] = MappingProxyType(
    {
        "wallSegmentation": "iou",
        "openingAndFurnitureDetection": "map50",
        "dimensionReading": "cer",
    }
)
"""Số đo duy nhất của họ trong `ModelMetricsSchema` (`metrics` chứa **đúng** khoá này)."""
