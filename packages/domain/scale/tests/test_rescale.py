"""Đổi tỉ lệ cho mục chưa duyệt (#35, N19): độ dài mặt bằng nhân `k`, chiều cao giữ, mục đã duyệt giữ nguyên.

`include_reviewed=True` (H4) đổi cả mục đã duyệt.
"""

import pytest

from packages.domain.scale import RescaleError, rescale_dimensions, rescale_unreviewed
from packages.domain.spatial import Point, Segment, SpatialLayer, Wall, sample_building, sample_layer
from packages.domain.spatial.thickness import STANDARD_THICKNESSES_MM, snap_thickness

LAYER = sample_layer(0)
WALL, DOOR, ROOM, ITEM = LAYER.walls[0], LAYER.openings[0], LAYER.rooms[0], LAYER.furniture[0]
DIMENSIONS = sample_building().dimensions[:3]
UNREVIEWED = {"reviewed": False, "source": "ai", "confidence": 0.5}


def test_unreviewed_entities_double_with_k_2() -> None:
    """`k = 2`: toạ độ, vị trí và bề rộng ô mở, tâm và hộp bao nhân đôi; bề dày bắt bậc (440 → 400); cao, góc giữ."""
    scaled = rescale_unreviewed(LAYER, 6.0, 12.0)
    wall, door, item = scaled.walls[0], scaled.openings[0], scaled.furniture[0]
    assert wall.centreline == Segment(start=Point(x=0, y=0), end=Point(x=2000, y=0))
    assert (wall.thickness_mm, wall.height_mm, wall.confidence) == (400, WALL.height_mm, WALL.confidence)
    assert (door.offset_mm, door.width_mm, door.height_mm, door.sill_height_mm) == (600, 1800, 2200, 0)
    assert (item.centre, item.rotation_deg) == (Point(x=800, y=800), ITEM.rotation_deg)
    assert (item.bounding_box.min, item.bounding_box.max) == (Point(x=0, y=0), Point(x=1600, y=1600))
    assert [entity.reviewed for entity in scaled.entities()] == [entity.reviewed for entity in LAYER.entities()]


@pytest.mark.parametrize(("curve", "new", "expected"), [(300, 12.0, 600), (-500, 3.0, -250), (500, 2.0, 166)])
def test_curve_offset_scales_and_stays_within_half_the_chord(curve: int, new: float, expected: int) -> None:
    """Sagitta nhân `k` như mọi độ dài mặt bằng; làm tròn lố nửa dây (1000 mm · ⅓ → dây 333, sagitta 167) thì kẹp."""
    wall = WALL.model_copy(update={"curve_offset_mm": curve, **UNREVIEWED})
    (scaled,) = rescale_unreviewed(LAYER.model_copy(update={"walls": (wall,)}), 6.0, new).walls
    assert scaled.curve_offset_mm == expected
    assert "curveOffsetMm" not in WALL.model_dump(by_alias=True)


def test_reviewed_entities_are_untouched() -> None:
    """Phòng của mẫu đã duyệt: giữ nguyên từng trường, kể cả `areaM2` (K21)."""
    scaled = rescale_unreviewed(LAYER, 6.0, 12.0)
    assert scaled.rooms == LAYER.rooms
    approved = WALL.model_copy(update={"reviewed": True, "source": "human", "confidence": 1.0})
    assert rescale_unreviewed(LAYER.model_copy(update={"walls": (approved,)}), 6.0, 12.0).walls == (approved,)


def test_unreviewed_room_gets_its_area_recomputed() -> None:
    """Phòng chưa duyệt: đường bao nhân đôi, `areaM2` tính lại từ đường bao mới (4000 x 4250 → 68,00 m²)."""
    room = ROOM.model_copy(update=UNREVIEWED)
    scaled = rescale_unreviewed(LAYER.model_copy(update={"rooms": (room,)}), 6.0, 12.0).rooms[0]
    assert scaled.outline[2] == Point(x=8000, y=8500)
    assert scaled.area_m2 == 68.0


