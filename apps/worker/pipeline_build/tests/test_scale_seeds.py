"""Tỉ lệ `s_dựng` trên 10 seed đầu và ảnh hưởng của `fallback_mm_per_px` (B5-05 việc E, khối [8]).

`s_dựng` được tính lại độc lập với mã dựng (`clamp(150 / trung vị thickness_px, 1, 200)`), không
nhập nội bộ của A. Không nhập `apps.ml.*`, không đọc DB.
"""

import logging
import statistics
from datetime import UTC, datetime
from decimal import Decimal
from typing import Final

import pytest

from apps.worker.pipeline_build.build import BuiltLayer, build_layer
from apps.worker.pipeline_build.ids import new_spatial_id
from packages.domain.scale.rescale import rescale_unreviewed
from packages.ml_contracts.artifacts import BoxPx, DetectionPx, ObjectsResult, TextPx, TextResult, WallPx, WallsResult
from packages.ml_contracts.synthetic import EVAL_SET_SEEDS, SyntheticPlan, render_plan
from packages.testing.fixtures.clock import FakeClock

logger = logging.getLogger(__name__)

_FIRST_TEN_SEEDS: Final = tuple(range(100, 110))
_LEVEL_ID: Final = new_spatial_id("level", FakeClock(start=datetime(2026, 1, 1, tzinfo=UTC)))
_IMAGE_WIDTH_PX = 1600
_IMAGE_HEIGHT_PX = 1200


def _s_dung(walls: tuple[WallPx, ...]) -> float:
    """`clamp(150 / trung vị thickness_px, 1, 200)` — công thức [8], tính lại trong test."""
    median_thickness = statistics.median(wall.thickness_px for wall in walls)
    return min(max(150 / median_thickness, 1.0), 200.0)


def _ratio(plan: SyntheticPlan) -> float:
    """`s_dựng / mm_per_px` đáp án của một trang tổng hợp."""
    return _s_dung(plan.walls) / plan.mm_per_px


def _out_of_range_seeds() -> tuple[int, ...]:
    """Seed của `EVAL_SET_SEEDS` có tỉ số `s_dựng/mm_per_px` ∉ [0.9, 1.1] (tính ở lúc nạp module)."""
    return tuple(seed for seed in EVAL_SET_SEEDS if not 0.9 <= _ratio(render_plan(seed)) <= 1.1)


_OUT_OF_RANGE_SEEDS: Final = _out_of_range_seeds()


def _build(
    plan: SyntheticPlan,
    *,
    walls: tuple[WallPx, ...] | None = None,
    detections: tuple[DetectionPx, ...] = (),
    texts: tuple[TextPx, ...] = (),
    fallback_mm_per_px: Decimal,
    clock: FakeClock,
) -> BuiltLayer:
    """Dựng `BuiltLayer` từ một `SyntheticPlan`, cho phép ghi đè tường/phát hiện/chữ."""
    return build_layer(
        level_id=_LEVEL_ID,
        walls=WallsResult(walls=walls if walls is not None else plan.walls),
        objects=ObjectsResult(detections=detections or plan.detections),
        text=TextResult(items=texts),
        width_px=plan.pixels.shape[1],
        height_px=plan.pixels.shape[0],
        fallback_mm_per_px=fallback_mm_per_px,
        clock=clock,
    )


@pytest.mark.parametrize("seed", _FIRST_TEN_SEEDS)
def test_scale_ratio__first_ten_seeds(seed: int) -> None:
    """Log `s_dựng / mm_per_px` của 10 seed đầu (khối [11] mục 3); `s_dựng` phải dương."""
    plan = render_plan(seed)
    s_dung = _s_dung(plan.walls)
    ratio = s_dung / plan.mm_per_px
    logger.info("seed=%d s_dung=%.4f mm_per_px=%.4f ratio=%.4f", seed, s_dung, plan.mm_per_px, ratio)
    assert s_dung > 0


def _assert_fallback_covers_pipeline(seed: int, fallback: Decimal, clock: FakeClock) -> None:
    """`fallback_mm_per_px` bằng `fallback`, `text` rỗng: số phòng/ô mở ≥ 90 % lượt `pipeline` cùng seed."""
    plan = render_plan(seed)
    pipeline_built = _build(plan, fallback_mm_per_px=Decimal("1"), clock=FakeClock(start=clock.now()))
    fallback_built = _build(plan, texts=(), fallback_mm_per_px=fallback, clock=FakeClock(start=clock.now()))
    pipeline_rooms, pipeline_openings = len(pipeline_built.layer.rooms), len(pipeline_built.layer.openings)
    fallback_rooms, fallback_openings = len(fallback_built.layer.rooms), len(fallback_built.layer.openings)
    assert fallback_rooms >= 0.9 * pipeline_rooms, (
        f"seed {seed} fallback={fallback}: {fallback_rooms} phòng < 90% của {pipeline_rooms}"
    )
    assert fallback_openings >= 0.9 * pipeline_openings, (
        f"seed {seed} fallback={fallback}: {fallback_openings} ô mở < 90% của {pipeline_openings}"
    )


