"""`apply_post_rules`: luật 1 (thiết bị áp tường), luật 2 (cửa sổ trên tường ngoài), bất biến chung."""

from typing import Any

import pytest

from packages.domain.rules_ai import apply_post_rules, gap_to_wall_face, wall_side
from packages.domain.rules_ai.tests.builders import (
    box_room,
    fid,
    furniture,
    layer,
    oid,
    opening,
    wall,
    wid,
    with_openings,
)
from packages.domain.rules_ai.tests.reference import ref_apply_post_rules
from packages.domain.spatial import Furniture, Opening, SpatialLayer, Wall, sample_layer

# Tường ngang y = 0 dày 100 (mặt ở y = 50); đồ vuông 600 nằm phía trên, khe = min.y - 50.
BOTTOM = wall(1, (0, 0), (6000, 0))
OUTER = wall(1, (0, 0), (4000, 0))  # mép ngoài phòng 1 của `_rooms_layer`
MIDDLE = wall(2, (4000, 0), (4000, 4000))  # giữa hai phòng của `_rooms_layer`


def _fixture_at_gap(gap: int, **kwargs: Any) -> Furniture:
    """Đồ 600 x 600 có khe tới mặt tường `BOTTOM` đúng `gap` mm."""
    return furniture(1, (3000, 50 + gap + 300), **kwargs)


def _apply_fixture(item: Furniture, *walls: Wall) -> Furniture:
    """Qua luật một đồ trên lớp chỉ có `walls`, trả đồ ra (kiểm luôn bằng bản quét hết)."""
    source = layer(walls=walls or (BOTTOM,), furniture_items=(item,))
    result = apply_post_rules(source)
    assert result == ref_apply_post_rules(source)
    return result.furniture[0]


@pytest.mark.parametrize("gap", [0, 40, 50])
def test_fixture_within_tolerance__unchanged(gap: int) -> None:
    """Khe ≤ 50 (kể cả đúng 50): đã áp tường, giữ nguyên."""
    item = _fixture_at_gap(gap)
    assert _apply_fixture(item) == item


@pytest.mark.parametrize("gap", [60, 300])
def test_fixture_in_reach__moves_flush_and_caps_confidence(gap: int) -> None:
    """Khe 60 và đúng 300 (mép tầm với): dời sát mặt tường, đo lại ≤ 50, tin cậy 0,82 → 0,5, không đổi phòng/góc."""
    item = _fixture_at_gap(gap, room_id="R-T000000001")
    moved = _apply_fixture(item)
    assert gap_to_wall_face(moved.bounding_box, BOTTOM) <= 50
    assert moved.centre.y == item.centre.y - gap
    assert moved.bounding_box.min.y == item.bounding_box.min.y - gap
    assert moved.bounding_box.max.y == item.bounding_box.max.y - gap
    assert (moved.centre.x, moved.confidence) == (item.centre.x, 0.5)
    assert (moved.room_id, moved.rotation_deg, moved.source, moved.reviewed) == (item.room_id, 0.0, "ai", False)


def test_fixture_moved__second_pass_changes_nothing() -> None:
    """Idempotent: lượt hai không dời, không hạ thêm tin cậy."""
    once = apply_post_rules(layer(walls=(BOTTOM,), furniture_items=(_fixture_at_gap(120),)))
    assert apply_post_rules(once) == once


def test_fixture_confidence_below_cap__kept_when_moved() -> None:
    """Tin cậy 0,3 thấp hơn trần: dời nhưng `min` giữ 0,3."""
    moved = _apply_fixture(_fixture_at_gap(120, confidence=0.3))
    assert moved.confidence == 0.3
    assert moved.centre.y == 350


def test_fixture_out_of_reach__unchanged() -> None:
    """Khe 301: sai phòng, để QC báo cho người duyệt."""
    item = _fixture_at_gap(301)
    assert _apply_fixture(item) == item


def test_fixture_without_any_wall_nearby__unchanged() -> None:
    """Lớp không có tường, hoặc tường ở xa (ngoài mọi ô ứng viên): giữ nguyên."""
    item = _fixture_at_gap(120)
    far = wall(2, (0, 90_000), (6000, 90_000))
    assert apply_post_rules(layer(furniture_items=(item,))).furniture == (item,)
    assert _apply_fixture(item, far) == item


def test_kitchen_cabinet_moves_but_table_does_not() -> None:
    """Tủ bếp cũng áp tường (bảng FE `fitout/index.ts:87`); bàn thì không phải áp tường."""
    assert _apply_fixture(_fixture_at_gap(120, kind="kitchenCabinet")).centre.y == 350
    table = _fixture_at_gap(120, kind="table")
    assert _apply_fixture(table) == table