def test_same_scale_returns_the_layer() -> None:
    """`old == new` → trả nguyên lớp, không dựng lại."""
    assert rescale_unreviewed(LAYER, 12.0, 12.0) is LAYER


def test_halves_round_like_math_round() -> None:
    """`k = 0,5`: 2,5 → 3 và -2,5 → -2 như `Math.round` (`round()` dựng sẵn cho 2 và -2); bề dày bắt bậc."""
    odd = WALL.model_copy(
        update={"thickness_mm": 5, "centreline": Segment(start=Point(x=-5, y=0), end=Point(x=1000, y=3))}
    )
    scaled = rescale_unreviewed(LAYER.model_copy(update={"walls": (odd,)}), 12.0, 6.0).walls[0]
    assert scaled.thickness_mm == 100
    assert scaled.centreline == Segment(start=Point(x=-2, y=0), end=Point(x=500, y=2))


def test_one_millimetre_wall_collapsing_names_the_wall() -> None:
    """`k` làm tường 1 mm về 0 → `RescaleError` mang đúng id, không kẹp."""
    tiny = WALL.model_copy(update={"centreline": Segment(start=Point(x=0, y=0), end=Point(x=1, y=0))})
    with pytest.raises(RescaleError, match=WALL.id) as caught:
        rescale_unreviewed(LAYER.model_copy(update={"walls": (tiny,)}), 12.0, 4.0)
    assert caught.value.entity_id == WALL.id


def test_thin_ai_wall_snaps_up_instead_of_collapsing() -> None:
    """B3: bề dày AI không còn nhân thẳng nên 1 mm · ⅓ không về 0 mà bắt về bậc nhỏ nhất 100."""
    thin = WALL.model_copy(update={"thickness_mm": 1})
    assert rescale_unreviewed(LAYER.model_copy(update={"walls": (thin,)}), 12.0, 4.0).walls[0].thickness_mm == 100


def test_length_beyond_safe_integer_names_the_entity() -> None:
    """`k` hữu hạn nhưng đẩy độ dài vượt 2^53 - 1 → `RescaleError` của đúng tường, không kẹp."""
    with pytest.raises(RescaleError) as caught:
        rescale_unreviewed(LAYER, 1.0, 1e300)
    assert caught.value.entity_id == WALL.id


@pytest.mark.parametrize(
    ("old", "new"),
    [(0, 12), (12, 0), (-6, 12), (float("nan"), 12), (12, float("inf")), (1e-300, 1e300), (1e300, 1e-300)],
)
def test_scales_must_be_positive_and_finite(old: float, new: float) -> None:
    """`old`, `new` và cả `new / old` phải hữu hạn và > 0, cho cả lớp lẫn kích thước (review B3-01 #3).

    Là lỗi tham số (`ValueError` thuần), không đổ cho thực thể chưa duyệt đầu tiên (`RescaleError`).
    """
    for rescale in (lambda: rescale_unreviewed(LAYER, old, new), lambda: rescale_dimensions(DIMENSIONS, old, new)):
        with pytest.raises(ValueError, match="tỉ lệ") as caught:
            rescale()
        assert not isinstance(caught.value, RescaleError)


def test_dimensions_double_line_and_keep_values() -> None:
    """`k = 2`: `line` nhân đôi, `valueMm` và `referenceIds` giữ; kích thước đã duyệt giữ nguyên."""
    approved = DIMENSIONS[2].model_copy(update={"reviewed": True, "source": "human"})
    first, _, kept = rescale_dimensions((*DIMENSIONS[:2], approved), 6.0, 12.0)
    assert first.line == Segment(start=Point(x=0, y=-1000), end=Point(x=2000, y=-1000))
    assert (first.value_mm, first.reference_ids) == (DIMENSIONS[0].value_mm, DIMENSIONS[0].reference_ids)
    assert kept == approved


def test_dimensions_at_the_same_scale_are_returned_as_is() -> None:
    """`old == new` → cùng các kích thước."""
    assert rescale_dimensions(list(DIMENSIONS), 12.0, 12.0) == DIMENSIONS


