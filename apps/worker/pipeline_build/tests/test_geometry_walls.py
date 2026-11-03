"""Bước 3 của `build_walls`: px → mm, bề dày chuẩn, tường suy biến, khối cô lập (B5-05 [8] "Tường").

Đầu vào dựng tay bằng `WallPx` nên mỗi ca chỉ đo đúng một luật; `Scaling(1.0, 1.0)` cho px = mm.
"""

import math
from collections import Counter

import numpy as np
import pytest

from apps.worker.pipeline_build.clusters import axis_share, region_labels
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


@pytest.mark.parametrize(
    ("piece", "kept"),
    [
        pytest.param(wall_px(700, 10000, 1100, 10000), False, id="extension-line-900mm"),  # ch-13: vạch gióng
        pytest.param(wall_px(5000, 11500, 5300, 11500), False, id="beyond-1m-band"),
        pytest.param(wall_px(12500, 6000, 12500, 6400), True, id="balcony-pier-500mm"),  # song song vỏ, sát căn
        pytest.param(wall_px(5000, 5000, 5400, 5000), True, id="inside-main-box"),
    ],
)
def test_build_walls__short_piece_near_main_box(piece: WallPx, kept: bool, fake_clock: FakeClock) -> None:
    """Mẩu < 600 mm trong `FAR_CLUSTER_GAP_MM`: bỏ khi nằm trên đường gióng hay cách hộp căn > 1 m; trụ ban công
    song song vỏ cách 500 mm và mẩu trong hộp căn được giữ."""
    dropped: Counter[str] = Counter()
    result = build_walls(
        [*_room(2000, 2000, 12000, 10000), piece],
        [],
        level_id=new_spatial_id("level", fake_clock),
        scaling=Scaling(1.0, 1.0),
        clock=fake_clock,
        dropped=dropped,
    )
    assert dropped["isolatedBlock"] == (0 if kept else 1)
    assert (4 in result.input_to_wall) is kept


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


def test_build_walls__hairline_piece_dropped_unless_the_whole_plan_is_thin(fake_clock: FakeClock) -> None:
    """C2: mẩu 50 mm đo 20 mm cạnh tường thật → bỏ (không bắt lên 100); bản toàn nét mảnh thì giữ (tỉ lệ sai)."""
    dropped: Counter[str] = Counter()
    level = new_spatial_id("level", fake_clock)
    mixed = build_walls(
        [wall_px(0, 0, 5000, 0), wall_px(2000, 500, 2050, 500, 20.0)],
        [],
        level_id=level,
        scaling=Scaling(1.0, 1.0),
        clock=fake_clock,
        dropped=dropped,
    )
    thin = build_walls(
        [wall_px(0, 0, 5000, 0, 20.0)],
        [],
        level_id=level,
        scaling=Scaling(1.0, 1.0),
        clock=fake_clock,
        dropped=Counter(),
    )
    assert (len(mixed.walls), mixed.input_to_wall, dropped["isolatedBlock"]) == (1, {0: 0}, 1)
    assert [wall.thickness_mm for wall in thin.walls] == [100]


def test_build_walls__dangling_nib_dropped_real_stub_kept(fake_clock: FakeClock) -> None:
    """C2: mẩu 150 mm từ tường ra, đầu kia lơ lửng → bỏ; mẩu 350 mm đo 100 mm → giữ (tường thật)."""
    dropped: Counter[str] = Counter()
    result = build_walls(
        [wall_px(0, 0, 5000, 0), wall_px(1000, 0, 1000, 150), wall_px(3000, 0, 3000, 350)],
        [],
        level_id=new_spatial_id("level", fake_clock),
        scaling=Scaling(1.0, 1.0),
        clock=fake_clock,
        dropped=dropped,
    )
    assert result.input_to_wall == {0: 0, 2: 1}
    assert dropped["isolatedBlock"] == 1


@pytest.mark.parametrize(
    ("walls", "kept"),
    [
        pytest.param([wall_px(0, 100, 5000, 100), wall_px(1000, 47, 1000, 100)], {0: 0}, id="53-stub-in-100-body"),
        pytest.param([wall_px(0, 0, 0, 3000, 220), wall_px(0, 1000, 11, 1000)], {0: 0}, id="11-stub-in-220-body"),
        pytest.param(
            [wall_px(0, 0, 5000, 0), wall_px(0, 150, 5000, 150), wall_px(2000, 0, 2000, 150)],
            {0: 0, 1: 1, 2: 2},
            id="150-connector-kept",
        ),
    ],
)
def test_build_walls__nib_buried_in_one_wall_dropped(
    walls: list[WallPx], kept: dict[int, int], fake_clock: FakeClock
) -> None:
    """W4: mẩu < 200 mm có cả hai đầu trong thân cùng một tường → bỏ; mẩu nối hai tường song song → giữ."""
    result = build_walls(
        walls,
        [],
        level_id=new_spatial_id("level", fake_clock),
        scaling=Scaling(1.0, 1.0),
        clock=fake_clock,
        dropped=Counter(),
    )
    assert result.input_to_wall == kept


