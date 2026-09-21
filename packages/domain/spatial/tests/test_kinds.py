"""A5, loại thay đổi theo HOP-DONG-MOI §1.3, id đỉnh tường."""

import pytest

from packages.core.ids import SPATIAL_PREFIX
from packages.domain.spatial import (
    ID_PREFIX_BY_KIND,
    SpatialLayer,
    ai_reviewed_ids,
    change_entity_type,
    sample_building,
    sample_layer,
    vertex_id,
)

GRAPH = sample_building()
DOOR = GRAPH.openings[0]
WINDOW = GRAPH.openings[-1]


def test_prefix_table_is_the_core_one() -> None:
    """Không khai bảng tiền tố thứ hai: đúng đối tượng của `packages.core.ids`."""
    assert ID_PREFIX_BY_KIND is SPATIAL_PREFIX


def test_one_ai_reviewed_wall_is_reported() -> None:
    """Lớp có đúng một tường `ai` + `reviewed` → đúng id đó."""
    layer = sample_layer(0)
    bad = layer.walls[1].model_copy(update={"reviewed": True})
    tampered = layer.model_copy(update={"walls": (layer.walls[0], bad, *layer.walls[2:])})
    assert ai_reviewed_ids(tampered) == (bad.id,)


def test_sample_building_has_no_a5_violation() -> None:
    """Mẫu A14 sạch A5, cả đồ thị lẫn từng lớp."""
    assert ai_reviewed_ids(GRAPH) == ()
    assert all(ai_reviewed_ids(sample_layer(index)) == () for index in range(4))


def test_graph_reports_in_order_with_building_pseudo_id() -> None:
    """Đồ thị báo theo thứ tự khai trường; `Building` không có id nên dùng `"building"`."""
    ai_approved = {"source": "ai", "reviewed": True}
    graph = GRAPH.model_copy(
        update={
            "building": GRAPH.building.model_copy(update=ai_approved),
            "levels": (GRAPH.levels[0].model_copy(update=ai_approved), *GRAPH.levels[1:]),
            "notes": (GRAPH.notes[0].model_copy(update=ai_approved),),
        }
    )
    assert ai_reviewed_ids(graph) == ("building", GRAPH.levels[0].id, "note-1")


def test_empty_layer_has_no_violation() -> None:
    """Lớp rỗng → rỗng."""
    assert ai_reviewed_ids(SpatialLayer(walls=(), openings=(), rooms=(), furniture=())) == ()


@pytest.mark.parametrize(
    ("entity", "expected"),
    [
        (GRAPH.walls[0], "wall"),
        (DOOR, "door"),
        (WINDOW, "window"),
        (GRAPH.furniture[0], "furniture"),
        (GRAPH.rooms[0], "room"),
        (GRAPH.dimensions[0], "dimension"),
        (GRAPH.levels[0], None),
        (GRAPH.axes[0], None),
        (GRAPH.notes[0], None),
        (GRAPH.building, None),
    ],
)
def test_change_entity_type(entity: object, expected: str | None) -> None:
    """Mỗi kiểu thực thể một `entityType`; cửa đi và cửa sổ tách theo `kind`; loại không có nhật ký → `None`."""
    assert change_entity_type(entity) == expected


def test_door_and_window_samples_are_what_the_table_assumes() -> None:
    """Hai ca ô mở trên đúng là một cửa đi và một cửa sổ."""
    assert (DOOR.kind, WINDOW.kind) == ("door", "window")


def test_vertex_id() -> None:
    """Id đỉnh tường theo §1.3."""
    assert vertex_id("W-X", "start") == "V-W-X-start"
    assert vertex_id("W-WALL0000000", "end") == "V-W-WALL0000000-end"
