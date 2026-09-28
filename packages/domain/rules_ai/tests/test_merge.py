"""`merge_pipeline_result`: giữ mục đã duyệt, ghim tham chiếu, đối chiếu id/hình học, nối lại, idempotent."""

from collections.abc import Mapping
from typing import Any, Protocol

import pytest

from packages.domain.rules_ai import MergeResult, merge_pipeline_result
from packages.domain.rules_ai.tests.builders import (
    box_room,
    fid,
    furniture,
    layer,
    oid,
    opening,
    rid,
    wall,
    wid,
    with_openings,
)
from packages.domain.rules_ai.tests.reference import ref_merge
from packages.domain.spatial import SpatialLayer, ai_reviewed_ids, check_integrity, diff_layers, has_critical

HUMAN: dict[str, Any] = {"source": "human", "reviewed": True}
FAR_ROOM = ((10_000, 0), (14_000, 4000))  # xa mọi phòng khác trong test


class _MergeOutcome(Protocol):
    """Bản chép của Protocol `MergeOutcome` (B3-03, `writer.py:81`): gói này không nhập B3-03."""

    @property
    def layer(self) -> SpatialLayer:
        """Lớp sau khi gộp."""
        ...

    @property
    def id_map(self) -> Mapping[str, str]:
        """Id AI bị bỏ → id được giữ."""
        ...


def _merge(current: SpatialLayer, ai: SpatialLayer) -> MergeResult:
    """Trộn và đối chiếu ngay với bản tham chiếu so mọi cặp: mọi ca đều được kiểm chéo."""
    result = merge_pipeline_result(current, ai)
    expected, dropped, id_map = ref_merge(current, ai)
    assert result.layer == expected
    assert result.dropped_ai_ids == dropped
    assert dict(result.id_map) == id_map
    assert result.changes == tuple(diff_layers(current, result.layer))
    return result


def test_empty_current__layer_is_ai_and_nothing_dropped() -> None:
    """`current` rỗng: kết quả bằng `ai`, không bỏ gì."""
    ai = layer(
        walls=with_openings((wall(1, (0, 0), (4000, 0)),), (opening(1, 1),)),
        openings=(opening(1, 1),),
        rooms=(box_room(1, (0, 0), (4000, 4000), wall_ids=(wid(1),)),),
        furniture_items=(furniture(1, (500, 500), room_id=rid(1)),),
    )
    result = _merge(layer(), ai)
    assert result.layer == ai
    assert result.dropped_ai_ids == ()
    assert dict(result.id_map) == {}


def test_empty_ai__only_kept_entities_and_pins_remain() -> None:
    """`ai` rỗng: còn `K` (đã duyệt, người vẽ) và phần ghim; AI cũ chưa duyệt không ai trỏ thì mất."""
    reviewed_room = box_room(1, (0, 0), (4000, 4000), wall_ids=(wid(1),), **HUMAN)
    pinned = wall(1, (0, 0), (4000, 0))
    stray = wall(2, (0, 4000), (4000, 4000))
    drawn = furniture(1, (500, 500), source="human")
    current = layer(walls=(pinned, stray), rooms=(reviewed_room,), furniture_items=(drawn,))
    result = _merge(current, layer())
    assert result.layer == layer(walls=(pinned,), rooms=(reviewed_room,), furniture_items=(drawn,))
    assert result.dropped_ai_ids == ()


def test_reviewed_room_pins_old_wall_and_new_room_relinks_to_it() -> None:
    """Phòng đã duyệt trỏ tường AI cũ → ghim nguyên; tường AI mới trùng đầu mút bị bỏ, phòng AI mới nối lại."""
    pinned = wall(1, (0, 0), (4000, 0))
    reviewed_room = box_room(1, (0, 0), (4000, 4000), wall_ids=(pinned.id,), **HUMAN)
    new_wall = wall(9, (10, 5), (4010, -3))
    new_room = box_room(9, *FAR_ROOM, wall_ids=(new_wall.id,))
    result = _merge(layer(walls=(pinned,), rooms=(reviewed_room,)), layer(walls=(new_wall,), rooms=(new_room,)))
    assert result.layer.walls == (pinned,)
    assert result.layer.rooms == (reviewed_room, new_room.model_copy(update={"wall_ids": (pinned.id,)}))
    assert dict(result.id_map) == {new_wall.id: pinned.id}
    assert result.dropped_ai_ids == (new_wall.id,)
    assert not has_critical(check_integrity(result.layer))


