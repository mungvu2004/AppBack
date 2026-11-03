"""Test thuần của `checks.geometry_checks` (BENCH3D-01): lớp dựng tay, không DB."""

from decimal import Decimal

import pytest

from apps.worker.pipeline_quality.checks import geometry_checks
from apps.worker.pipeline_quality.report import build_report
from packages.domain.spatial.model import Opening, Point, Room, Segment, SpatialLayer, Wall

_LEVEL = "L-LEVEL00000000001"
_AI = {"confidence": 0.9, "source": "ai", "reviewed": False}

XY = tuple[float, float]


def _walls(*segments: tuple[XY, XY], thickness: int = 200) -> tuple[Wall, ...]:
    return tuple(
        Wall(
            id=f"W-WALL{index:010d}",
            level_id=_LEVEL,
            centreline=Segment(start=Point(x=int(a[0]), y=int(a[1])), end=Point(x=int(b[0]), y=int(b[1]))),
            thickness_mm=thickness,
            height_mm=3000,
            kind="partition",
            opening_ids=(),
            **_AI,
        )
        for index, (a, b) in enumerate(segments)
    )


def _box(x0: float, y0: float, x1: float, y1: float) -> list[tuple[XY, XY]]:
    """Bốn tường kín của hộp."""
    return [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]


def _room(
    index: int, x0: int, y0: int, x1: int, y1: int, *, usage: str = "bedroom", wall_ids: tuple[str, ...] = ()
) -> Room:
    return Room.model_validate(
        {
            "id": f"R-ROOM{index:010d}",
            "levelId": _LEVEL,
            "name": "phòng",
            "usage": usage,
            "outline": [{"x": x0, "y": y0}, {"x": x1, "y": y0}, {"x": x1, "y": y1}, {"x": x0, "y": y1}],
            "areaM2": (x1 - x0) * (y1 - y0) / 1e6,
            "wallIds": list(wall_ids),
            **_AI,
        }
    )


def _door(wall_id: str) -> Opening:
    return Opening(
        id="D-OPEN000000000001",
        wall_id=wall_id,
        kind="door",
        offset_mm=100,
        width_mm=800,
        height_mm=2100,
        sill_height_mm=0,
        swing="left",
        **_AI,
    )


def _codes(layer: SpatialLayer) -> list[tuple[str, bool]]:
    return [(check.code, check.critical) for check in geometry_checks(layer)]


def _layer(walls: tuple[Wall, ...], rooms: tuple[Room, ...] = (), openings: tuple[Opening, ...] = ()) -> SpatialLayer:
    return SpatialLayer(walls=walls, openings=openings, rooms=rooms, furniture=())


def test_closed_rectangle_with_door__no_check() -> None:
    """Tường dưới chẻ làm hai đoạn thẳng hàng nối đầu: song song, sát nhau nhưng không chồng → không phải tường đôi."""
    segments = _box(0, 0, 5000, 4000)
    segments[0:1] = [((0, 0), (2500, 0)), ((2500, 0), (5000, 0))]
    walls = _walls(*segments)
    room = _room(1, 0, 0, 5000, 4000, wall_ids=(walls[0].id,))
    assert _codes(_layer(walls, (room,), (_door(walls[0].id),))) == []


def test_empty_layer__no_check() -> None:
    assert _codes(_layer(())) == []


def test_rectangle_with_one_metre_gap__open_envelope() -> None:
    """Tường dưới chỉ tới x = 4000 trên khung 5000: khe 1 m, phòng bên trong bị lũ ngoài tràn tới."""
    segments = _box(0, 0, 5000, 4000)
    segments[0] = ((0, 0), (4000, 0))
    walls = _walls(*segments)
    loggia = _room(2, 6000, 0, 7000, 1000, usage="loggia")
    layer = _layer(walls, (_room(1, 0, 0, 5000, 4000, wall_ids=(walls[0].id,)), loggia), (_door(walls[0].id),))
    assert _codes(layer) == [("OPEN_ENVELOPE", True)]


def test_lone_small_room_outside_envelope__info_only() -> None:
    """Một hộp kỹ thuật 1 m² lòi ra ngoài vỏ kín (cn-03): vẫn báo nhưng không chặn cả tầng."""
    walls = _walls(*_box(0, 0, 5000, 4000))
    rooms = (
        _room(1, 0, 0, 5000, 4000, wall_ids=(walls[0].id,)),
        _room(2, 6000, 0, 7000, 1000, usage="utility", wall_ids=(walls[0].id,)),
    )
    assert _codes(_layer(walls, rooms, (_door(walls[0].id),))) == [("OPEN_ENVELOPE", False)]


