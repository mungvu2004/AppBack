"""`apps.api.spatial_read.codec`: khứ hồi jsonb ↔ mô hình, và những gì phải coi là hỏng (B3-02 [8])."""

from typing import Any

import pytest

from apps.api.spatial_read.codec import DocumentCorruptError, document_from_json, document_to_json, entity_ids
from packages.domain.spatial import sample_building, sample_layer
from packages.testing.factories.spatial import sample_floor_dimensions, sample_floor_layer

SAMPLE_ENTITY_COUNT = 99
"""48 tường + 16 ô mở + 21 đồ đạc + 14 phòng của toà mẫu A14; kích thước **không** tính."""


def _raw(level_index: int = 0) -> dict[str, Any]:
    """Tài liệu dây hợp lệ của một tầng mẫu, kèm kích thước của tầng ấy."""
    graph = sample_building()
    level_id = graph.levels[level_index].id
    dimensions = [d for d in graph.dimensions if d.level_id == level_id]
    return dict(document_to_json(sample_layer(level_index), (), dimensions))


@pytest.mark.parametrize("level_index", range(4))
def test_round_trip_keeps_every_sample_level(level_index: int) -> None:
    """Ghi rồi đọc lại bốn tầng mẫu cho đúng mô hình cũ, và `axes` v1 luôn rỗng."""
    raw = _raw(level_index)
    layer, axes, dimensions = document_from_json(raw)

    assert layer == sample_layer(level_index)
    assert axes == ()
    assert document_to_json(layer, axes, dimensions) == raw


def test_document_to_json_drops_axes() -> None:
    """`axes` được nhận nhưng v1 không ghi: khoá có mặt, giá trị rỗng (hợp đồng [2])."""
    graph = sample_building()
    assert document_to_json(sample_layer(0), graph.axes, ())["axes"] == []


def test_unknown_key_is_corrupt() -> None:
    """Khoá lạ trong một thực thể → `DocumentCorruptError`, không phải "bỏ qua rồi đọc tiếp"."""
    raw = _raw()
    raw["layer"]["walls"][0]["colour"] = "red"
    with pytest.raises(DocumentCorruptError):
        document_from_json(raw)


def test_unknown_top_level_key_is_corrupt() -> None:
    """Khoá lạ ở **mức ngoài** cũng hỏng — khung tài liệu cũng `extra="forbid"`."""
    raw = _raw()
    raw["notes"] = []
    with pytest.raises(DocumentCorruptError):
        document_from_json(raw)


def test_fractional_mm_is_corrupt() -> None:
    """mm thập phân → hỏng (K20): độ dài là số nguyên, `1.5` nghĩa là một lượt ghi đã sai kiểu."""
    raw = _raw()
    raw["layer"]["walls"][0]["thicknessMm"] = 220.5
    with pytest.raises(DocumentCorruptError):
        document_from_json(raw)


def test_missing_section_is_corrupt() -> None:
    """Thiếu hẳn `dimensions` → hỏng; codec **không** điền giá trị mặc định thay người ghi."""
    raw = _raw()
    del raw["dimensions"]
    with pytest.raises(DocumentCorruptError):
        document_from_json(raw)


def test_entity_ids_cover_sample_building() -> None:
    """Bốn tầng mẫu gộp lại cho đúng 99 id, và mỗi tầng không id nào trùng."""
    all_ids = [entity_id for index in range(4) for entity_id in entity_ids(sample_layer(index))]
    assert len(all_ids) == SAMPLE_ENTITY_COUNT
    assert len(set(all_ids)) == SAMPLE_ENTITY_COUNT


def test_entity_ids_exclude_dimensions() -> None:
    """Kích thước không chiếm id: chúng vắng khỏi tập, dù cùng tầng."""
    graph = sample_building()
    dimension_ids = {dimension.id for dimension in graph.dimensions}
    assert entity_ids(sample_layer(0)) & dimension_ids == frozenset()


def test_sample_floor_layer_rewrites_ids_and_references() -> None:
    """`id_suffix` nối vào thân **mọi** id lẫn tham chiếu, nên lớp sau khi đổi vẫn tự nhất quán."""
    layer = sample_floor_layer(0, level_id="L-LEVELTEST01", id_suffix="9")

    assert all(wall.id.endswith("9") for wall in layer.walls)
    assert all(wall.level_id == "L-LEVELTEST01" for wall in layer.walls)
    assert {opening.wall_id for opening in layer.openings} <= {wall.id for wall in layer.walls}
    assert {room_id for item in layer.furniture if (room_id := item.room_id)} <= {room.id for room in layer.rooms}
    assert entity_ids(layer) & entity_ids(sample_layer(0)) == frozenset()


def test_sample_floor_layer_reviewed_marks_every_entity() -> None:
    """`reviewed=True` đặt `source="human"`, `reviewed=True` cho mọi mục (C01 `__C01_reviewed`)."""
    layer = sample_floor_layer(0, level_id="L-LEVELTEST01", reviewed=True)

    assert all(entity.reviewed and entity.source == "human" for entity in layer.entities())


def test_sample_floor_dimensions_follow_the_level() -> None:
    """Kích thước cũng đổi `levelId` và hậu tố, kể cả `referenceIds` trỏ sang tường."""
    dimensions = sample_floor_dimensions(0, level_id="L-LEVELTEST01", id_suffix="9")

    assert dimensions
    assert all(dimension.level_id == "L-LEVELTEST01" for dimension in dimensions)
    assert all(reference.endswith("9") for d in dimensions for reference in d.reference_ids)


@pytest.mark.parametrize("suffix", ["a", "-", "Ạ"])
def test_bad_suffix_is_rejected(suffix: str) -> None:
    """Hậu tố ngoài `[0-9A-Z]` dựng ra id không qua nổi mẫu W4 → `ValueError` ngay."""
    with pytest.raises(ValueError, match="id_suffix"):
        sample_floor_layer(0, level_id="L-LEVELTEST01", id_suffix=suffix)


def test_too_long_suffix_is_rejected() -> None:
    """Thân id tối đa 64 ký tự (W4); hậu tố đẩy quá → `ValueError` thay vì một id DB từ chối."""
    with pytest.raises(ValueError, match="dài quá"):
        sample_floor_dimensions(0, level_id="L-LEVELTEST01", id_suffix="Z" * 60)
