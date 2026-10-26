"""Suy cờ `edited` (H1): sửa trường theo dõi là sửa, duyệt hay đổi tin cậy thì không, mục người vẽ giữ nguyên."""

from packages.domain.spatial import (
    Point,
    SpatialLayer,
    Wall,
    mark_edited,
    mark_edited_dimensions,
    sample_building,
    sample_layer,
)

LAYER = sample_layer(0)
WALL = LAYER.walls[0]
DIMENSIONS = sample_building().dimensions[:2]


def _with_wall(wall: Wall) -> SpatialLayer:
    """Lớp mẫu với tường đầu thay bằng `wall`."""
    return LAYER.model_copy(update={"walls": (wall, *LAYER.walls[1:])})


def _edited_ids(layer: SpatialLayer) -> list[str]:
    """Id các thực thể mang `edited=True`, theo thứ tự lớp."""
    return [entity.id for entity in layer.entities() if entity.edited]


def test_unchanged_ai_layer_is_not_edited() -> None:
    """Gửi lại đúng lớp: không mục nào `edited`; phòng người vẽ (đã duyệt) giữ nguyên."""
    marked = mark_edited(LAYER, sample_layer(0))
    assert _edited_ids(marked) == []
    assert marked.rooms == LAYER.rooms


def test_moved_vertex_marks_its_wall() -> None:
    """Dời đầu tường: mục `vertex` quy về tường chủ → chỉ tường đó `edited`."""
    moved = WALL.model_copy(update={"centreline": WALL.centreline.model_copy(update={"start": Point(x=-250, y=0)})})
    marked = mark_edited(LAYER, _with_wall(moved))
    assert _edited_ids(marked) == [WALL.id]
    assert marked.walls[0].centreline == moved.centreline


def test_new_ai_id_is_edited() -> None:
    """Id mới gắn `ai` (người tách tường, dán…) → `edited`."""
    current = LAYER.model_copy(update={"walls": LAYER.walls[1:]})
    assert _edited_ids(mark_edited(current, LAYER)) == [WALL.id]


def test_previous_flag_is_kept_when_sent_drops_it() -> None:
    """Mục cũ đã `edited`, client gửi lại không có trường (mặc định `False`) → vẫn `edited`."""
    current = _with_wall(WALL.model_copy(update={"edited": True}))
    assert _edited_ids(mark_edited(current, LAYER)) == [WALL.id]


def test_human_entity_sent_back_as_ai_is_edited() -> None:
    """Mục người vẽ bị client hạ về `ai` (Quyết định 3A) → `edited`, `source` vẫn `ai`."""
    drawn = WALL.model_copy(update={"source": "human", "reviewed": True, "confidence": 1.0})
    marked = mark_edited(_with_wall(drawn), LAYER)
    assert _edited_ids(marked) == [WALL.id]
    assert marked.walls[0].source == "ai"


def test_review_or_confidence_change_is_not_edited() -> None:
    """Chỉ đổi `reviewed`/`confidence` (ngoài bảng theo dõi) → không `edited`."""
    current = _with_wall(WALL.model_copy(update={"reviewed": True, "confidence": 0.99}))
    assert _edited_ids(mark_edited(current, LAYER)) == []


def test_dimension_override_is_edited() -> None:
    """Đặt `overrideValueMm` cho kích thước AI → chỉ kích thước đó `edited`."""
    first, second = DIMENSIONS
    sent = (first.model_copy(update={"override_value_mm": 1234}), second)
    assert [item.edited for item in mark_edited_dimensions(DIMENSIONS, sent)] == [True, False]


def test_unchanged_dimensions_are_not_edited() -> None:
    """Gửi lại đúng kích thước → không mục nào `edited`, giá trị giữ nguyên."""
    marked = mark_edited_dimensions(DIMENSIONS, list(DIMENSIONS))
    assert marked == DIMENSIONS
    assert not any(item.edited for item in marked)