@pytest.mark.parametrize("seed", _OUT_OF_RANGE_SEEDS)
@pytest.mark.parametrize("fallback", [Decimal("1"), Decimal("10")])
def test_scale_fallback__out_of_range_seed_covers_pipeline(seed: int, fallback: Decimal, fake_clock: FakeClock) -> None:
    """Trên seed có tỉ số `s_dựng/mm_per_px` ngoài [0.9, 1.1]: fallback 1 và 10 vẫn phủ ≥ 90% lượt pipeline."""
    _assert_fallback_covers_pipeline(seed, fallback, fake_clock)


_GRID_REFERENCE_ROOMS = 2
_GRID_REFERENCE_OPENINGS = 1


def _hand_built_grid_walls(thickness_px: float) -> tuple[WallPx, ...]:
    """Lưới hai phòng dựng tay, trong ảnh 1600x1200 px (lề 200 px): hình chữ nhật 200..1400 x
    200..800 chia đôi bằng một vách giữa `x = 800`.

    `thickness_px` chọn để với `fallback_mm_per_px = 10` mọi vách ra đúng 110 mm thật (đáp án).
    """

    def _wall(x0: float, y0: float, x1: float, y1: float) -> WallPx:
        """Một cạnh của lưới, đường tim `(x0,y0)`→`(x1,y1)`, bề dày `thickness_px` chung."""
        return WallPx(start={"x": x0, "y": y0}, end={"x": x1, "y": y1}, thickness_px=thickness_px, confidence=0.99)

    return (
        _wall(200, 200, 1400, 200),
        _wall(200, 800, 1400, 800),
        _wall(200, 200, 200, 800),
        _wall(1400, 200, 1400, 800),
        _wall(800, 200, 800, 800),
    )


def _hand_built_grid_door() -> DetectionPx:
    """Một cửa đi trên vách giữa `x = 800`, tâm hộp khớp tâm vách theo chiều dọc."""
    return DetectionPx(label="door", box=BoxPx(x_min=780, y_min=450, x_max=820, y_max=550), confidence=0.9)


@pytest.mark.parametrize("fallback", [Decimal("1"), Decimal("10")])
def test_scale_fallback__hand_built_110mm_grid(fallback: Decimal, fake_clock: FakeClock) -> None:
    """Lưới dựng tay 2 phòng trong ảnh, vách 110 mm thật, 1 cửa: fallback 1 và 10 đều ra ≥ 90% tham chiếu."""
    walls = _hand_built_grid_walls(thickness_px=11.0)
    plan = render_plan(next(iter(EVAL_SET_SEEDS)))  # chỉ mượn kích thước ảnh mặc định
    built = _build(
        plan,
        walls=walls,
        detections=(_hand_built_grid_door(),),
        texts=(),
        fallback_mm_per_px=fallback,
        clock=fake_clock,
    )
    assert built.dropped["outOfImage"] == 0, f"fallback={fallback}: {built.dropped}"
    assert len(built.layer.rooms) >= 0.9 * _GRID_REFERENCE_ROOMS, (
        f"fallback={fallback}: {len(built.layer.rooms)} phòng < 90% của {_GRID_REFERENCE_ROOMS}"
    )
    assert len(built.layer.openings) >= 0.9 * _GRID_REFERENCE_OPENINGS, (
        f"fallback={fallback}: {len(built.layer.openings)} ô mở < 90% của {_GRID_REFERENCE_OPENINGS}"
    )
    rescale_unreviewed(built.layer, float(built.scale_mm_per_px), 10.0)


@pytest.mark.parametrize("seed", _FIRST_TEN_SEEDS)
def test_rescale_unreviewed__fallback_to_answer_scale_does_not_raise(seed: int, fake_clock: FakeClock) -> None:
    """Dựng bằng fallback rồi `rescale_unreviewed` về `mm_per_px` đáp án: không ném (K19 dựng, không đoán khi đổi)."""
    plan = render_plan(seed)
    built = _build(plan, texts=(), fallback_mm_per_px=Decimal("10"), clock=fake_clock)
    rescale_unreviewed(built.layer, float(built.scale_mm_per_px), plan.mm_per_px)