def test_reviewed_wall_with_new_ai_window__window_dropped_and_opening_ids_untouched() -> None:
    """Tường đã duyệt + cửa sổ AI mới trên đúng tường đó: cửa sổ bị bỏ (trong `dropped_ai_ids`), `openingIds` nguyên."""
    reviewed_wall = wall(1, (0, 0), (4000, 0), **HUMAN)
    ai_wall = wall(9, (0, 0), (4000, 0), opening_ids=(oid(9),))
    result = _merge(layer(walls=(reviewed_wall,)), layer(walls=(ai_wall,), openings=(opening(9, 9),)))
    assert result.layer == layer(walls=(reviewed_wall,))
    assert result.layer.walls[0].opening_ids == ()
    assert result.dropped_ai_ids == (ai_wall.id, oid(9))
    assert oid(9) not in result.id_map


def test_reviewed_opening_on_old_ai_wall__wall_and_listed_openings_pinned() -> None:
    """Ô mở đã duyệt trên tường AI cũ: ghim tường, cả `openingIds` và các ô mở nó liệt kê."""
    reviewed_opening = opening(1, 1, **HUMAN)
    old_opening = opening(2, 1)
    old_wall = wall(1, (0, 0), (4000, 0), opening_ids=(oid(1), oid(2)))
    unrelated = wall(2, (0, 4000), (4000, 4000))
    current = layer(walls=(old_wall, unrelated), openings=(reviewed_opening, old_opening))
    result = _merge(current, layer())
    assert result.layer == layer(walls=(old_wall,), openings=(reviewed_opening, old_opening))


def test_reference_closure__chains_through_furniture_room_wall_and_opening() -> None:
    """Đóng tham chiếu lặp tới điểm dừng: đồ đã duyệt → phòng AI → tường AI → ô mở AI đều được ghim."""
    chair = furniture(1, (500, 500), kind="chair", room_id=rid(1), **HUMAN)
    old_room = box_room(1, (0, 0), (4000, 4000), wall_ids=(wid(1),))
    old_wall = wall(1, (0, 0), (4000, 0), opening_ids=(oid(1),))
    old_opening = opening(1, 1)
    loose = wall(2, (0, 4000), (4000, 4000))
    current = layer(walls=(loose, old_wall), openings=(old_opening,), rooms=(old_room,), furniture_items=(chair,))
    result = _merge(current, layer())
    assert result.layer == layer(
        walls=(old_wall,), openings=(old_opening,), rooms=(old_room,), furniture_items=(chair,)
    )


def test_furniture_of_dropped_ai_room__room_id_moves_to_the_reviewed_room() -> None:
    """Đồ AI trỏ phòng AI bị bỏ vì trùng phòng đã duyệt: `roomId` đổi sang phòng đã duyệt."""
    reviewed_room = box_room(1, (0, 0), (4000, 4000), **HUMAN)
    ai_room = box_room(9, (100, 100), (3900, 3900))
    chair = furniture(9, (10_000, 10_000), kind="chair", room_id=ai_room.id)
    result = _merge(layer(rooms=(reviewed_room,)), layer(rooms=(ai_room,), furniture_items=(chair,)))
    assert result.layer.rooms == (reviewed_room,)
    assert [f.room_id for f in result.layer.furniture] == [reviewed_room.id]
    assert dict(result.id_map) == {ai_room.id: reviewed_room.id}


def test_same_id_dropped__wall_maps_to_itself_and_opening_has_no_mapping() -> None:
    """Tường AI trùng id tường `K` → bỏ, ánh xạ về chính id; ô mở AI trùng id ô mở `K` → bỏ, không ánh xạ."""
    kept_wall = wall(1, (0, 0), (4000, 0), **HUMAN)
    kept_opening = opening(1, 1, **HUMAN)
    current = layer(walls=with_openings((kept_wall,), (kept_opening,)), openings=(kept_opening,))
    same_wall = wall(1, (0, 9000), (4000, 9000))  # trùng id, xa hình học
    other_wall = wall(2, (0, 6000), (4000, 6000), opening_ids=(oid(1), oid(2)))
    ai = layer(walls=(same_wall, other_wall), openings=(opening(1, 2), opening(2, 2)))
    result = _merge(current, ai)
    assert result.id_map[same_wall.id] == same_wall.id
    assert oid(1) in result.dropped_ai_ids
    assert oid(1) not in result.id_map
    assert result.layer.walls[1].opening_ids == (oid(2),)
    assert [o.id for o in result.layer.openings] == [oid(1), oid(2)]