def test_empty_layer_rescales_to_empty() -> None:
    """Lớp rỗng → lớp rỗng."""
    empty = SpatialLayer(walls=(), openings=(), rooms=(), furniture=())
    assert rescale_unreviewed(empty, 6.0, 12.0) == empty


def test_reviewed_entities_scale_when_include_reviewed() -> None:
    """`include_reviewed=True` (H4): tường và phòng đã duyệt cũng nhân đôi, cờ duyệt giữ; bề dày người gõ giữ (B3)."""
    approved = WALL.model_copy(update={"reviewed": True, "source": "human", "confidence": 1.0})
    layer = LAYER.model_copy(update={"walls": (approved,)})
    scaled = rescale_unreviewed(layer, 6.0, 12.0, include_reviewed=True)
    wall, room = scaled.walls[0], scaled.rooms[0]
    assert wall.centreline == Segment(start=Point(x=0, y=0), end=Point(x=2000, y=0))
    assert (wall.thickness_mm, wall.reviewed, wall.source) == (220, True, "human")
    assert (room.outline[2], room.reviewed) == (Point(x=8000, y=8500), True)


def test_dimensions_include_reviewed_scale_line() -> None:
    """`include_reviewed=True`: `line` của kích thước đã duyệt nhân đôi, `valueMm` giữ."""
    approved = DIMENSIONS[0].model_copy(update={"reviewed": True, "source": "human"})
    (scaled,) = rescale_dimensions((approved,), 6.0, 12.0, include_reviewed=True)
    assert scaled.line == Segment(start=Point(x=0, y=-1000), end=Point(x=2000, y=-1000))
    assert (scaled.value_mm, scaled.reviewed) == (approved.value_mm, True)


def test_detected_thickness_follows_scale() -> None:
    """U48: bề dày máy đo cũng là px · tỉ lệ nên co giãn cùng `thicknessMm`; vắng thì vẫn vắng."""
    measured = WALL.model_copy(update={**UNREVIEWED, "detected_thickness_mm": 221})
    scaled = rescale_unreviewed(LAYER.model_copy(update={"walls": (measured,)}), 6.0, 12.0)
    assert scaled.walls[0].detected_thickness_mm == 442
    assert rescale_unreviewed(LAYER, 6.0, 12.0).walls[0].detected_thickness_mm is None


def _ai_wall(detected: int, thickness: int | None = None) -> Wall:
    """Tường AI chưa duyệt có số đo; `thickness` vắng thì là bậc của số đo (chưa ai sửa)."""
    return WALL.model_copy(
        update={**UNREVIEWED, "detected_thickness_mm": detected, "thickness_mm": thickness or detected}
    )


def _rescaled_wall(wall: Wall, old: float, new: float) -> Wall:
    """Một tường sau `rescale_unreviewed(old → new)`."""
    return rescale_unreviewed(LAYER.model_copy(update={"walls": (wall,)}), old, new).walls[0]


@pytest.mark.parametrize("thickness", [100, 150, 200, 220])
def test_ai_thickness_stays_standard_and_round_trips(thickness: int) -> None:
    """B3: `k = 1,276` cho bậc chuẩn (không 128/191/255/281 lẻ); đổi `k` rồi `1/k` trả đúng bậc cũ."""
    there = _rescaled_wall(_ai_wall(thickness), 6.0, 6.0 * 1.276)
    assert there.thickness_mm in STANDARD_THICKNESSES_MM
    assert there.thickness_mm == snap_thickness(there.detected_thickness_mm or 0)
    back = _rescaled_wall(there, 6.0 * 1.276, 6.0)
    assert (back.thickness_mm, back.detected_thickness_mm) == (thickness, thickness)


def test_hand_edited_thickness_is_kept() -> None:
    """B3: bề dày lệch bậc của số đo là người gõ tay → giữ; số đo vẫn đổi theo tỉ lệ."""
    scaled = _rescaled_wall(_ai_wall(221, thickness=300), 6.0, 12.0)
    assert (scaled.thickness_mm, scaled.detected_thickness_mm) == (300, 442)
