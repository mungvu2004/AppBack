"""Dây thật của `build_layer`: tường từ `vectorize`, hộp/chữ đáp án (B5-05 việc E, khối [8]).

`vectorize` trả `WallSegment` (px thuần, `packages/vision/walls/types.py`), đổi sang `WallPx` ngay
trong test — không nhập `apps.ml.*` (nơi đổi kiểu thật xảy ra ở ranh giới ML, ngoài phạm vi việc E).
"""

import logging
import math
from datetime import UTC, datetime
from decimal import Decimal
from typing import Final

import pytest

from apps.worker.pipeline_build.build import BuiltLayer, build_layer
from apps.worker.pipeline_build.ids import new_spatial_id
from packages.domain.spatial.integrity import check_integrity, has_critical
from packages.domain.spatial.model import Point, Segment, Wall
from packages.ml_contracts.artifacts import ObjectsResult, TextResult, WallPx, WallsResult
from packages.ml_contracts.synthetic import SyntheticPlan, render_plan
from packages.testing.fixtures.clock import FakeClock
from packages.vision.walls.types import WallSegment
from packages.vision.walls.vectorize import vectorize

logger = logging.getLogger(__name__)

_FIRST_TEN_SEEDS: Final = tuple(range(100, 110))
_LEVEL_ID: Final = new_spatial_id("level", FakeClock(start=datetime(2026, 1, 1, tzinfo=UTC)))
_FALLBACK_MM_PER_PX = Decimal("10")
_DOOR_LABELS: Final = frozenset({"door", "double_door"})


def _to_wall_px(segment: WallSegment) -> WallPx:
    """`WallSegment` (px thuần) → `WallPx` (hợp đồng ML): `start`/`end` là tuple `(x, y)` → dict."""
    (x0, y0), (x1, y1) = segment.start, segment.end
    return WallPx(
        start={"x": x0, "y": y0},
        end={"x": x1, "y": y1},
        thickness_px=segment.thickness_px,
        confidence=segment.confidence,
    )


def _build_from_vectorized(seed: int, clock: FakeClock) -> tuple[BuiltLayer, SyntheticPlan]:
    """Dựng `BuiltLayer` với tường thật từ `vectorize(plan.walls_mask)`; trả kèm `plan`."""
    plan = render_plan(seed)
    walls = tuple(_to_wall_px(segment) for segment in vectorize(plan.walls_mask))
    built = build_layer(
        level_id=_LEVEL_ID,
        walls=WallsResult(walls=walls),
        objects=ObjectsResult(detections=plan.detections),
        text=TextResult(items=plan.texts),
        width_px=plan.pixels.shape[1],
        height_px=plan.pixels.shape[0],
        fallback_mm_per_px=_FALLBACK_MM_PER_PX,
        clock=clock,
    )
    return built, plan


def _point_segment_distance(point: Point, segment: Segment) -> float:
    """Khoảng cách từ `point` tới đoạn `segment`, mm (chiếu vuông góc, kẹp trong đoạn)."""
    ax, ay = segment.start.x, segment.start.y
    bx, by = segment.end.x, segment.end.y
    px, py = point.x, point.y
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
    closest_x, closest_y = ax + t * dx, ay + t * dy
    return math.hypot(px - closest_x, py - closest_y)


def _nearest_wall(walls: tuple[Wall, ...], point: Point) -> Wall:
    """Tường có đường tim gần `point` nhất (khoảng cách điểm-đoạn)."""
    return min(walls, key=lambda wall: _point_segment_distance(point, wall.centreline))


@pytest.mark.parametrize("seed", _FIRST_TEN_SEEDS)
def test_build_layer__real_wire_no_critical_and_min_rooms(seed: int, fake_clock: FakeClock) -> None:
    """Dây thật (10 seed đầu): không vấn đề nghiêm trọng, mỗi seed ≥ 2 phòng."""
    built, _ = _build_from_vectorized(seed, fake_clock)
    issues = check_integrity(built.layer, level_id=_LEVEL_ID)
    assert not has_critical(issues), f"seed {seed}: {issues}"
    assert len(built.layer.rooms) >= 2, f"seed {seed}: {len(built.layer.rooms)} phòng"


def test_build_layer__real_door_match_rate_at_least_90_percent(fake_clock: FakeClock) -> None:
    """≥ 90% cửa đi đáp án (door/double_door) qua 10 seed đầu thành `Opening` trên đúng tường gần nhất."""
    matched = 0
    total = 0
    for seed in _FIRST_TEN_SEEDS:
        built, plan = _build_from_vectorized(seed, FakeClock(start=fake_clock.now()))
        scale = float(built.scale_mm_per_px)
        for detection in plan.detections:
            if detection.label not in _DOOR_LABELS:
                continue
            total += 1
            centre_px_x = (detection.box.x_min + detection.box.x_max) / 2
            centre_px_y = (detection.box.y_min + detection.box.y_max) / 2
            centre_mm = Point(x=round(centre_px_x * scale), y=round(centre_px_y * scale))
            nearest = _nearest_wall(built.layer.walls, centre_mm)
            if nearest.opening_ids:
                matched += 1
    rate = matched / total if total else 0.0
    logger.info("door_match_rate=%.4f matched=%d total=%d", rate, matched, total)
    assert total > 0, "không có cửa đi nào trong 10 seed đầu — không kiểm được tỉ lệ"
    assert rate >= 0.9, f"tỉ lệ khớp cửa {rate:.2%} < 90% ({matched}/{total})"


def test_build_layer__real_seed100_pipeline_scale_within_2_percent(fake_clock: FakeClock) -> None:
    """Seed 100: `scale_source == "pipeline"`, `scale_mm_per_px` lệch đáp án ≤ 2%."""
    built, plan = _build_from_vectorized(100, fake_clock)
    assert built.scale_source == "pipeline", f"scale_source={built.scale_source}, cần suy được tỉ lệ từ chữ"
    deviation = abs(float(built.scale_mm_per_px) - plan.mm_per_px) / plan.mm_per_px
    logger.info(
        "seed=100 scale_mm_per_px=%s answer_mm_per_px=%.4f deviation=%.4f",
        built.scale_mm_per_px,
        plan.mm_per_px,
        deviation,
    )
    assert deviation <= 0.02, f"lệch mm_per_px {deviation:.2%} > 2%"
    logger.info("seed=100 dropped=%s", dict(built.dropped))
