"""Bước 7 của `build_layer` (B5-05 [6]): `Dimension` từ mẫu tỉ lệ, tối đa một mỗi chữ.

Hình học dựng tay: tường ngang 1000 px chia đôi bởi một vách dọc, nên `wall_spans` cho hai nhịp
500 px; ở 5 mm/px mỗi nhịp là 2500 mm và cả tường là 5000 mm.
"""

from collections.abc import Sequence
from decimal import Decimal

import pytest

from apps.worker.pipeline_build.build import BuiltLayer, _SpanIndex
from apps.worker.pipeline_build.tests.helpers import build_wrapped
from packages.domain.spatial import Dimension
from packages.ml_contracts.artifacts import (
    BoxPx,
    PointPx,
    TextPx,
    WallPx,
)
from packages.ml_contracts.synthetic import render_plan
from packages.testing.fixtures.clock import FakeClock
from packages.vision.dimensions import wall_spans

LEVEL_ID = "L-0000000000000000000000001"
MAIN_WALL = WallPx(start=PointPx(x=100.0, y=100.0), end=PointPx(x=1100.0, y=100.0), thickness_px=20.0, confidence=0.9)
CROSS_WALL = WallPx(start=PointPx(x=600.0, y=100.0), end=PointPx(x=600.0, y=700.0), thickness_px=20.0, confidence=0.9)
TEXT_CONFIDENCE = 0.7


def _text(value: str, centre_x: float, centre_y: float = 145.0) -> TextPx:
    """Chữ kích thước nằm ngang (rộng ≥ cao nên chỉ ghép với tường ngang), cao 30 px."""
    return TextPx(
        text=value,
        box=BoxPx(x_min=centre_x - 50, y_min=centre_y - 15, x_max=centre_x + 50, y_max=centre_y + 15),
        confidence=TEXT_CONFIDENCE,
    )


def _run(texts: Sequence[TextPx], clock: FakeClock) -> BuiltLayer:
    """`build_layer` trên hình học dựng tay ở trên, `fallback` 5 mm/px."""
    return build_wrapped(
        walls=(MAIN_WALL, CROSS_WALL),
        texts=texts,
        width_px=1600,
        height_px=1200,
        fallback_mm_per_px=Decimal("5"),
        clock=clock,
        level_id=LEVEL_ID,
    )


def _texts() -> tuple[TextPx, ...]:
    """Bốn chữ: nhịp trái, chữ tổng giữa, nhịp phải, và một chữ đọc hỏng (mẫu ngoại lai)."""
    return (_text("2500", 350.0), _text("5000", 500.0), _text("2500", 850.0), _text("9999", 400.0, 185.0))


def _length_mm(dimension: Dimension) -> float:
    """Chiều dài `line` của một kích thước, mm (để đối chiếu với `valueMm`)."""
    line = dimension.line
    return float(abs(line.end.x - line.start.x) + abs(line.end.y - line.start.y))


def test_build_layer__dimension_per_text_at_most_one(fake_clock: FakeClock) -> None:
    """Chữ nhịp và chữ tổng cùng tường → mỗi chữ tối đa một `Dimension`, `line` đúng nhịp."""
    built = _run(_texts(), fake_clock)
    assert built.scale_source == "pipeline"
    assert len(built.dimensions) == 3
    assert sorted(item.value_mm for item in built.dimensions) == [2500, 2500, 5000]
    for dimension in built.dimensions:
        ratio = _length_mm(dimension) / dimension.value_mm
        assert abs(ratio - 1.0) <= 0.02


def test_build_layer__dimension_references_its_wall(fake_clock: FakeClock) -> None:
    """`referenceIds` là đúng tường mang mẫu, `confidence` là min của chữ và tường."""
    built = _run(_texts(), fake_clock)
    wall_id = built.layer.walls[0].id
    assert {item.reference_ids for item in built.dimensions} == {(wall_id,)}
    assert {item.confidence for item in built.dimensions} == {TEXT_CONFIDENCE}
    assert {(item.kind, item.source, item.reviewed) for item in built.dimensions} == {("linear", "ai", False)}


def test_build_layer__rejected_outlier_makes_no_dimension(fake_clock: FakeClock) -> None:
    """Chữ `9999` cho mẫu gấp đôi tỉ lệ, bị `infer_scale` loại → `dimensionUnpaired`, không dựng."""
    built = _run(_texts(), fake_clock)
    assert built.dropped["dimensionUnpaired"] == 1
    assert all(item.value_mm != 9999 for item in built.dimensions)


def test_build_layer__no_dimension_when_scale_is_project_default(fake_clock: FakeClock) -> None:
    """Tỉ lệ đến từ `fallback` thì mẫu không đáng tin → không `Dimension` nào (bước 7)."""
    built = _run([_text("2500", 350.0)], fake_clock)
    assert built.scale_source == "project_default"
    assert built.dimensions == ()


@pytest.mark.parametrize("value", ["2500", "5000"])
def test_build_layer__dimension_value_matches_text(value: str, fake_clock: FakeClock) -> None:
    """`valueMm` là số mm đọc từ chữ, không phải chiều dài tính lại từ pixel."""
    built = _run(_texts(), fake_clock)
    assert any(item.value_mm == int(value) for item in built.dimensions)


def test_span_index__matches_wall_spans_on_seed_100() -> None:
    """Tập con láng giềng cho đúng điểm chia của `wall_spans(walls)` (tối ưu bước 7, O(n) thay O(n²))."""
    walls = render_plan(100).walls
    index = _SpanIndex.of(walls)
    expected = wall_spans(walls)
    assert [index.spans(j) for j in range(len(walls))] == list(expected)


def test_build_layer__whole_wall_line_comes_from_input_wall(fake_clock: FakeClock) -> None:
    """Mẫu `sall` lấy đường tim tường **gốc** (đổi px → mm), cùng đại lượng với `valueMm` (F3).

    Tường gộp ở 3b dài hơn tường vào, nên `Wall.centreline` của tường giữ không dùng được.
    """
    (whole,) = [item for item in _run(_texts(), fake_clock).dimensions if item.value_mm == 5000]
    assert (whole.line.start.x, whole.line.start.y) == (500, 500)
    assert (whole.line.end.x, whole.line.end.y) == (5500, 500)
