"""Diff theo trường, đúng bảng tên HOP-DONG-MOI §1.3: tạo, xoá, sửa, gỡ trường, đổi loại ô mở, thứ tự."""

from packages.core.errors import MISSING
from packages.domain.spatial import FieldChange, Point, diff_layers, has_untracked_changes, sample_layer

LAYER = sample_layer(0)
WALL = LAYER.walls[0]
DOOR = LAYER.openings[0]
ROOM = LAYER.rooms[0]
ITEM = LAYER.furniture[0]
START, END = f"V-{WALL.id}-start", f"V-{WALL.id}-end"


def test_identical_layers_have_no_changes() -> None:
    """Hai lớp giống nhau → rỗng, và không có thay đổi ngoài bảng."""
    assert diff_layers(LAYER, sample_layer(0)) == []
    assert not has_untracked_changes(LAYER, sample_layer(0))


def test_new_wall_gives_seven_entries() -> None:
    """Tường mới: ba trường của tường rồi hai đỉnh x, y ngay sau (7 mục)."""
    old = LAYER.model_copy(update={"walls": LAYER.walls[1:]})
    assert diff_layers(old, LAYER) == [
        FieldChange(WALL.id, "wall", "thickness_mm", 220),
        FieldChange(WALL.id, "wall", "height_mm", 3600),
        FieldChange(WALL.id, "wall", "kind", "partition"),
        FieldChange(START, "vertex", "x", 0),
        FieldChange(START, "vertex", "y", 0),
        FieldChange(END, "vertex", "x", 1000),
        FieldChange(END, "vertex", "y", 0),
    ]


def test_deleted_wall_gives_three_entries() -> None:
    """Xoá tường: `__deleted__` cho tường và hai đỉnh, không có giá trị."""
    new = LAYER.model_copy(update={"walls": LAYER.walls[1:]})
    assert diff_layers(LAYER, new) == [
        FieldChange(WALL.id, "wall", "__deleted__", MISSING),
        FieldChange(START, "vertex", "__deleted__", MISSING),
        FieldChange(END, "vertex", "__deleted__", MISSING),
    ]


def test_moved_wall_start_is_one_vertex_entry() -> None:
    """Sửa `x` đầu tường → đúng một mục `vertex`."""
    moved = WALL.model_copy(update={"centreline": WALL.centreline.model_copy(update={"start": Point(x=-250, y=0)})})
    new = LAYER.model_copy(update={"walls": (moved, *LAYER.walls[1:])})
    assert diff_layers(LAYER, new) == [FieldChange(START, "vertex", "x", -250)]


def test_removed_room_id_is_missing() -> None:
    """Gỡ `roomId` của đồ đạc → `room_id` với `MISSING` (trên dây: vắng `value`)."""
    loose = ITEM.model_copy(update={"room_id": None})
    new = LAYER.model_copy(update={"furniture": (loose, *LAYER.furniture[1:])})
    assert diff_layers(LAYER, new) == [FieldChange(ITEM.id, "furniture", "room_id", MISSING)]


def test_new_entity_skips_absent_fields() -> None:
    """Đồ đạc mới chưa gắn phòng: không có mục `room_id`; giá trị lồng xuất dạng JSON."""
    loose = ITEM.model_copy(update={"room_id": None})
    old = LAYER.model_copy(update={"furniture": LAYER.furniture[1:]})
    new = LAYER.model_copy(update={"furniture": (loose, *LAYER.furniture[1:])})
    assert diff_layers(old, new) == [
        FieldChange(ITEM.id, "furniture", "kind", "table"),
        FieldChange(ITEM.id, "furniture", "centre", {"x": 400, "y": 400}),
        FieldChange(ITEM.id, "furniture", "rotation_deg", 0.0),
    ]


def test_door_becoming_window_is_delete_plus_create() -> None:
    """`door → window`: tạo dưới `window` theo thứ tự lớp, rồi `__deleted__` dưới `door`."""
    window = DOOR.model_copy(update={"kind": "window"})
    new = LAYER.model_copy(update={"openings": (window, *LAYER.openings[1:])})
    assert diff_layers(LAYER, new) == [
        FieldChange(DOOR.id, "window", "width_mm", 900),
        FieldChange(DOOR.id, "window", "height_mm", 2200),
        FieldChange(DOOR.id, "window", "sill_height_mm", 0),
        FieldChange(DOOR.id, "window", "offset_mm", 300),
        FieldChange(DOOR.id, "window", "swing", "left"),
        FieldChange(DOOR.id, "window", "wall_id", WALL.id),
        FieldChange(DOOR.id, "door", "__deleted__", MISSING),
    ]


def test_review_only_change_is_untracked() -> None:
    """Chỉ đổi `reviewed` (ngoài bảng) → diff rỗng nhưng `has_untracked_changes` đúng."""
    approved = WALL.model_copy(update={"reviewed": True, "source": "human", "confidence": 1.0})
    new = LAYER.model_copy(update={"walls": (approved, *LAYER.walls[1:])})
    assert diff_layers(LAYER, new) == []
    assert has_untracked_changes(LAYER, new)


def test_tracked_change_is_not_untracked() -> None:
    """Có mục trong bảng thì `has_untracked_changes` sai, kể cả khi trường ngoài bảng cũng đổi."""
    renamed = ROOM.model_copy(update={"name": "Phòng ngủ", "reviewed": False})
    new = LAYER.model_copy(update={"rooms": (renamed, *LAYER.rooms[1:])})
    assert diff_layers(LAYER, new) == [FieldChange(ROOM.id, "room", "name", "Phòng ngủ")]
    assert not has_untracked_changes(LAYER, new)


def test_order_is_new_layer_order_then_deletions_in_old_order() -> None:
    """Sửa theo thứ tự `walls → openings → rooms → furniture` của `new`, rồi mục xoá theo `old`; gọi lại y hệt."""
    thicker = WALL.model_copy(update={"thickness_mm": 300})
    reshaped = ROOM.model_copy(update={"outline": (*ROOM.outline[:3], Point(x=0, y=5000))})
    new = LAYER.model_copy(
        update={
            "walls": (thicker, *LAYER.walls[1:]),
            "openings": LAYER.openings[1:],
            "rooms": (reshaped, *LAYER.rooms[1:]),
            "furniture": (ITEM.model_copy(update={"rotation_deg": 90.0}), *LAYER.furniture[1:-1]),
        }
    )
    changes = diff_layers(LAYER, new)
    assert changes == [
        FieldChange(WALL.id, "wall", "thickness_mm", 300),
        FieldChange(
            ROOM.id,
            "room",
            "outline",
            [{"x": 0, "y": 0}, {"x": 4000, "y": 0}, {"x": 4000, "y": 4250}, {"x": 0, "y": 5000}],
        ),
        FieldChange(ITEM.id, "furniture", "rotation_deg", 90.0),
        FieldChange(DOOR.id, "door", "__deleted__", MISSING),
        FieldChange(LAYER.furniture[-1].id, "furniture", "__deleted__", MISSING),
    ]
    assert diff_layers(LAYER, new) == changes