@pytest.mark.parametrize(
    ("bad", "message"),
    [
        ({"source": "human"}, "source=ai"),
        ({"reviewed": True}, "source=ai"),
    ],
)
def test_ai_entity_not_ai_unreviewed__value_error(bad: dict[str, Any], message: str) -> None:
    """`ai` có mục `source` khác `ai` hoặc `reviewed=True` → `ValueError` (tiền điều kiện, lỗi vĩnh viễn)."""
    with pytest.raises(ValueError, match=message):
        merge_pipeline_result(layer(), layer(walls=(wall(1, (0, 0), (4000, 0), **bad),)))


def test_levels_differ__value_error() -> None:
    """Hai lớp khác `levelId` (hoặc một lớp lẫn hai tầng) → `ValueError`."""
    other = "L-LEVEL000001"
    current = layer(walls=(wall(1, (0, 0), (4000, 0)),))
    with pytest.raises(ValueError, match="nhiều tầng"):
        merge_pipeline_result(current, layer(walls=(wall(2, (0, 0), (4000, 0), level=other),)))


def test_second_merge_gives_the_same_layer() -> None:
    """B5-06b giao lặp: `merge(merge(c, a).layer, a).layer == merge(c, a).layer`."""
    reviewed_wall = wall(1, (0, 0), (4000, 0), **HUMAN)
    reviewed_room = box_room(1, (0, 0), (4000, 4000), wall_ids=(reviewed_wall.id,), **HUMAN)
    current = layer(walls=(reviewed_wall, wall(2, (0, 4000), (4000, 4000))), rooms=(reviewed_room,))
    ai = layer(
        walls=(wall(9, (5, 0), (4005, 0)), wall(8, (0, 9000), (4000, 9000))),
        rooms=(box_room(9, (200, 200), (3800, 3800)), box_room(8, *FAR_ROOM)),
        furniture_items=(furniture(9, (500, 500), room_id=rid(9)),),
    )
    first = _merge(current, ai)
    assert _merge(first.layer, ai).layer == first.layer
    assert ai_reviewed_ids(first.layer) == ()


@pytest.mark.parametrize(
    ("kept", "fresh", "matches"),
    [
        (((49, 0), (1049, 0)), ((99, 0), (1099, 0)), True),  # đúng 50, qua biên ô 50 (49 // 50 = 0, 99 // 50 = 1)
        (((-1, 0), (999, 0)), ((49, 0), (1049, 0)), True),  # đúng 50, qua ô âm (-1 // 50 = -1)
        (((49, 0), (1049, 0)), ((1099, 0), (99, 0)), True),  # tường AI ngược chiều
        (((49, 0), (1049, 0)), ((1049, 0), (49, 0)), True),  # trùng hệt, ngược chiều
        (((49, 0), (1049, 0)), ((100, 0), (1100, 0)), False),  # lệch 51
        (((0, 0), (1000, 0)), ((30, 40), (1030, 40)), True),  # 50 theo đường chéo (3-4-5)
        (((0, 0), (1000, 0)), ((31, 40), (1031, 40)), False),  # 50,4 theo đường chéo
        (((0, 0), (1000, 0)), ((0, 0), (1000, 60)), False),  # một đầu khớp, đầu kia lệch
    ],
)
def test_wall_grid_boundaries__fifty_matches_fifty_one_does_not(
    kept: tuple[tuple[int, int], tuple[int, int]], fresh: tuple[tuple[int, int], tuple[int, int]], matches: bool
) -> None:
    """Biên lưới 50 mm: lệch đúng 50 qua biên ô (và số âm, ngược chiều) → trùng; lệch 51 → không."""
    current = layer(walls=(wall(1, *kept, **HUMAN),))
    result = _merge(current, layer(walls=(wall(9, *fresh),)))
    assert (wid(9) in result.id_map) is matches
    assert len(result.layer.walls) == (1 if matches else 2)


def test_two_kept_walls_match__earlier_in_current_wins() -> None:
    """`K` hoà: lấy phần tử đứng trước trong `current`, đảo thứ tự thì đảo kết quả."""
    first = wall(1, (0, 0), (4000, 0), **HUMAN)
    second = wall(2, (20, 0), (4020, 0), **HUMAN)
    fresh = layer(walls=(wall(9, (10, 0), (4010, 0)),))
    assert _merge(layer(walls=(first, second)), fresh).id_map[wid(9)] == wid(1)
    assert _merge(layer(walls=(second, first)), fresh).id_map[wid(9)] == wid(2)


