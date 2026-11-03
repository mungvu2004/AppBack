"""Luật 2, cửa lùa ra lô gia (BENCH3D-12): cửa sổ rộng giữa một phòng và lô gia chưa có lối vào → cửa đi lùa."""

from typing import Any

import pytest

from packages.domain.rules_ai import apply_post_rules
from packages.domain.rules_ai.constants import SLIDING_DOOR_HEIGHT_MM, SLIDING_DOOR_MIN_WIDTH_MM
from packages.domain.rules_ai.tests.builders import box_room, layer, oid, opening, wall, with_openings
from packages.domain.rules_ai.tests.reference import ref_apply_post_rules
from packages.domain.spatial import Opening, Room, SpatialLayer, Wall

# Phòng khách x 0..4000, lô gia x 4000..5500, phòng ngủ y 4000..7000 dưới cả hai; y 0..4000 cho hai phòng trên.
LIVING = box_room(1, (0, 0), (4000, 4000))
LOGGIA = box_room(2, (4000, 0), (5500, 4000)).model_copy(update={"usage": "loggia"})
BEDROOM = box_room(3, (0, 4000), (5500, 7000))
GLASS = wall(1, (4000, 0), (4000, 4000))  # giữa khách và lô gia
RAIL = wall(2, (5500, 0), (5500, 4000))  # mép ngoài lô gia
UNDER = wall(3, (4000, 4000), (5500, 4000))  # giữa lô gia và phòng ngủ
CURVED = GLASS.model_copy(update={"curve_offset_mm": 200})


def _sized(item: Opening, width: int, offset: int = 500) -> Opening:
    """Ô mở dời/đổi rộng."""
    return item.model_copy(update={"width_mm": width, "offset_mm": offset})


def _plan(walls: tuple[Wall, ...], openings: tuple[Opening, ...], rooms: tuple[Room, ...]) -> SpatialLayer:
    """Lớp với `openingIds` điền sẵn."""
    return layer(walls=with_openings(walls, openings), openings=openings, rooms=rooms)


WIDE = _sized(opening(1, 1), 2000)
ROOMS = (LIVING, LOGGIA, BEDROOM)


def _apply(source: SpatialLayer) -> SpatialLayer:
    """Áp luật, đối chiếu bản tham chiếu và idempotent."""
    result = apply_post_rules(source)
    assert result == ref_apply_post_rules(source)
    assert apply_post_rules(result) == result
    return result


@pytest.mark.parametrize(
    "extra",
    [
        (),
        (_sized(opening(2, 2, kind="door"), 1200),),  # cửa ra ngoài lan can: lô gia vẫn chưa vào được từ trong nhà
        (_sized(opening(2, 9, kind="door"), 800),),  # cửa đi trỏ tường không có: bỏ qua
    ],
)
def test_wide_window_into_loggia_without_entry__becomes_sliding_door(extra: tuple[Opening, ...]) -> None:
    """Cửa sổ 2000 khách → lô gia chưa có cửa nối phòng: cửa đi lùa cao cửa đi, bệ 0, tin cậy ≤ 0,5; tường nguyên."""
    source = _plan((GLASS, RAIL), (WIDE, *extra), ROOMS)
    result = _apply(source)
    door = result.openings[0]
    assert (door.id, door.kind, door.swing, door.width_mm) == (oid(1), "door", "sliding", 2000)
    assert (door.height_mm, door.sill_height_mm, door.confidence) == (SLIDING_DOOR_HEIGHT_MM, 0, 0.5)
    assert result.walls[0] == source.walls[0]


def test_every_wide_window_into_the_same_loggia__converted_in_one_pass() -> None:
    """Hai ô kính rộng vào cùng một lô gia chưa có lối vào (khách và phòng ngủ): cả hai thành cửa đi."""
    under = _sized(opening(2, 3), 1500, 0)
    result = _apply(_plan((GLASS, UNDER), (WIDE, under), ROOMS))
    assert [o.kind for o in result.openings] == ["door", "door"]


@pytest.mark.parametrize(
    ("walls", "openings", "rooms"),
    [
        ((GLASS,), (_sized(opening(1, 1), SLIDING_DOOR_MIN_WIDTH_MM - 1),), ROOMS),  # hẹp hơn ngưỡng
        ((GLASS, UNDER), (WIDE, _sized(opening(2, 3, kind="door"), 800)), ROOMS),  # lô gia đã có cửa đi từ phòng ngủ
        ((GLASS,), (WIDE,), (LIVING, LOGGIA.model_copy(update={"usage": "other"}), BEDROOM)),  # không phải lô gia
        ((CURVED,), (WIDE,), ROOMS),  # tường cong
    ],
)
def test_window_kept__when_not_wide_loggia_without_entry(
    walls: tuple[Wall, ...], openings: tuple[Opening, ...], rooms: tuple[Room, ...]
) -> None:
    """Hẹp, lô gia đã vào được, phòng bên kia không phải lô gia, tường cong: giữ cửa sổ (luật 2 cũ hạ tin cậy)."""
    result = _apply(_plan(walls, openings, rooms))
    assert (result.openings[0].kind, result.openings[0].confidence) == ("window", 0.5)


def test_window_on_loggia_rail__stays_window_and_rail_becomes_envelope() -> None:
    """Cửa sổ rộng trên mép ngoài lô gia (một bên không có phòng): không đổi loại, tường thành `envelope` như cũ."""
    result = _apply(_plan((RAIL,), (_sized(opening(1, 2), 3000),), ROOMS))
    assert (result.openings[0].kind, result.walls[0].kind) == ("window", "envelope")


@pytest.mark.parametrize("flags", [{"source": "human"}, {"reviewed": True}])
def test_window_not_ai_unreviewed__untouched(flags: dict[str, Any]) -> None:
    """Cửa sổ của người vẽ hay đã duyệt: luật không đụng (K21)."""
    source = _plan((GLASS,), (_sized(opening(1, 1, **flags), 2000),), ROOMS)
    assert _apply(source).openings == source.openings


def test_door_on_curved_wall__does_not_count_as_entry() -> None:
    """Cửa đi trên tường cong không dò được phòng hai bên: lô gia vẫn tính là chưa có lối vào."""
    curved_under = UNDER.model_copy(update={"curve_offset_mm": 150})
    source = _plan((GLASS, curved_under), (WIDE, _sized(opening(2, 3, kind="door"), 800)), ROOMS)
    assert _apply(source).openings[0].kind == "door"


@pytest.mark.parametrize(("depth", "kind"), [(500, "window"), (790, "window"), (900, "door")])
def test_thin_loggia_strip__keeps_window(depth: int, kind: str) -> None:
    """Dải "lô gia" sâu < 800 mm từ tim tường (giữa tường ngoài và nét khung bản vẽ, BENCH3D-23 f-06): không ai bước
    ra, cửa sổ giữ nguyên; lô gia sâu 900 mm vẫn đổi thành cửa lùa."""
    loggia = box_room(2, (4000, 0), (4000 + depth, 4000)).model_copy(update={"usage": "loggia"})
    rail = wall(2, (4000 + depth, 0), (4000 + depth, 4000))
    result = _apply(_plan((GLASS, rail), (WIDE,), (LIVING, loggia, BEDROOM)))
    assert result.openings[0].kind == kind
