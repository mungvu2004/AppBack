"""Bước 3 của `build_walls`: px → mm, bề dày chuẩn, tường suy biến, khối cô lập (B5-05 [8] "Tường").

Đầu vào dựng tay bằng `WallPx` nên mỗi ca chỉ đo đúng một luật; `Scaling(1.0, 1.0)` cho px = mm.
"""

from collections import Counter

import pytest

from apps.worker.pipeline_build.geometry import Scaling, build_walls
from apps.worker.pipeline_build.ids import new_spatial_id
from packages.ml_contracts.artifacts import PointPx, WallPx
from packages.testing.fixtures.clock import FakeClock


def wall_px(x0: float, y0: float, x1: float, y1: float, thickness_px: float = 100.0) -> WallPx:
    """`WallPx` gọn cho test: tim tường và bề dày px, `confidence` cố định 0,9."""
    return WallPx(start=PointPx(x=x0, y=y0), end=PointPx(x=x1, y=y1), thickness_px=thickness_px, confidence=0.9)


@pytest.mark.parametrize(
    ("thickness_px", "expected_mm"),
    [(95.0, 100), (125.0, 100), (175.0, 150), (210.0, 200), (260.0, 220), (1000.0, 400)],
)
def test_build_walls__thickness_snaps_to_standard(thickness_px: float, expected_mm: int, fake_clock: FakeClock) -> None:
    """Bề dày đo bắt về `STANDARD_THICKNESSES_MM`, hoà lấy số nhỏ hơn (125 → 100, 210 → 200)."""
    dropped: Counter[str] = Counter()
    result = build_walls(
        [wall_px(0, 0, 5000, 0, thickness_px)],
        [],
        level_id=new_spatial_id("level", fake_clock),
        scaling=Scaling(1.0, 1.0),
        clock=fake_clock,
        dropped=dropped,
    )
    assert [wall.thickness_mm for wall in result.walls] == [expected_mm]
    assert result.walls[0].height_mm == 3600
    assert (result.walls[0].kind, result.walls[0].source, result.walls[0].reviewed) == ("partition", "ai", False)
    assert result.walls[0].confidence == 0.9
    assert result.input_to_wall == {0: 0}


def test_build_walls__zero_length_after_rounding_dropped(fake_clock: FakeClock) -> None:
    """Tường 0,2 px thành hai đầu trùng nhau sau `js_round` → `wallZeroLength`, không ném."""
    dropped: Counter[str] = Counter()
    result = build_walls(
        [wall_px(0, 0, 0.2, 0)],
        [],
        level_id=new_spatial_id("level", fake_clock),
        scaling=Scaling(1.0, 1.0),
        clock=fake_clock,
        dropped=dropped,
    )
    assert result.walls == ()
    assert dropped["wallZeroLength"] == 1
    assert result.input_to_wall == {}


def test_build_walls__degenerate_after_rescale_to_final(fake_clock: FakeClock) -> None:
    """`project_default` (`build` 10, `final` 1): tường 0,3 px chạm tường khác vẫn bị bỏ, không ném."""
    dropped: Counter[str] = Counter()
    result = build_walls(
        [wall_px(0, 0, 400, 0), wall_px(0, 0, 0.3, 0)],
        [],
        level_id=new_spatial_id("level", fake_clock),
        scaling=Scaling(build=10.0, final=1.0),
        clock=fake_clock,
        dropped=dropped,
    )
    assert dropped["wallZeroLength"] == 1
    assert len(result.walls) == 1
    assert result.input_to_wall == {0: 0}


def test_build_walls__isolated_block_dropped_touching_block_kept(fake_clock: FakeClock) -> None:
    """Khối ngắn xa mọi tường là `isolatedBlock`; khối ngắn cách tường ≤ `WALL_JOIN_MM` thì giữ."""
    dropped: Counter[str] = Counter()
    result = build_walls(
        [wall_px(0, 0, 5000, 0), wall_px(1000, 100, 1080, 100), wall_px(9000, 9000, 9080, 9000)],
        [],
        level_id=new_spatial_id("level", fake_clock),
        scaling=Scaling(1.0, 1.0),
        clock=fake_clock,
        dropped=dropped,
    )
    assert dropped["isolatedBlock"] == 1
    assert result.input_to_wall == {0: 0, 1: 1}


def test_build_walls__empty_input_gives_empty_set(fake_clock: FakeClock) -> None:
    """Không tường nào: `WallSet` rỗng, không dựng cây rỗng rồi ném."""
    dropped: Counter[str] = Counter()
    result = build_walls(
        [],
        [],
        level_id=new_spatial_id("level", fake_clock),
        scaling=Scaling(1.0, 1.0),
        clock=fake_clock,
        dropped=dropped,
    )
    assert (result.walls, result.openings, result.bridges) == ((), (), ())
    assert result.input_to_wall == {}


def _room(x0: float, y0: float, x1: float, y1: float) -> list[WallPx]:
    return [wall_px(x0, y0, x1, y0), wall_px(x1, y0, x1, y1), wall_px(x1, y1, x0, y1), wall_px(x0, y1, x0, y0)]


def test_build_walls__far_small_cluster_dropped_near_parts_kept(fake_clock: FakeClock) -> None:
    """U57: sơ đồ vị trí căn nhỏ cách căn > 1,5 m bị bỏ; vách trong tách rời, ban công cách 1 m vẫn giữ."""
    unit = _room(0, 0, 10000, 8000)
    partition = [wall_px(4000, 1000, 4000, 7000)]  # tách rời vì khe cửa hai đầu
    balcony = [wall_px(11000, 2000, 11000, 6000)]  # ngoài căn 1 m
    key_plan = [wall_px(14000, 6000, 15500, 6000), wall_px(15500, 6000, 15500, 7000)]  # ngoài căn 4 m
    dropped: Counter[str] = Counter()
    result = build_walls(
        unit + partition + balcony + key_plan,
        [],
        level_id=new_spatial_id("level", fake_clock),
        scaling=Scaling(1.0, 1.0),
        clock=fake_clock,
        dropped=dropped,
    )
    assert dropped["isolatedBlock"] == 2
    assert set(result.input_to_wall) == set(range(6))


def test_build_walls__far_large_cluster_kept(fake_clock: FakeClock) -> None:
    """Cụm xa nhưng không nhỏ (căn thứ hai cùng cỡ) không phải sơ đồ vị trí: giữ cả hai."""
    dropped: Counter[str] = Counter()
    result = build_walls(
        _room(0, 0, 6000, 5000) + _room(9000, 0, 15000, 5000),
        [],
        level_id=new_spatial_id("level", fake_clock),
        scaling=Scaling(1.0, 1.0),
        clock=fake_clock,
        dropped=dropped,
    )
    assert dropped["isolatedBlock"] == 0
    assert len(result.input_to_wall) == 8