@pytest.mark.parametrize(
    ("fresh_low", "fresh_high", "matches"),
    [
        ((100, 100), (3900, 3900), True),  # tâm phòng AI nằm trong phòng `K`
        ((-20_000, -20_000), (30_000, 30_000), True),  # ngược lại: tâm phòng `K` nằm trong phòng AI lớn
        ((5000, 0), (9000, 4000), False),  # kề nhau, không phòng nào chứa tâm phòng kia
    ],
)
def test_room_matching__centroid_inside_either_outline(
    fresh_low: tuple[int, int], fresh_high: tuple[int, int], matches: bool
) -> None:
    """Phòng trùng khi tâm diện tích của một bên nằm trong đường bao bên kia (cả hai chiều)."""
    kept = box_room(1, (0, 0), (4000, 4000), **HUMAN)
    fresh = box_room(9, fresh_low, fresh_high)
    result = _merge(layer(rooms=(kept,)), layer(rooms=(fresh,)))
    assert (rid(9) in result.id_map) is matches


@pytest.mark.parametrize(
    ("kind", "centre", "dropped"),
    [
        ("bed", (1000, 1000), True),  # cùng kind, tâm trong hộp
        ("bed", (1400, 1400), True),  # tâm đúng góc hộp (tính cả biên)
        ("bed", (1401, 1000), False),  # lệch 1 mm ra ngoài hộp
        ("chair", (1000, 1000), False),  # khác kind
    ],
)
def test_furniture_matching__same_kind_and_centre_in_box(kind: str, centre: tuple[int, int], dropped: bool) -> None:
    """Đồ trùng khi cùng `kind` và tâm AI nằm trong hộp đồ `K` (tính cả biên)."""
    kept = furniture(1, (1000, 1000), kind="bed", size=800, **HUMAN)
    result = _merge(layer(furniture_items=(kept,)), layer(furniture_items=(furniture(9, centre, kind=kind),)))
    assert (fid(9) in result.dropped_ai_ids) is dropped
    assert dict(result.id_map) == {}


def test_dangling_references_in_current__no_error_and_reviewed_intact() -> None:
    """`current` có tham chiếu treo: không ném, mục đã duyệt nguyên vẹn (K21)."""
    lost_room = box_room(1, (0, 0), (4000, 4000), wall_ids=(wid(7),), **HUMAN)
    lost_opening = opening(1, 8, **HUMAN)
    lost_chair = furniture(1, (500, 500), kind="chair", room_id=rid(6), **HUMAN)
    current = layer(openings=(lost_opening,), rooms=(lost_room,), furniture_items=(lost_chair,))
    result = _merge(current, layer(walls=(wall(9, (0, 9000), (4000, 9000)),)))
    assert result.layer.rooms == (lost_room,)
    assert result.layer.openings == (lost_opening,)
    assert result.layer.furniture == (lost_chair,)


def test_old_unreviewed_ai_entities_are_replaced_by_the_new_result() -> None:
    """Mục AI chưa duyệt của `current` không ai trỏ tới bị thay bằng kết quả mới; thứ tự: `K` rồi AI mới."""
    kept = wall(1, (0, 0), (4000, 0), **HUMAN)
    old = wall(2, (0, 500), (4000, 500))
    fresh = wall(9, (0, 9000), (4000, 9000))
    result = _merge(layer(walls=(old, kept)), layer(walls=(fresh,)))
    assert result.layer.walls == (kept, fresh)


def test_result_is_frozen_and_id_map_is_read_only_and_matches_the_protocol() -> None:
    """`MergeResult` frozen, `id_map` chỉ đọc; thoả theo cấu trúc Protocol `MergeOutcome` của B3-03."""
    result = merge_pipeline_result(layer(), layer())
    outcome: _MergeOutcome = result
    assert outcome.layer == layer()
    with pytest.raises(AttributeError):
        result.layer = layer()  # type: ignore[misc]  # kiểm đúng việc frozen chặn gán
    with pytest.raises(TypeError):
        result.id_map["W-X"] = "W-Y"  # type: ignore[index]  # kiểm đúng việc `id_map` chỉ đọc


def test_merge_with_no_critical_inputs__output_has_no_critical() -> None:
    """Hai đầu vào không lỗi critical thì kết quả cũng không (kể cả khi tường AI bị bỏ và ô mở của nó đi theo)."""
    reviewed_wall = wall(1, (0, 0), (4000, 0), opening_ids=(oid(1),), **HUMAN)
    reviewed_opening = opening(1, 1, **HUMAN)
    current = layer(walls=(reviewed_wall,), openings=(reviewed_opening,))
    ai_wall = wall(9, (0, 0), (4000, 0), opening_ids=(oid(9),))
    ai = layer(walls=(ai_wall,), openings=(opening(9, 9),))
    assert not has_critical(check_integrity(current))
    assert not has_critical(check_integrity(ai))
    assert not has_critical(check_integrity(_merge(current, ai).layer))
