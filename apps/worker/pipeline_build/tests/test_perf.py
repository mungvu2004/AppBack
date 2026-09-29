"""Hiệu năng `build_layer` trên trần B5-01: 20k tường, 5k hộp, 5k chữ (B5-05 việc E, khối [8]).

Nhân bản `render_plan(100)` bằng tịnh tiến để giữ hình học hợp lệ (tường có hướng, hộp `min<max`)
ở quy mô lớn thay vì sinh ngẫu nhiên có thể vi phạm mô hình. Marker `perf` (BE-00 §12); phần phủ
của đường mã này do các test không-`perf` khác (`test_e2e_wire.py`, …) gánh.
"""

import logging
import math
import time
from datetime import UTC, datetime
from decimal import Decimal
from typing import Final
from unittest.mock import patch

import pytest

import apps.worker.pipeline_build.build as build_module
from apps.worker.pipeline_build.build import build_layer
from apps.worker.pipeline_build.ids import new_spatial_id
from packages.domain.spatial.model import SpatialLayer
from packages.ml_contracts.artifacts import (
    MAX_DETECTIONS,
    MAX_TEXTS,
    MAX_WALLS,
    BoxPx,
    DetectionPx,
    ObjectsResult,
    TextPx,
    TextResult,
    WallPx,
    WallsResult,
)
from packages.ml_contracts.synthetic import render_plan
from packages.testing.fixtures.clock import FakeClock

logger = logging.getLogger(__name__)

_LEVEL_ID: Final = new_spatial_id("level", FakeClock(start=datetime(2026, 1, 1, tzinfo=UTC)))
_FALLBACK_MM_PER_PX = Decimal("10")


def _shift_wall(wall: WallPx, dx: float, dy: float) -> WallPx:
    """Tường tịnh tiến `(dx, dy)` px; bề dày, tin cậy giữ nguyên."""
    start = wall.start.model_copy(update={"x": wall.start.x + dx, "y": wall.start.y + dy})
    end = wall.end.model_copy(update={"x": wall.end.x + dx, "y": wall.end.y + dy})
    return wall.model_copy(update={"start": start, "end": end})


def _shift_box(box: BoxPx, dx: float, dy: float) -> BoxPx:
    """Hộp tịnh tiến `(dx, dy)` px; `min < max` giữ nguyên vì cả hai cạnh cùng dịch."""
    return box.model_copy(
        update={"x_min": box.x_min + dx, "x_max": box.x_max + dx, "y_min": box.y_min + dy, "y_max": box.y_max + dy}
    )


def _tile_grid_size(base_counts: tuple[int, int, int], caps: tuple[int, int, int]) -> tuple[int, int]:
    """Số cột/hàng lưới tịnh tiến đủ để mọi danh sách đạt trần sau khi cắt ở caps."""
    replicas_needed = max(-(-cap // max(count, 1)) for count, cap in zip(base_counts, caps, strict=True))
    cols = math.ceil(math.sqrt(replicas_needed))
    rows = math.ceil(replicas_needed / cols)
    return cols, rows


def _oversized_inputs() -> tuple[tuple[WallPx, ...], tuple[DetectionPx, ...], tuple[TextPx, ...], int, int]:
    """Tường/hộp/chữ nhân bản từ `render_plan(100)` tới đúng trần B5-01, và kích thước ảnh lớn kèm theo."""
    plan = render_plan(100)
    base_h, base_w = plan.pixels.shape[0], plan.pixels.shape[1]
    cols, rows = _tile_grid_size(
        (len(plan.walls), len(plan.detections), len(plan.texts)), (MAX_WALLS, MAX_DETECTIONS, MAX_TEXTS)
    )
    walls: list[WallPx] = []
    detections: list[DetectionPx] = []
    texts: list[TextPx] = []
    for row in range(rows):
        for col in range(cols):
            dx, dy = col * base_w, row * base_h
            if len(walls) < MAX_WALLS:
                walls.extend(_shift_wall(wall, dx, dy) for wall in plan.walls)
            if len(detections) < MAX_DETECTIONS:
                detections.extend(
                    detection.model_copy(update={"box": _shift_box(detection.box, dx, dy)})
                    for detection in plan.detections
                )
            if len(texts) < MAX_TEXTS:
                texts.extend(text.model_copy(update={"box": _shift_box(text.box, dx, dy)}) for text in plan.texts)
    return (
        tuple(walls[:MAX_WALLS]),
        tuple(detections[:MAX_DETECTIONS]),
        tuple(texts[:MAX_TEXTS]),
        cols * base_w,
        rows * base_h,
    )


@pytest.mark.perf
def test_build_layer__perf_under_30_seconds(fake_clock: FakeClock) -> None:
    """20k tường/5k hộp/5k chữ (trần B5-01): `build_layer` < 30s sau một lượt khởi động seed 100."""
    warm_plan = render_plan(100)
    build_layer(
        level_id=_LEVEL_ID,
        walls=WallsResult(walls=warm_plan.walls),
        objects=ObjectsResult(detections=warm_plan.detections),
        text=TextResult(items=warm_plan.texts),
        width_px=warm_plan.pixels.shape[1],
        height_px=warm_plan.pixels.shape[0],
        fallback_mm_per_px=_FALLBACK_MM_PER_PX,
        clock=fake_clock,
    )

    walls, detections, texts, width_px, height_px = _oversized_inputs()
    assert len(walls) == MAX_WALLS
    assert len(detections) == MAX_DETECTIONS
    assert len(texts) == MAX_TEXTS

    post_rules_seconds: list[float] = []
    real_apply_post_rules = build_module.apply_post_rules  # type: ignore[attr-defined]  # build.py nhập lại tên này

    def _timed_apply_post_rules(layer: SpatialLayer) -> SpatialLayer:
        """Vá đo giờ gọi `apply_post_rules` thật, không thay hành vi."""
        start = time.perf_counter()
        result: SpatialLayer = real_apply_post_rules(layer)
        post_rules_seconds.append(time.perf_counter() - start)
        return result

    with patch.object(build_module, "apply_post_rules", side_effect=_timed_apply_post_rules):
        start = time.perf_counter()
        build_layer(
            level_id=_LEVEL_ID,
            walls=WallsResult(walls=tuple(walls)),
            objects=ObjectsResult(detections=tuple(detections)),
            text=TextResult(items=tuple(texts)),
            width_px=width_px,
            height_px=height_px,
            fallback_mm_per_px=_FALLBACK_MM_PER_PX,
            clock=fake_clock,
        )
        elapsed = time.perf_counter() - start

    logger.info(
        "build_layer elapsed=%.3fs apply_post_rules_total=%.3fs apply_post_rules_calls=%d",
        elapsed,
        sum(post_rules_seconds),
        len(post_rules_seconds),
    )
    assert elapsed < 30.0, f"build_layer mất {elapsed:.2f}s, trần 30s"