@pytest.mark.parametrize(
    "flags",
    [
        {"source": "ai", "reviewed": True},
        {"source": "human", "reviewed": True},
        {"source": "human", "reviewed": False},
    ],
)
def test_fixture_not_ai_unreviewed__untouched(flags: dict[str, Any]) -> None:
    """Chỉ đồ AI chưa duyệt bị đổi (K21): đã duyệt hay do người vẽ đi ra bằng hệt."""
    item = _fixture_at_gap(120, **flags)
    assert _apply_fixture(item) == item


def test_fixture_on_diagonal_wall__snaps_to_the_endpoint() -> None:
    """Tường chéo 30°, hộp gần đầu mút: chân đường vuông góc rơi vào đầu mút, dời về phía đầu mút."""
    diagonal = wall(1, (0, 0), (8660, 5000))
    item = furniture(1, (-300, -200), size=200)
    moved = _apply_fixture(item, diagonal)
    assert (moved.centre.x - item.centre.x, moved.centre.y - item.centre.y) == (155, 78)
    assert gap_to_wall_face(moved.bounding_box, diagonal) <= 50


def test_fixture_between_two_equidistant_walls__moves_to_the_earlier_wall() -> None:
    """Hai tường cách đều (khe 300): dời về tường đứng trước trong `walls`, đảo thứ tự thì đảo hướng."""
    low = wall(1, (0, 0), (6000, 0))
    high = wall(2, (0, 1300), (6000, 1300))
    item = furniture(1, (3000, 650))
    assert _apply_fixture(item, low, high).centre.y == 350
    assert _apply_fixture(item, high, low).centre.y == 950


def test_index_matches_full_scan__long_diagonal_cell_edges_and_negatives() -> None:
    """Chỉ mục lưới: tường chéo dài qua nhiều ô, đồ vắt biên ô 1.000, toạ độ âm — bằng hệt quét hết."""
    walls = (
        wall(1, (-5000, -3000), (5000, 4000)),
        wall(2, (-2000, -500), (-2000, 2500), thickness=200),
        wall(3, (990, -4000), (990, -100)),
    )
    specs = [
        ((-2400, 1000), "sanitaryFixture", 400),  # sát tường 2, hộp vắt biên ô -3/-2, khe 100
        ((1500, -1500), "kitchenCabinet", 400),  # cách tường 3 một khoảng 260
        ((-229, 828), "sanitaryFixture", 200),  # cách tường chéo dài ≈ 200, tường chạy qua ~10 ô
        ((1000, 500), "kitchenCabinet", 800),  # tâm đúng biên ô
        ((-1000, -1000), "sanitaryFixture", 200),
        ((999, -1001), "kitchenCabinet", 200),  # nằm trong thân tường 3
    ]
    items = tuple(furniture(n, centre, kind=kind, size=size) for n, (centre, kind, size) in enumerate(specs, start=1))
    source = layer(walls=walls, furniture_items=items)
    result = apply_post_rules(source)
    assert result == ref_apply_post_rules(source)
    assert sum(after != before for after, before in zip(result.furniture, items, strict=True)) >= 3


def _rooms_layer(
    wall_items: tuple[Wall, ...], openings: tuple[Opening, ...], *, with_rooms: bool = True
) -> SpatialLayer:
    """Hai phòng kề nhau 4 x 4 m (x 0..8000), tường và ô mở cho trước (điền `openingIds`)."""
    rooms = (box_room(1, (0, 0), (4000, 4000)), box_room(2, (4000, 0), (8000, 4000))) if with_rooms else ()
    return layer(walls=with_openings(wall_items, openings), openings=openings, rooms=rooms)


def test_window_on_exterior_ai_wall__wall_becomes_envelope() -> None:
    """Cửa sổ AI trên tường AI `partition` ở mép ngoài: tường thành `envelope`, tin cậy ≤ 0,5, cửa sổ nguyên."""
    window = opening(1, 1)
    source = _rooms_layer((OUTER,), (window,))
    result = apply_post_rules(source)
    assert result == ref_apply_post_rules(source)
    assert (result.walls[0].kind, result.walls[0].confidence) == ("envelope", 0.5)
    assert result.openings == (window,)
    assert apply_post_rules(result) == result


def test_two_windows_on_one_exterior_wall__decided_once() -> None:
    """Một tường chủ nhiều cửa sổ chỉ quyết một lần; cả hai cửa sổ giữ nguyên."""
    windows = (opening(1, 1), opening(2, 1))
    result = apply_post_rules(_rooms_layer((OUTER,), windows))
    assert result.walls[0].kind == "envelope"
    assert result.openings == windows