def test_two_far_rectangles__multiple_plans() -> None:
    walls = _walls(*_box(0, 0, 5000, 4000), *_box(20000, 0, 25000, 4000))
    rooms = (
        _room(1, 0, 0, 5000, 4000, wall_ids=(walls[0].id,)),
        _room(2, 20000, 0, 25000, 4000, wall_ids=(walls[0].id,)),
    )
    assert _codes(_layer(walls, rooms, (_door(walls[0].id),))) == [("MULTIPLE_PLANS", True)]


def _plans(layer: SpatialLayer, scale_basis: str | None = None) -> tuple[bool, dict[str, float]] | None:
    """(critical, detail) của `MULTIPLE_PLANS`, vắng → `None`."""
    found = [c for c in geometry_checks(layer, scale_basis=scale_basis) if c.code == "MULTIPLE_PLANS"]
    return (found[0].critical, dict(found[0].detail)) if found else None


def test_joined_units_spanning_whole_tower__multiple_plans() -> None:
    """Các căn dính liền thành một cụm tường nhưng hộp bao dài 40 m: tờ cả tầng nhiều căn khi tỉ lệ tin được."""
    partitions = [((10000 * i, 0), (10000 * i, 8000)) for i in range(1, 4)]
    walls = _walls(*_box(0, 0, 40000, 8000), *partitions)
    assert _plans(_layer(walls), "chain") == (True, {"plans": 1, "spanMm": 40000})


@pytest.mark.parametrize(
    ("span", "basis", "expected"),
    [
        (40000, "chain", "block"),
        (40000, "door", "warn"),  # 40·0,83 = 33,2 m: có thể là căn lớn ước cửa lệch → chỉ báo
        (45000, "door", "block"),
        (40000, "wallThickness", "warn"),
        (40000, None, "warn"),
        (62000, None, "block"),
        (32000, "door", "warn"),  # 32·1,17 = 37,4 m
        (29000, "door", "absent"),
    ],
)
def test_span_rule_follows_the_scale_error_band(span: int, basis: str | None, expected: str) -> None:
    """BENCH3D-14: span 35 m chặn khi `span·(1-e)` vẫn quá, chỉ báo khi `span·(1+e)` quá (e theo `scaleBasis`)."""
    found = _plans(_layer(_walls(*_box(0, 0, span, 8000))), basis)
    assert {None: "absent", True: "block", False: "warn"}[found and found[0]] == expected


def test_small_house_on_a_wide_lot__not_multiple_plans() -> None:
    """Nhà 10 x 15 m (12 phòng 2,5 x 5 m) trong tường rào lô 40 x 30 m: span tường / cạnh phòng 11,3 nhưng phòng chỉ
    phủ 15 m (4,2 lần) → không phải tờ nhiều căn, tỉ lệ ước cửa chỉ cho báo, không chặn."""
    rooms = tuple(
        _room(i * 3 + j, 15000 + 2500 * i, 7500 + 5000 * j, 17500 + 2500 * i, 12500 + 5000 * j)
        for i in range(4)
        for j in range(3)
    )
    walls = _walls(*_box(0, 0, 40000, 30000), *_box(15000, 7500, 25000, 22500))
    found = _plans(_layer(walls, rooms), "door")
    assert found is not None
    assert found[0] is False
    assert (found[1]["wallSpanRatio"], found[1]["roomSpanRatio"]) == (11.3, 4.2)


def test_six_joined_units_with_underestimated_scale__multiple_plans() -> None:
    """Tờ 6 căn 10 x 10 m liền nhau, tỉ lệ ước bề dày tường thấp còn 0,4 lần: span 24 m dưới mọi ngưỡng mm, nhưng
    span / cạnh phòng trung vị (2 m) = 12 ở cả tường lẫn phòng → chặn dù tỉ lệ sai (BENCH3D-14)."""
    walls = _walls(
        *_box(0, 0, 24000, 4000),
        ((0, 2000), (24000, 2000)),
        *[((2000 * i, 0), (2000 * i, 4000)) for i in range(1, 12)],
    )
    rooms = tuple(
        _room(i * 2 + j, 2000 * i, 2000 * j, 2000 * i + 2000, 2000 * j + 2000) for i in range(12) for j in range(2)
    )
    assert _plans(_layer(walls, rooms), "wallThickness") == (
        True,
        {"plans": 1, "spanMm": 24000, "wallSpanRatio": 12.0, "roomSpanRatio": 12.0},
    )


