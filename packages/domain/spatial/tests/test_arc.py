"""`arc_points`, `sagitta_through`: cung tả bằng dây + sagitta có dấu (quy ước `curveOffset` của Pascal)."""

import itertools
import math

import pytest

from packages.domain.spatial.arc import arc_points, sagitta_through


@pytest.mark.parametrize("sagitta", [400.0, -400.0, 1000.0, 30.0])
def test_arc_points__lie_on_one_circle_and_give_the_sagitta_back(sagitta: float) -> None:
    """Đỉnh đều trên một đường tròn, giữ hai đầu, số dây chẵn, đỉnh giữa trả lại đúng sagitta; dây ≤ 10°."""
    start, end = (0.0, 0.0), (2000.0, 0.0)
    points = arc_points(start, end, sagitta)
    assert (points[0], points[-1]) == (start, end)
    assert len(points) % 2 == 1
    assert sagitta_through(start, points[len(points) // 2], end) == pytest.approx(sagitta)
    radius = 2000.0**2 / (8 * abs(sagitta)) + abs(sagitta) / 2
    for one, two in itertools.pairwise(points):
        assert 2 * math.degrees(math.asin(math.dist(one, two) / (2 * radius))) <= 10.0 + 1e-9


def test_arc_points__positive_sagitta_bulges_against_the_left_normal() -> None:
    """Dây (0,0)→(2000,0), pháp tuyến (0, 1): sagitta 1000 là nửa vòng đỉnh (1000, -1000), như Pascal."""
    points = arc_points((0.0, 0.0), (2000.0, 0.0), 1000.0)
    apex = points[len(points) // 2]
    assert apex == pytest.approx((1000.0, -1000.0))


@pytest.mark.parametrize(("start", "end"), [((0.0, 0.0), (10.0, 0.0)), ((5.0, 5.0), (5.0, 5.0))])
def test_arc_points__straight_or_empty_is_just_the_ends(start: tuple[float, float], end: tuple[float, float]) -> None:
    """Sagitta 0 hay dây rỗng: chỉ hai đầu."""
    assert arc_points(start, end, 0.0 if start != end else 3.0) == [start, end]
