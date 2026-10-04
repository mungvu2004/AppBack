"""Danh mục 16 mục: id, nhóm, tên, số liệu, `is_item_id` và hiệu năng dựng cả danh mục."""

import logging
import time
import unicodedata

import pytest

from packages.domain.library import (
    CATALOGUE,
    ITEM_ID_MAX_LEN,
    LIBRARY_GROUPS,
    CatalogueItem,
    build_glb,
    build_preview_png,
    is_item_id,
)

_log = logging.getLogger(__name__)

TABLE_ORDER = [
    ("table-dining-6", "bàn ăn sáu chỗ", "table"),
    ("table-desk", "bàn làm việc", "table"),
    ("chair-dining", "ghế ăn tựa lưng", "chair"),
    ("chair-stool", "ghế đẩu", "chair"),
    ("bed-double-1600", "giường đôi 1m6", "bed"),
    ("bed-single-1000", "giường đơn 1m", "bed"),
    ("sofa-three-seat", "sofa ba chỗ", "sofa"),
    ("sofa-armchair", "ghế bành", "sofa"),
    ("storage-wardrobe", "tủ quần áo hai cánh", "storage"),
    ("storage-bookshelf", "kệ sách năm tầng", "storage"),
    ("sanitary-toilet", "bồn cầu", "sanitary"),
    ("sanitary-basin", "chậu rửa mặt", "sanitary"),
    ("kitchen-base-cabinet", "tủ bếp dưới", "kitchen"),
    ("kitchen-fridge", "tủ lạnh", "kitchen"),
    ("technical-panel", "tủ điện", "technical"),
    ("technical-water-purifier", "máy lọc nước", "technical"),
]
MAX_TRIANGLES = 900_000  # SCENE_BUDGET.maxTriangles của FE


def test_catalogue_order_names_and_groups_match_table() -> None:
    """Thứ tự (= `sort_order`), id, tên và nhóm đúng bảng [5]."""
    assert [(i.id, i.name, i.group) for i in CATALOGUE] == TABLE_ORDER


def test_catalogue_ids_unique_and_valid() -> None:
    """16 id duy nhất, mỗi id khớp `is_item_id`."""
    ids = [i.id for i in CATALOGUE]
    assert len(ids) == len(set(ids)) == 16
    assert all(is_item_id(i) for i in ids)


def test_catalogue_covers_all_eight_groups_in_fe_order() -> None:
    """Đủ 8 nhóm; danh sách nhóm đúng thứ tự chip FE."""
    assert LIBRARY_GROUPS == ("table", "chair", "bed", "sofa", "storage", "sanitary", "kitchen", "technical")
    assert {i.group for i in CATALOGUE} == set(LIBRARY_GROUPS)
    assert [i.group for i in CATALOGUE] == sorted((i.group for i in CATALOGUE), key=LIBRARY_GROUPS.index)


@pytest.mark.parametrize("item", CATALOGUE, ids=lambda i: i.id)
def test_catalogue_name_is_clean_nfc(item: CatalogueItem) -> None:
    """Tên NFC, 1-120 ký tự, không ký tự điều khiển/định dạng (`Cc`, `Cf`)."""
    assert unicodedata.normalize("NFC", item.name) == item.name
    assert 1 <= len(item.name) <= 120
    assert not any(unicodedata.category(c) in {"Cc", "Cf"} for c in item.name)


@pytest.mark.parametrize("item", CATALOGUE, ids=lambda i: i.id)
def test_catalogue_numbers_positive_and_colour_count(item: CatalogueItem) -> None:
    """Kích thước khối > 0, `rgb` 0-255, mỗi mục 2-4 màu; toạ độ khối là số nguyên."""
    assert item.parts
    for p in item.parts:
        assert p.width_mm > 0
        assert p.height_mm > 0
        assert p.depth_mm > 0
        assert p.y_mm >= 0
        assert all(0 <= c <= 255 for c in p.rgb)
        assert all(type(v) is int for v in (p.x_mm, p.y_mm, p.z_mm, p.width_mm, p.height_mm, p.depth_mm))
    assert 2 <= len({p.rgb for p in item.parts}) <= 4


def test_catalogue_measured_values_positive_and_within_budget() -> None:
    """Số đo từ tệp: mọi số > 0; tổng tam giác dưới ngân sách cảnh của FE."""
    assets = [build_glb(i) for i in CATALOGUE]
    for a in assets:
        assert min(a.width_mm, a.depth_mm, a.height_mm, a.triangle_count, a.size_bytes) > 0
        assert a.triangle_count < MAX_TRIANGLES
    assert sum(a.triangle_count for a in assets) < MAX_TRIANGLES


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("a", True),
        ("a-b", True),
        ("a1-2b-c3", True),
        ("A", False),
        ("a_b", False),
        ("", False),
        ("-a", False),
        ("a-", False),
        ("a--b", False),
        ("a b", False),
        ("a\n", False),
        ("á", False),
        ("a" * ITEM_ID_MAX_LEN, True),
        ("a" * (ITEM_ID_MAX_LEN + 1), False),
    ],
)
def test_is_item_id_boundaries(value: str, expected: bool) -> None:
    """Biên của mẫu id và trần 64 ký tự (64 đạt, 65 hỏng)."""
    assert is_item_id(value) is expected


@pytest.mark.perf
def test_build_all_assets_under_one_second() -> None:
    """16 mục dựng GLB + PNG dưới 1 s tổng (lịch gọi mỗi lượt); số đo in bằng `logging`."""
    start = time.perf_counter()
    for item in CATALOGUE:
        build_glb(item)
        build_preview_png(item)
    elapsed = time.perf_counter() - start
    _log.info("catalogue_build_elapsed_s=%.3f", elapsed)
    assert elapsed < 1.0
