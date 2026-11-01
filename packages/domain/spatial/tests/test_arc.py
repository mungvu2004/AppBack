"""`arc_points`, `sagitta_through`: cung tả bằng dây + sagitta có dấu (quy ước `curveOffset` của Pascal)."""

import itertools
import math

import pytest

from packages.domain.spatial.arc import arc_points, foot_on_arc, sagitta_through, span_points


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


def test_span_points__straight_wall_gives_the_span_on_the_chord() -> None:
    """Tường thẳng: hai đầu đoạn `[low, high]` đo dọc dây."""
    assert span_points((0, 0), (1000, 0), 0, 200, 500) == [(200.0, 0.0), (500.0, 0.0)]


def test_span_points__curved_span_lies_on_the_arc_with_its_arc_length() -> None:
    """Tường cong: đỉnh đoạn nằm trên đường tròn, đầu đoạn cách đầu tường đúng 100 mm dọc cung, dài ≈ 600 mm."""
    radius = 1000**2 / (8 * 300) + 150
    centre = (500, radius - 300)
    points = span_points((0, 0), (1000, 0), 300, 100, 700)
    assert all(math.dist(point, centre) == pytest.approx(radius) for point in points)
    assert math.dist(points[0], (0, 0)) == pytest.approx(2 * radius * math.sin(50 / radius))
    assert sum(math.dist(a, b) for a, b in itertools.pairwise(points)) == pytest.approx(600, rel=0.002)


@pytest.mark.parametrize(
    ("point", "foot"), [((500, -1000), (500, -300)), ((500, 0), (500, -300)), ((2000, 300), (1000, 0))]
)
def test_foot_on_arc__radial_foot_inside_the_sweep_else_nearest_end(
    point: tuple[float, float], foot: tuple[float, float]
) -> None:
    """Đỉnh cung (500, -300): điểm cùng phương bán kính rơi xuống đỉnh; điểm ngoài góc quét về đầu mút gần."""
    assert foot_on_arc(point, (0, 0), (1000, 0), 300) == pytest.approx(foot)
