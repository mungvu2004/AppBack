"""Tường cong qua bước dựng tầng: `explode_arcs` → bước 3-6 trên dây → `join_arcs` gộp lại một tường."""

import itertools
import math
from datetime import UTC, datetime

import pytest

from apps.worker.pipeline_build.arcs import explode_arcs, join_arcs
from apps.worker.pipeline_build.geometry import WallSet
from apps.worker.pipeline_build.ids import new_spatial_id
from apps.worker.pipeline_build.tests.helpers import SPATIAL_LEVEL_ID, build_wrapped
from packages.domain.spatial import Point, Segment, Wall
from packages.ml_contracts.artifacts import BoxPx, DetectionPx, PointPx, WallPx
from packages.testing.fixtures.clock import FakeClock

_T = 22.0
"""Bề dày tường mẫu (px); 10 mm/px → 220 mm."""
_START = datetime(2026, 1, 1, tzinfo=UTC)


def _wall(ax: float, ay: float, bx: float, by: float, sagitta: float = 0.0) -> WallPx:
    """Một `WallPx` bề dày `_T`, độ tin 0,9."""
    return WallPx(
        start=PointPx(x=ax, y=ay), end=PointPx(x=bx, y=by), thickness_px=_T, confidence=0.9, sagitta_px=sagitta
    )


def _room_with_bay() -> list[WallPx]:
    """Phòng 300 x 400 px, cạnh phải mở ra ban công cong lồi sang phải 60 px (đỉnh cung ở (460, 300)).

    Cung rộng để dây nổ ra (≤ 10°) vẫn dài hơn ô mở hẹp nhất ở tỉ lệ dựng ước từ bề dày (~6,8 mm/px).
    """
    return [
        _wall(100, 100, 400, 100),
        _wall(100, 100, 100, 500),
        _wall(100, 500, 400, 500),
        _wall(400, 100, 400, 500),
        _wall(400, 100, 400, 500, sagitta=60.0),
    ]


def test_build_layer__curved_wall_is_one_wall_with_its_window() -> None:
    """Ban công cong ra MỘT tường `curveOffsetMm`, cửa sổ ở đỉnh cung gắn vào nó, phòng ban công trỏ tới nó."""
    window = DetectionPx(label="window", box=BoxPx(x_min=445, y_min=270, x_max=475, y_max=330), confidence=0.9)
    built = build_wrapped(
        walls=_room_with_bay(), detections=[window], width_px=600, height_px=600, clock=FakeClock(start=_START)
    )
    curved = [wall for wall in built.layer.walls if wall.curve_offset_mm]
    assert len(curved) == 1
    wall = curved[0]
    assert {(wall.centreline.start.x, wall.centreline.end.x)} == {(4000, 4000)}
    assert abs(abs(wall.curve_offset_mm) - 600) <= 2
    assert len(built.layer.walls) == 5
    (opening,) = built.layer.openings
    assert opening.wall_id == wall.id
    assert wall.opening_ids == (opening.id,)
    arc_mm = 4 * math.atan(2 * 600 / 4000) * (4000**2 / 4800 + 300)
    # Ô mở còn bị kẹp trong MỘT dây (8 dây, NO-432): tâm cách đỉnh cung không quá một dây.
    assert abs(opening.offset_mm + opening.width_mm / 2 - arc_mm / 2) <= arc_mm / 8
    assert any(wall.id in room.wall_ids for room in built.layer.rooms)
    assert all(len(set(room.wall_ids)) == len(room.wall_ids) for room in built.layer.rooms)
    assert b'"curveOffsetMm"' in built.to_json()


def test_explode_arcs__straight_walls_pass_through() -> None:
    """Không có tường cong: y nguyên đầu vào, không cung nào; `join_arcs` trả nguyên đối số."""
    walls = _room_with_bay()[:4]
    exploded, arc_of = explode_arcs(walls)
    assert exploded == tuple(walls)
    assert arc_of == (None,) * 4
    empty = WallSet((), (), {}, ())
    assert join_arcs(empty, (), arc_of) == (empty, ())


def _chords(*points: tuple[int, int]) -> tuple[Wall, ...]:
    """Các `Wall` nối đuôi qua `points` (mm), id theo thứ tự."""
    clock = FakeClock(start=_START)
    return tuple(
        Wall(
            id=new_spatial_id("wall", clock),
            level_id=SPATIAL_LEVEL_ID,
            centreline=Segment(start=Point(x=ax, y=ay), end=Point(x=bx, y=by)),
            thickness_mm=220,
            height_mm=2700,
            kind="partition",
            opening_ids=(),
            confidence=0.9,
            source="ai",
            reviewed=False,
        )
        for (ax, ay), (bx, by) in itertools.pairwise(points)
    )


@pytest.mark.parametrize(
    ("points", "input_to_wall"),
    [
        pytest.param([(0, 0), (500, 200), (1000, 0), (1500, -300)], {0: 0, 1: 1, 2: 2}, id="odd-chord-count"),
        pytest.param([(0, 0), (500, 200), (1000, 0)], {0: 0, 1: 0}, id="chords-fused"),
        pytest.param([(0, 0), (500, 200), (1000, 0)], {0: 0}, id="chord-dropped"),
    ],
)
def test_join_arcs__keeps_chords_when_the_chain_is_not_whole(
    points: list[tuple[int, int]], input_to_wall: dict[int, int]
) -> None:
    """Số dây lẻ, hai dây gộp làm một hay một dây mất: không đoán cung, giữ nguyên các dây."""
    walls = _chords(*points)
    wall_set = WallSet(walls, (), input_to_wall, ())
    assert join_arcs(wall_set, (), (0,) * (len(points) - 1)) == (wall_set, ())


def test_join_arcs__keeps_chords_that_no_longer_meet() -> None:
    """Hai dây không còn chung đỉnh (bước 3b kéo một đầu đi): giữ nguyên."""
    first, second = _chords((0, 0), (500, 200), (1000, 0))
    moved = second.model_copy(update={"centreline": Segment(start=Point(x=510, y=200), end=Point(x=1000, y=0))})
    wall_set = WallSet((first, moved), (), {0: 0, 1: 1}, ())
    assert join_arcs(wall_set, (), (0, 0)) == (wall_set, ())
