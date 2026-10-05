"""Helper dùng chung của test `pipeline_build`: hằng và vỏ bọc `build_layer` (gộp NO-291)."""

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Final

from apps.worker.pipeline_build.build import BuiltLayer, build_layer
from apps.worker.pipeline_build.ids import new_spatial_id
from packages.ml_contracts.artifacts import (
    DetectionPx,
    ObjectsResult,
    TextPx,
    TextResult,
    WallPx,
    WallsResult,
)
from packages.ml_contracts.synthetic import SyntheticPlan
from packages.testing.fixtures.clock import FakeClock

FALLBACK_MM_PER_PX: Final = Decimal("10")
SPATIAL_LEVEL_ID: Final = new_spatial_id("level", FakeClock(start=datetime(2026, 1, 1, tzinfo=UTC)))
"""Id tầng hợp mẫu W4 (`LevelIdStr`); test cần id thật, không phải chuỗi tuỳ ý."""


def build_wrapped(
    *,
    walls: Sequence[WallPx] = (),
    detections: Sequence[DetectionPx] = (),
    texts: Sequence[TextPx] = (),
    width_px: int,
    height_px: int,
    fallback_mm_per_px: Decimal = FALLBACK_MM_PER_PX,
    clock: FakeClock,
    level_id: str = SPATIAL_LEVEL_ID,
) -> BuiltLayer:
    """`build_layer` với ba kết quả ML dựng từ dãy thường; mọi test dựng lớp đi qua đây."""
    return build_layer(
        level_id=level_id,
        walls=WallsResult(walls=tuple(walls)),
        objects=ObjectsResult(detections=tuple(detections)),
        text=TextResult(items=tuple(texts)),
        width_px=width_px,
        height_px=height_px,
        fallback_mm_per_px=fallback_mm_per_px,
        clock=clock,
    )


def build_from_plan(
    plan: SyntheticPlan,
    clock: FakeClock,
    *,
    walls: Sequence[WallPx] | None = None,
    detections: Sequence[DetectionPx] | None = None,
    texts: Sequence[TextPx] | None = None,
    fallback_mm_per_px: Decimal = FALLBACK_MM_PER_PX,
) -> BuiltLayer:
    """Dựng từ một `SyntheticPlan`; tường/phát hiện/chữ để `None` thì lấy của `plan`."""
    return build_wrapped(
        walls=plan.walls if walls is None else walls,
        detections=plan.detections if detections is None else detections,
        texts=plan.texts if texts is None else texts,
        width_px=plan.pixels.shape[1],
        height_px=plan.pixels.shape[0],
        fallback_mm_per_px=fallback_mm_per_px,
        clock=clock,
    )
