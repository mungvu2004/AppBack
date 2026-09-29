"""Khe cửa đi trên trang tổng hợp phải thành hai đầu mút tường đối diện (B5-02 khối [8]).

Dùng đáp án của `render_plan` làm chuẩn: mỗi cửa đi khoét mặt nạ nên vector hoá phải trả
hai đầu tường nhìn nhau qua khe, cách nhau đúng bề rộng khe (± 3 px). Không có mạng, không
có model — `packages.ml_contracts.synthetic` là mã test dùng chung, không phải mã gói.
"""

import itertools
import math

import pytest

from packages.ml_contracts.artifacts import BoxPx
from packages.ml_contracts.synthetic import EVAL_SET_SEEDS, render_plan
from packages.vision.walls.types import WallSegment
from packages.vision.walls.vectorize import vectorize

GAP_TOL_PX = 3.0
"""Sai số cho phép giữa khoảng hai đầu mút và bề rộng khe (khối [8])."""
CROSS_TOL_PX = 10.0
"""Đầu mút phải nằm trên tim tường chủ mới được coi là một bên của khe."""
SEEDS = tuple(EVAL_SET_SEEDS)[:10]


def _gap_axis(box: BoxPx) -> tuple[float, tuple[float, float], bool]:
    """`(bề rộng khe, tâm khe, khe chạy theo trục x)` của hộp cửa đi."""
    span_x, span_y = box.x_max - box.x_min, box.y_max - box.y_min
    centre = ((box.x_min + box.x_max) / 2.0, (box.y_min + box.y_max) / 2.0)
    return (max(span_x, span_y), centre, span_x >= span_y)


def _facing_pair(
    walls: tuple[WallSegment, ...], centre: tuple[float, float], along_x: bool
) -> tuple[float, float] | None:
    """Khoảng cách và độ lệch ngang của hai đầu mút gần tâm khe nhất, mỗi bên một cái."""
    axis, cross = (0, 1) if along_x else (1, 0)
    ends = [
        point for wall in walls for point in (wall.start, wall.end) if abs(point[cross] - centre[cross]) <= CROSS_TOL_PX
    ]
    sides = [
        sorted((p for p in ends if sign * (p[axis] - centre[axis]) > 0), key=lambda p: math.dist(p, centre))
        for sign in (-1.0, 1.0)
    ]
    if not all(sides):
        return None
    low, high = sides[0][0], sides[1][0]
    return (abs(high[axis] - low[axis]), abs(high[cross] - low[cross]))


@pytest.mark.parametrize("seed", SEEDS)
def test_door_gap_has_two_facing_wall_ends(seed: int) -> None:
    plan = render_plan(seed)
    walls = vectorize(plan.walls_mask)
    doors = [d for d in plan.detections if d.label == "door"]
    assert doors
    for door in doors:
        width, centre, along_x = _gap_axis(door.box)
        pair = _facing_pair(walls, centre, along_x)
        assert pair is not None, f"seed {seed}: không có đầu mút hai bên khe ở {centre}"
        assert abs(pair[0] - width) <= GAP_TOL_PX, f"seed {seed}: khe {width} px, đo {pair[0]} px"


@pytest.mark.parametrize("seed", SEEDS[:3])
def test_synthetic_plan_walls_stay_under_the_cap(seed: int) -> None:
    walls = vectorize(render_plan(seed).walls_mask)
    assert walls
    assert len(walls) <= 20_000
    assert all(wall.thickness_px > 0 for wall in walls)
    assert all(wall.start < wall.end or wall.start == wall.end for wall in walls)
    assert list(walls) == sorted(walls, key=lambda w: (w.start, w.end))
    assert all(a.start <= b.start for a, b in itertools.pairwise(walls))
