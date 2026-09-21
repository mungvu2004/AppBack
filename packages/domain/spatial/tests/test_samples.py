"""Bộ mẫu A14: đúng số lượng, id và cờ duyệt của `createSampleBuilding()`; lớp theo tầng."""

from decimal import Decimal

import pytest

from packages.domain.spatial import sample_building, sample_layer
from packages.domain.spatial.samples import SAMPLE_TOTAL_AREA_M2

GRAPH = sample_building()


def test_counts_match_the_fe_fixture() -> None:
    """4 tầng, 48 tường, 16 ô mở (9 cửa đi + 7 cửa sổ), 21 đồ đạc, 14 phòng, 4 trục, 34 kích thước, 1 ghi chú."""
    counts = [len(getattr(GRAPH, name)) for name in ("levels", "walls", "openings", "furniture", "rooms")]
    assert counts == [4, 48, 16, 21, 14]
    assert (len(GRAPH.axes), len(GRAPH.dimensions), len(GRAPH.notes)) == (4, 34, 1)
    assert [opening.kind for opening in GRAPH.openings] == ["door"] * 9 + ["window"] * 7


def test_ids_and_review_flags_match_the_fe_fixture() -> None:
    """Id ổn định và `APPROVED`/`DETECTED` như FE; ô mở thứ 9 là cửa sổ đầu tiên trên tường 9."""
    assert GRAPH.levels[3].id == "L-LEVEL000003"
    assert GRAPH.walls[47].id == "W-WALL0000470"
    assert (GRAPH.openings[9].id, GRAPH.openings[9].wall_id) == ("D-WNDW0000000", "W-WALL0000090")
    assert GRAPH.walls[9].opening_ids == ("D-WNDW0000000",)
    assert GRAPH.walls[16].opening_ids == ()
    assert {(entity.source, entity.reviewed, entity.confidence) for entity in (*GRAPH.walls, *GRAPH.dimensions)} == {
        ("ai", False, 0.82)
    }
    assert {(entity.source, entity.reviewed) for entity in (*GRAPH.levels, *GRAPH.rooms, *GRAPH.axes)} == {
        ("human", True)
    }
    assert GRAPH.rooms[13].area_m2 == 27.6
    assert GRAPH.building.gross_floor_area_m2 == 248.6
    assert Decimal("248.60") == SAMPLE_TOTAL_AREA_M2


def test_note_created_at_is_utc() -> None:
    """`+07:00` của FE đổi sang `Z` 3 chữ số (HOP-DONG-MOI §4.1); cùng thời điểm."""
    note = GRAPH.notes[0]
    assert (note.id, note.author_id, note.created_at) == ("note-1", "U-1", "2026-08-13T02:00:00.000Z")


def test_sample_building_is_shared_and_immutable() -> None:
    """Gọi lại trả cùng bản (mô hình bất biến, dùng chung an toàn)."""
    assert sample_building() is GRAPH


def test_layer_holds_one_level() -> None:
    """Tầng 0: tường 0, 4, …, 44; ô mở có tường chủ ở tầng đó; phòng và đồ đạc cùng tầng."""
    layer = sample_layer(0)
    assert [wall.id for wall in layer.walls] == [f"W-WALL{index:06d}0" for index in range(0, 48, 4)]
    hosts = ["W-WALL0000000", "W-WALL0000040", "W-WALL0000080", "W-WALL0000120"]
    assert [opening.wall_id for opening in layer.openings] == hosts
    levels = {wall.level_id for wall in layer.walls} | {room.level_id for room in layer.rooms}
    assert levels | {item.level_id for item in layer.furniture} == {"L-LEVEL000000"}
    assert (len(layer.rooms), len(layer.furniture)) == (4, 6)


@pytest.mark.parametrize("index", [-1, 4])
def test_layer_outside_the_sample_is_refused(index: int) -> None:
    """Mẫu chỉ có tầng 0..3."""
    with pytest.raises(ValueError, match=r"0\.\.3"):
        sample_layer(index)
