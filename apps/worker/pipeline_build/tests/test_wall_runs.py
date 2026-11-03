"""Test `wall_runs.merge_wall_runs` (WALL-RUN): khúc thẳng hàng chạm nhau → một tường, một bề dày."""

from typing import Any

from apps.worker.pipeline_build.wall_runs import merge_wall_runs
from packages.domain.spatial import Dimension, Opening, Point, Room, Segment, SpatialLayer, Wall

_LEVEL = "L-LEVEL00000000001"
_AI: dict[str, Any] = {"confidence": 0.9, "source": "ai", "reviewed": False}

XY = tuple[int, int]


def _wall(index: int, a: XY, b: XY, measured: int, **extra: Any) -> Wall:
    """Tường AI `partition`, bề dày đo `measured`, bậc chuẩn tạm 200 (gộp phải bắt bậc lại)."""
    fields: dict[str, Any] = {
        "id": f"W-WALL{index:010d}",
        "level_id": _LEVEL,
        "centreline": Segment(start=Point(x=a[0], y=a[1]), end=Point(x=b[0], y=b[1])),
        "thickness_mm": 200,
        "detected_thickness_mm": measured,
        "height_mm": 3300,
        "kind": "partition",
        "opening_ids": (),
        **_AI,
    }
    return Wall(**(fields | extra))


def _door(index: int, wall_id: str, offset: int, swing: str = "left") -> Opening:
    """Cửa đi 900 trên `wall_id`, cách đầu tim `offset`."""
    return Opening(
        id=f"D-OPEN{index:012d}",
        wall_id=wall_id,
        kind="door",
        offset_mm=offset,
        width_mm=900,
        height_mm=2100,
        sill_height_mm=0,
        swing=swing,
        **_AI,
    )


def _room(wall_ids: tuple[str, ...]) -> Room:
    """Phòng 12 x 4 m dưới mép trên."""
    outline = (Point(x=0, y=0), Point(x=12000, y=0), Point(x=12000, y=4000), Point(x=0, y=4000))
    return Room(
        id="R-ROOM0000000001",
        level_id=_LEVEL,
        name="phòng",
        usage="other",
        outline=outline,
        area_m2=48.0,
        wall_ids=wall_ids,
        **_AI,
    )


def test_five_pieces_of_one_edge_become_one_wall_with_one_thickness() -> None:
    """f-22: mép trên 5 khúc đo 300/200/150/200/300 → một tường 0-12000, bề dày = trung vị theo độ dài (200)."""
    pieces = [
        ((0, 0), (2000, 0), 300),
        ((2000, 0), (5000, 0), 200),
        ((5000, 0), (7000, 0), 150),
        ((7000, 0), (10000, 0), 200),
        ((10000, 0), (12000, 0), 300),
    ]
    door = _door(1, "W-WALL0000000002", 500)
    walls = tuple(_wall(i, a, b, t, opening_ids=(door.id,) if i == 2 else ()) for i, (a, b, t) in enumerate(pieces))
    dim = Dimension(
        id="M-DIM0000000001",
        level_id=_LEVEL,
        kind="linear",
        reference_ids=(walls[4].id, walls[0].id),
        line=walls[0].centreline,
        value_mm=12000,
        **_AI,
    )
    layer = SpatialLayer(walls=walls, openings=(door,), rooms=(_room(tuple(w.id for w in walls)),), furniture=())
    merged, dims = merge_wall_runs(layer, (dim,))
    assert len(merged.walls) == 1
    wall = merged.walls[0]
    assert (wall.centreline.start, wall.centreline.end) == (Point(x=0, y=0), Point(x=12000, y=0))
    assert (wall.thickness_mm, wall.detected_thickness_mm, wall.opening_ids) == (200, 200, (door.id,))
    assert merged.openings[0].wall_id == wall.id
    assert merged.openings[0].offset_mm == 5500
    assert merged.rooms[0].wall_ids == (wall.id,)
    assert dims[0].reference_ids == (wall.id,)


def test_reversed_piece_moves_its_opening_and_flips_the_swing() -> None:
    """Khúc ngược chiều tường gộp: cửa cách đầu khúc 500 → cách đầu tường gộp 10000 - 500 - 900, trái thành phải."""
    long = _wall(0, (0, 0), (6000, 0), 200)
    back = _wall(1, (10000, 0), (6000, 0), 200, opening_ids=("D-OPEN000000000001",))
    door = _door(1, back.id, 500)
    merged, _ = merge_wall_runs(SpatialLayer(walls=(long, back), openings=(door,), rooms=(), furniture=()))
    assert [(o.wall_id, o.offset_mm, o.swing) for o in merged.openings] == [(long.id, 8600, "right")]


def test_pieces_that_must_stay_apart() -> None:
    """Không gộp: khác `kind` (tường bao 220 nối vách qua chữ T), khe 300 mm, khúc người vẽ, vuông góc, khúc cong."""
    walls = (
        _wall(0, (0, 0), (3000, 0), 220, kind="envelope"),
        _wall(1, (3000, 0), (6000, 0), 100),
        _wall(2, (6300, 0), (9000, 0), 100),
        _wall(3, (9000, 0), (12000, 0), 100, source="human"),
        _wall(4, (12000, 0), (12000, 3000), 100),
        _wall(5, (12000, 3000), (16000, 3000), 100, curve_offset_mm=300),
        _wall(6, (16000, 3000), (19000, 3000), 100),
    )
    layer = SpatialLayer(walls=walls, openings=(), rooms=(), furniture=())
    assert merge_wall_runs(layer) == (layer, ())


def test_overlapping_and_thin_pieces_take_the_longer_line() -> None:
    """Khúc chồng một phần và lệch tim 40 mm (< ½ bề dày) → một tường trên tim khúc dài, độ tin nhỏ nhất."""
    walls = (_wall(0, (0, 0), (5000, 0), 220), _wall(1, (4995, 40), (6000, 40), 110, confidence=0.5))
    merged, _ = merge_wall_runs(SpatialLayer(walls=walls, openings=(), rooms=(), furniture=()))
    wall = merged.walls[0]
    assert (wall.centreline.start, wall.centreline.end, wall.thickness_mm, wall.confidence) == (
        Point(x=0, y=0),
        Point(x=6000, y=0),
        220,
        0.5,
    )