def _spoke(x: float, y: float, degrees: float, length: float) -> WallPx:
    angle = math.radians(degrees)
    return wall_px(x, y, x + length * math.cos(angle), y + length * math.sin(angle))


@pytest.mark.parametrize(
    ("second", "kept"),
    [
        # phối cảnh 3D: một cụm cạnh tản 0/20/35/60/75° (mod 90), mỗi hướng 1/5 chiều dài → axis_share 0,2
        pytest.param([_spoke(20000, 0, a, 5000) for a in (0, 20, 35, 60, 75)], False, id="perspective"),
        # căn thứ hai xoay 30°: mọi tường theo một cặp hướng vuông góc → giữ
        pytest.param([_spoke(20000, 0, 30, 6000), _spoke(20000, 0, 120, 5000)], True, id="rotated-plan"),
        pytest.param(_room(20000, 0, 26000, 5000), True, id="second-unit"),
    ],
)
def test_build_walls__far_region_off_axis_dropped(second: list[WallPx], kept: bool, fake_clock: FakeClock) -> None:
    """B3: vùng phụ lớn (~ cỡ căn chính) mà phần lớn chiều dài không theo một cặp hướng vuông góc → bỏ cả vùng."""
    dropped: Counter[str] = Counter()
    result = build_walls(
        _room(0, 0, 8000, 6000) + second,
        [],
        level_id=new_spatial_id("level", fake_clock),
        scaling=Scaling(1.0, 1.0),
        clock=fake_clock,
        dropped=dropped,
    )
    assert dropped["isolatedBlock"] == (0 if kept else len(second))
    assert set(result.input_to_wall) >= set(range(4))
    assert (len(result.input_to_wall) == 4 + len(second)) is kept


@pytest.mark.parametrize(("gap", "joined"), [(2000, False), (1200, True)])
def test_build_walls__no_join_across_paper_between_units(gap: int, joined: bool, fake_clock: FakeClock) -> None:
    """B4: hai căn thẳng hàng cách khe giấy > `FAR_CLUSTER_GAP_MM` là hai vùng → 3b không nối tường qua khe (dù khe
    ≤ `OPENING_GAP_MAX_MM`); khe ≤ 1,5 m (ô cửa) vẫn nối như cũ."""
    result = build_walls(
        _room(0, 0, 6000, 5000) + _room(6000 + gap, 0, 12000 + gap, 5000),
        [],
        level_id=new_spatial_id("level", fake_clock),
        scaling=Scaling(1.0, 1.0),
        clock=fake_clock,
        dropped=Counter(),
    )
    spans = [abs(wall.centreline.end.x - wall.centreline.start.x) for wall in result.walls]
    assert (bool(result.bridges) or max(spans) > 6000) is joined


@pytest.mark.parametrize(
    ("degrees", "share"),
    [((89.0, 2.0), 1.0), ((30.0, 120.0), 1.0), ((0.0, 90.0, 30.0, 120.0), 0.5), ((0.0, 20.0, 35.0, 60.0, 75.0), 0.2)],
)
def test_axis_share__mod_90_window(degrees: tuple[float, ...], share: float) -> None:
    """Cửa sổ ±4° quanh hướng trội, góc mod 90: 89° và 2° cùng họ (vòng qua 0); bản xoay 30° thẳng trục với chính nó."""
    vectors = np.asarray([(math.cos(math.radians(a)), math.sin(math.radians(a))) for a in degrees])
    assert axis_share(vectors) == pytest.approx(share)


def test_region_labels__same_chain_as_multiple_plans() -> None:
    """Chuỗi `grow_region` từ cụm dài nhất: hộp 2 cách hộp 0 2 m (không nuốt) nhưng cách hộp 1 1,4 m → vùng của hộp 1;
    hộp 0 và 1 cách 2 m vẫn là hai vùng (không gộp vì vùng sau lớn tới gần vùng trước)."""
    boxes = [(0.0, 0.0, 6000.0, 5000.0), (8000.0, -1000.0, 14000.0, 5000.0), (3000.0, -4000.0, 7000.0, -2000.0)]
    assert region_labels(boxes, [3.0, 2.0, 1.0]) == [0, 1, 1]
    assert region_labels([*boxes, (6500.0, 0.0, 7500.0, 100.0)], [3.0, 2.0, 1.0, 1.0]) == [0, 0, 0, 0]
