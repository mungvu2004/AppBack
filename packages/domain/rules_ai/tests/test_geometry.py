"""Hình học: khe tới mặt tường (cùng số với FE), điểm trong đa giác, tâm diện tích, phân loại tường."""

import pytest

from packages.domain.rules_ai.geometry import (
    bounds_of,
    cell_keys,
    centroid,
    gap_to_wall_face,
    in_bounds,
    nearest_probe,
    outline_contains,
    probe_points,
    wall_side,
)
from packages.domain.rules_ai.tests.builders import box_room, furniture, rectangle, wall
from packages.domain.spatial import BoundingBox, Point, Room

# Vỏ nhà 6 x 4 m của `fitout.test.ts`: tường ngoài dày 220, mặt tường đông ở x = 6000 - 110.
EAST = wall(1, (6000, 0), (6000, 4000), kind="envelope", thickness=220)


def _box(centre_x: int, centre_y: int, size: int = 600) -> BoundingBox:
    """Hộp vuông cạnh `size` quanh tâm (test chỉ cần hộp, không cần đồ đạc)."""
    return furniture(1, (centre_x, centre_y), size=size).bounding_box


@pytest.mark.parametrize(
    ("centre_x", "size", "expected"),
    [
        (5590, 600, 0.0),  # cạnh hộp đúng trên mặt tường (`fitout.test.ts:348-357`)
        (5540, 600, 50.0),  # lệch 50 mm: đúng dung sai, còn tính là áp tường
        (5530, 600, 60.0),  # lệch 60 mm: vượt dung sai 10 mm
        (5900, 200, 0.0),  # đo tới mặt tường chứ không tới đường tim (`:369-382`): trong thân tường thì 0
        (7000, 600, 590.0),  # phía ngoài, hộp cách đường tim 700, trừ nửa bề dày 110
    ],
)
def test_gap_to_wall_face__matches_fe_cases(centre_x: int, size: int, expected: float) -> None:
    """Các ca khe của FE cho cùng số: trong/ngoài dung sai, đo tới mặt tường, không bao giờ âm."""
    assert gap_to_wall_face(_box(centre_x, 2000, size), EAST) == expected


def test_probe_points__order_is_min_corner_first_then_centre() -> None:
    """Bốn góc theo thứ tự `min`, `(max.x, min.y)`, `max`, `(min.x, max.y)` rồi tâm hộp."""
    box = _box(1000, 2000, 200)
    assert probe_points(box) == ((900, 1900), (1100, 1900), (1100, 2100), (900, 2100), (1000.0, 2000.0))


def test_nearest_probe__tie_keeps_the_earlier_probe() -> None:
    """Hai góc cùng cách tường: điểm dò đứng trước (góc `min`) thắng, chân rơi xuống đường tim."""
    horizontal = wall(1, (0, 0), (1000, 0))
    near = nearest_probe(BoundingBox(min=Point(x=100, y=100), max=Point(x=200, y=200)), horizontal)
    assert (near.distance, near.probe, near.foot) == (100.0, (100, 100), (100.0, 0.0))


def test_nearest_probe__foot_clamps_to_the_endpoint() -> None:
    """Điểm dò ngoài đầu mút: chân là chính đầu mút, khoảng cách là khoảng tới đầu mút."""
    horizontal = wall(1, (0, 0), (1000, 0))
    near = nearest_probe(BoundingBox(min=Point(x=1300, y=-400), max=Point(x=1400, y=-300)), horizontal)
    assert near.foot == (1000.0, 0.0)
    assert near.distance == pytest.approx(300 * 2**0.5)  # góc (min.x, max.y) gần đầu mút nhất


_U_SHAPE = (
    Point(x=0, y=0),
    Point(x=3000, y=0),
    Point(x=3000, y=3000),
    Point(x=2000, y=3000),
    Point(x=2000, y=1000),
    Point(x=1000, y=1000),
    Point(x=1000, y=3000),
    Point(x=0, y=3000),
)


