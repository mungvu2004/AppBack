"""Bước 10e: nối đầu tường lơ lửng (1 px = 10 mm, tường 220 mm = 22 px)."""

from packages.vision.walls.vectorize import _bridge_dangling_ends, _Seg


def _wall(index: int, a: tuple[float, float], b: tuple[float, float], thickness: float = 22.0) -> _Seg:
    axis = "h" if a[1] == b[1] else "v"
    return _Seg(a[0], a[1], b[0], b[1], thickness, 1.0, (1, index, 0), (1, index, 1), axis=axis)


def test_open_end_300_mm_short_of_a_wall_is_joined_to_its_centreline() -> None:
    target = _wall(0, (100.0, 0.0), (100.0, 200.0))
    stub = _wall(1, (0.0, 100.0), (59.0, 100.0))  # mặt tường đích ở x = 89: hở 30 px = 300 mm
    _bridge_dangling_ends([target, stub])
    assert (stub.bx, stub.by) == (100.0, 100.0)
    assert (stub.ax, stub.ay) == (0.0, 100.0)


def test_door_gap_900_mm_stays_open() -> None:
    target = _wall(0, (100.0, 0.0), (100.0, 200.0))
    jamb = _wall(1, (-100.0, 100.0), (-1.0, 100.0))  # hở 90 px = 900 mm
    before = (jamb.bx, jamb.by)
    _bridge_dangling_ends([target, jamb])
    assert (jamb.bx, jamb.by) == before


def test_collinear_door_gap_900_mm_stays_open() -> None:
    left = _wall(0, (0.0, 50.0), (100.0, 50.0))
    right = _wall(1, (190.0, 50.0), (300.0, 50.0))
    _bridge_dangling_ends([left, right])
    assert (left.bx, right.ax) == (100.0, 190.0)


def test_end_stops_at_the_first_wall_and_does_not_cross_it() -> None:
    first = _wall(0, (70.0, 0.0), (70.0, 200.0), thickness=10.0)
    second = _wall(1, (90.0, 0.0), (90.0, 200.0))
    stub = _wall(2, (0.0, 100.0), (40.0, 100.0))
    _bridge_dangling_ends([first, second, stub])
    assert (stub.bx, stub.by) == (70.0, 100.0)


def test_open_l_corner_is_closed_on_both_walls() -> None:
    horizontal = _wall(0, (0.0, 0.0), (80.0, 0.0))
    vertical = _wall(1, (100.0, 25.0), (100.0, 200.0))
    _bridge_dangling_ends([horizontal, vertical])
    assert (horizontal.bx, horizontal.by) == (100.0, 0.0)
    assert (vertical.ax, vertical.ay) == (100.0, 0.0)