def test_large_single_house__single_plan() -> None:
    """Nhà 30 m, tỉ lệ từ chuỗi kích thước: không báo (tỉ lệ ước bề dày tường thì 30·1,42 > 35 → chỉ báo)."""
    walls = _walls(*_box(0, 0, 30000, 12000))
    assert _plans(_layer(walls), "chain") is None


def test_small_far_cluster__single_plan() -> None:
    """Cụm xa nhưng ngắn (< 15 % tổng dài, kiểu logo góc trang) không tính là mặt bằng thứ hai."""
    walls = _walls(*_box(0, 0, 10000, 8000), *_box(30000, 0, 30800, 800))
    assert _plans(_layer(walls), "chain") is None


def test_three_stub_walls__wall_fragments() -> None:
    stubs = [((10000 + 1000 * i, 10000), (10150 + 1000 * i, 10000)) for i in range(3)]
    walls = _walls(*_box(0, 0, 8000, 8000), *stubs)
    assert _codes(_layer(walls)) == [("WALL_FRAGMENTS", True)]


def test_doubled_walls__wall_fragments() -> None:
    """Ba tường chồng gần trùng (lệch 10 mm, song song) lên ba cạnh của hộp kín."""
    box = _box(0, 0, 8000, 8000)
    doubled = [((0, 10), (8000, 10)), ((8010, 0), (8010, 8000)), ((8000, 7990), (0, 7990))]
    assert _codes(_layer(_walls(*box, *doubled))) == [("WALL_FRAGMENTS", True)]


def test_two_stubs__below_threshold() -> None:
    stubs = [((10000 + 1000 * i, 10000), (10150 + 1000 * i, 10000)) for i in range(2)]
    assert _codes(_layer(_walls(*_box(0, 0, 8000, 8000), *stubs))) == []


def test_rooms_without_any_opening__critical() -> None:
    walls = _walls(*_box(0, 0, 5000, 4000))
    assert _codes(_layer(walls, (_room(1, 0, 0, 5000, 4000),))) == [("ROOMS_WITHOUT_DOOR", True)]


def test_only_exempt_rooms_without_any_opening__no_check() -> None:
    """Tầng chỉ có lô gia + hành lang, không ô mở nào: phòng miễn bị lọc trước → không bật."""
    walls = _walls(*_box(0, 0, 5000, 4000))
    rooms = (_room(1, 0, 0, 2500, 4000, usage="loggia"), _room(2, 2500, 0, 5000, 4000, usage="corridor"))
    assert _codes(_layer(walls, rooms)) == []


def test_room_without_door_on_its_walls__info_only() -> None:
    """Có ô mở nhưng một phòng không tường nào mang cửa đi: chỉ báo, không chặn; hành lang được miễn."""
    walls = _walls(*_box(0, 0, 5000, 4000), ((2500, 0), (2500, 4000)))
    rooms = (
        _room(1, 0, 0, 2500, 4000, wall_ids=(walls[0].id,)),
        _room(2, 2500, 0, 5000, 4000, wall_ids=(walls[1].id,)),
        _room(3, 0, 0, 2500, 4000, usage="corridor", wall_ids=(walls[2].id,)),
    )
    checks = geometry_checks(_layer(walls, rooms, (_door(walls[0].id),)))
    assert [(c.code, c.critical, dict(c.detail)) for c in checks] == [
        ("ROOMS_WITHOUT_DOOR", False, {"doorlessRooms": 1, "share": 0.5})
    ]


def test_usage_unknown__critical_from_three_rooms() -> None:
    walls = _walls(*_box(0, 0, 6000, 4000))
    door = (_door(walls[0].id),)
    three = tuple(
        _room(i, 2000 * i, 0, 2000 * i + 2000, 4000, usage="other", wall_ids=(walls[0].id,)) for i in range(3)
    )
    assert _codes(_layer(walls, three, door)) == [("ROOM_USAGE_UNKNOWN", True)]
    assert _codes(_layer(walls, three[:2], door)) == [("ROOM_USAGE_UNKNOWN", False)]


def test_build_report__critical_check_sets_has_critical_and_wire() -> None:
    walls = _walls(*_box(0, 0, 5000, 4000))
    layer = _layer(walls, (_room(1, 0, 0, 5000, 4000),))
    report = build_report(run_id="run_01", revision=1, layer=layer, level_id=_LEVEL, threshold=Decimal("0.7"))
    assert report.issues == ()
    assert report.has_critical is True
    assert b'"checks":[{"code":"ROOMS_WITHOUT_DOOR","critical":true,"detail":{"openings":0,"rooms":1}}]' in (
        report.to_json_bytes()
    )