@pytest.mark.parametrize(("confidence", "expected"), [(0.82, 0.5), (0.3, 0.3)])
def test_window_on_interior_wall__confidence_capped_wall_unchanged(confidence: float, expected: float) -> None:
    """Cửa sổ giữa hai phòng: hạ tin cậy bằng `min` (0,82 → 0,5; 0,3 giữ 0,3), không xoá, tường nguyên."""
    window = opening(1, 2, confidence=confidence)
    source = _rooms_layer((MIDDLE,), (window,))
    result = apply_post_rules(source)
    assert result == ref_apply_post_rules(source)
    assert result.walls == with_openings((MIDDLE,), (window,))
    assert [(o.id, o.kind, o.confidence) for o in result.openings] == [(oid(1), "window", expected)]


@pytest.mark.parametrize("flags", [{"source": "human", "reviewed": True}, {"source": "human", "reviewed": False}])
def test_window_on_exterior_wall_not_editable__window_capped_wall_kept(flags: dict[str, Any]) -> None:
    """Tường ngoài đã duyệt hoặc người vẽ (không được đổi): tường nguyên, cửa sổ hạ tin cậy."""
    protected = wall(1, (0, 0), (4000, 0), **flags)
    source = _rooms_layer((protected,), (opening(1, 1),))
    result = apply_post_rules(source)
    assert result == ref_apply_post_rules(source)
    assert result.walls == with_openings((protected,), source.openings)
    assert result.openings[0].confidence == 0.5


def test_window_rule_leaves_other_cases_untouched() -> None:
    """Không phòng, cửa đi trên tường trong, tường chủ thiếu, tường đã `envelope`, cửa sổ đã duyệt: giữ nguyên."""
    envelope = wall(3, (4000, 4000), (0, 4000), kind="envelope")
    openings = (
        opening(1, 2, kind="door"),
        opening(2, 9),
        opening(3, 3),
        opening(4, 2, source="human", reviewed=True),
    )
    inside = _rooms_layer((MIDDLE, envelope), openings)
    assert apply_post_rules(inside) == inside
    no_rooms = _rooms_layer((OUTER,), (opening(5, 1),), with_rooms=False)
    assert apply_post_rules(no_rooms) == no_rooms


def test_window_probe_on_room_bounding_box_edge__same_as_public_wall_side() -> None:
    """Điểm dò đúng trên biên hộp bao phòng: chỉ mục quyết như `wall_side` công khai (một bên trong → ngoài)."""
    edge = wall(1, (1000, -200), (3000, -200))  # điểm dò (2000, 0) nằm đúng cạnh dưới của phòng 1
    source = _rooms_layer((edge,), (opening(1, 1),))
    assert wall_side(edge, source.rooms) == "exterior"
    assert apply_post_rules(source).walls[0].kind == "envelope"


def _mixed_layer() -> SpatialLayer:
    """Lớp có cả luật 1 (đồ khe 120) lẫn luật 2 (cửa sổ tường ngoài và tường trong)."""
    source = _rooms_layer((OUTER, MIDDLE), (opening(1, 1), opening(2, 2)))
    return source.model_copy(update={"furniture": (furniture(1, (3000, 470)),)})


def test_rules_are_idempotent_and_do_not_mutate_the_argument() -> None:
    """`f(f(x)) == f(x)` và đối số (mô hình frozen) không đổi."""
    source = _mixed_layer()
    before = source.model_dump()
    once = apply_post_rules(source)
    assert source.model_dump() == before
    assert once != source
    assert apply_post_rules(once) == once


def test_ids_source_and_reviewed_are_never_changed() -> None:
    """Luật không tạo id, không đổi `source` hay `reviewed` của bất kỳ thực thể nào."""
    source = _mixed_layer()
    result = apply_post_rules(source)
    assert [(e.id, e.source, e.reviewed) for e in result.entities()] == [
        (e.id, e.source, e.reviewed) for e in source.entities()
    ]
    assert {wid(1), wid(2), oid(1), oid(2), fid(1)} <= {e.id for e in result.entities()}


@pytest.mark.parametrize("level", range(4))
def test_sample_layers__reviewed_entities_come_out_equal(level: int) -> None:
    """Bộ mẫu A14 qua luật: mọi thực thể `reviewed=True` bằng hệt, id không đổi, idempotent."""
    source = sample_layer(level)
    result = apply_post_rules(source)
    for before, after in zip(source.entities(), result.entities(), strict=True):
        assert before.id == after.id
        if before.reviewed:
            assert before == after
    assert apply_post_rules(result) == result