@pytest.mark.parametrize(
    ("outline", "x", "y", "expected"),
    [
        (rectangle((0, 0), (4000, 4000)), 2000, 2000, True),
        (rectangle((0, 0), (4000, 4000)), 5000, 2000, False),
        (rectangle((0, 0), (4000, 4000)), 2000, -1, False),
        (rectangle((0, 0), (4000, 4000)), 0, 2000, True),  # cạnh trái: tia đông còn cắt cạnh phải
        (rectangle((0, 0), (4000, 4000)), 4000, 2000, False),  # cạnh phải: không cắt gì nữa
        (_U_SHAPE, 500, 2000, True),  # cánh trái của chữ U
        (_U_SHAPE, 1500, 2000, False),  # trong khe lõm
        (_U_SHAPE, 2500, 2000, True),  # cánh phải
        (_U_SHAPE, 1500, 500, True),  # đáy chữ U
        (_U_SHAPE, 1500, 3500, False),  # phía trên khe
        (rectangle((-3000, -3000), (-1000, -1000)), -2000.5, -2000, True),  # toạ độ âm, số thực
    ],
)
def test_outline_contains__matches_fe_ray_cast(outline: tuple[Point, ...], x: float, y: float, expected: bool) -> None:
    """Bắn tia đông: trong, ngoài, lõm chữ U, điểm trên cạnh (không hứa bên nào), số âm — như `outlineContains`."""
    assert outline_contains(outline, x, y) is expected


def test_centroid__rectangle_l_shape_and_degenerate() -> None:
    """Chữ nhật → tâm hình học; chữ L → tâm có trọng số; ba điểm thẳng hàng → trung bình đỉnh như FE."""
    assert centroid(rectangle((0, 0), (4000, 2000))) == (2000.0, 1000.0)
    l_shape = (
        Point(x=0, y=0),
        Point(x=2000, y=0),
        Point(x=2000, y=1000),
        Point(x=1000, y=1000),
        Point(x=1000, y=2000),
        Point(x=0, y=2000),
    )
    assert centroid(l_shape) == pytest.approx((5000 / 6, 5000 / 6))
    assert centroid((Point(x=0, y=0), Point(x=1000, y=0), Point(x=2000, y=0))) == (1000.0, 0.0)


def test_centroid__clockwise_outline_gives_the_same_centre() -> None:
    """Đường bao theo chiều kim đồng hồ: dấu diện tích và dấu tích chéo triệt tiêu nhau."""
    assert centroid(tuple(reversed(rectangle((0, 0), (4000, 2000))))) == (2000.0, 1000.0)


def test_bounds_and_cells__floor_division_covers_negative_coordinates() -> None:
    """Hộp bao, phép thử điểm-trong-hộp (tính cả biên) và ô lưới làm tròn xuống cả số âm."""
    bounds = bounds_of(rectangle((-1500, 200), (900, 2100)))
    assert bounds == (-1500, 200, 900, 2100)
    assert in_bounds(bounds, -1500, 2100)
    assert not in_bounds(bounds, -1501, 200)
    assert not in_bounds(bounds, 0, 2101)
    assert sorted(cell_keys((-1500, 200, 900, 2100), 1000)) == [(x, y) for x in (-2, -1, 0) for y in (0, 1, 2)]
    assert sorted(cell_keys((-1000, 0, -1000, 0), 1000)) == [(-1, 0)]


def _two_rooms() -> tuple[Room, Room]:
    """Hai phòng kề nhau 4 x 4 m dọc trục x."""
    return box_room(1, (0, 0), (4000, 4000)), box_room(2, (4000, 0), (8000, 4000))


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        ((0, 0), (4000, 0), "exterior"),  # mép ngoài phòng 1: một bên trong, một bên ngoài
        ((4000, 0), (4000, 4000), "interior"),  # giữa hai phòng: hai bên đều trong phòng
        ((0, 6000), (4000, 6000), "unknown"),  # xa mọi phòng: không bên nào
    ],
)
def test_wall_side__exterior_interior_unknown(start: tuple[int, int], end: tuple[int, int], expected: str) -> None:
    """Đúng một bên trong phòng → ngoài; hai bên → trong; không bên nào → chưa rõ."""
    assert wall_side(wall(1, start, end), _two_rooms()) == expected


def test_wall_side__no_rooms_is_unknown() -> None:
    """Lớp chưa có phòng nào: không kết luận được gì."""
    assert wall_side(wall(1, (0, 0), (4000, 0)), ()) == "unknown"
