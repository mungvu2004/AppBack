"""Danh mục 16 mục dựng sẵn của thư viện .glb: mỗi mục là vài khối hộp nguyên mm.

Danh mục là dữ liệu sản phẩm (B2-06 [5]); `.glb` và ảnh xem trước được sinh tất định từ
đây, không commit tệp nhị phân. Thứ tự của `CATALOGUE` chính là `sort_order` trong DB.
Bất biến của mỗi mục: hộp bao các khối đối xứng quanh 0 theo X và Z, đáy Y = 0, bằng đúng
W x D x H của bảng [5] (kích thước chẵn để `-W/2` là số nguyên). Trục glTF: Y lên, X rộng,
Z sâu; `x/y/z` của khối là góc nhỏ nhất.
"""

import re
from dataclasses import dataclass
from typing import Final

LIBRARY_GROUPS: Final[tuple[str, ...]] = (
    "table",
    "chair",
    "bed",
    "sofa",
    "storage",
    "sanitary",
    "kitchen",
    "technical",
)  # thứ tự chip của FE (`src/api/schemas/library.ts:74-83`)

ITEM_ID_MAX_LEN: Final = 64
ITEM_ID_RE: Final = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def is_item_id(value: str) -> bool:
    """Đúng khi `value` là id mục hợp lệ (khớp mẫu và ≤ 64 ký tự).

    Dùng ở biên HTTP để id sai mẫu trả 404 mà không truy vấn DB (R-17). Dùng `fullmatch`
    để chuỗi có xuống dòng cuối (`a\\n`) không lọt qua `$`.
    """
    return len(value) <= ITEM_ID_MAX_LEN and ITEM_ID_RE.fullmatch(value) is not None


@dataclass(frozen=True)
class Part:
    """Một khối hộp: góc nhỏ nhất `(x, y, z)`, kích thước và màu, mọi số nguyên mm."""

    x_mm: int
    y_mm: int
    z_mm: int
    width_mm: int
    height_mm: int
    depth_mm: int
    rgb: tuple[int, int, int]


@dataclass(frozen=True)
class CatalogueItem:
    """Một mục danh mục: id, tên tiếng Việt (NFC), nhóm và các khối."""

    id: str
    name: str
    group: str
    parts: tuple[Part, ...]


def part_bounds(item: CatalogueItem) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    """Hộp bao `((min_x, min_y, min_z), (max_x, max_y, max_z))` của mọi khối, mm.

    Nguồn duy nhất của kích thước đo (GLB và ảnh xem trước cùng dùng, R-07).
    Ném `ValueError` khi mục không có khối: hộp bao không xác định.
    """
    if not item.parts:
        raise ValueError(f"mục {item.id!r} không có khối nào")
    lo = tuple(min(v) for v in zip(*((p.x_mm, p.y_mm, p.z_mm) for p in item.parts), strict=True))
    hi = tuple(
        max(v)
        for v in zip(
            *((p.x_mm + p.width_mm, p.y_mm + p.height_mm, p.z_mm + p.depth_mm) for p in item.parts), strict=True
        )
    )
    return (lo[0], lo[1], lo[2]), (hi[0], hi[1], hi[2])


_WOOD = (160, 112, 72)
_DARK = (64, 48, 40)
_WHITE = (240, 240, 236)
_GREY = (150, 155, 160)
_FABRIC = (96, 118, 140)
_CUSHION = (140, 162, 184)
_RED = (190, 60, 50)
_BLUE = (60, 140, 200)
_LIGHT = (200, 172, 124)


def _bed(width: int, name: str, item_id: str) -> CatalogueItem:
    """Giường sâu 2000 mm: hai mẫu chỉ khác bề rộng nên dựng chung (R-07)."""
    half = width // 2
    return CatalogueItem(
        item_id,
        name,
        "bed",
        (
            Part(-half, 0, -1000, width, 450, 60, _WOOD),  # đầu giường
            Part(-half, 100, -940, width, 150, 1940, _WOOD),  # khung
            Part(-half + 20, 250, -920, width - 40, 200, 1900, _WHITE),  # đệm
            Part(-half, 0, 880, 60, 100, 60, _DARK),  # chân cuối giường
            Part(half - 60, 0, 880, 60, 100, 60, _DARK),
        ),
    )


CATALOGUE: Final[tuple[CatalogueItem, ...]] = (
    CatalogueItem(
        "table-dining-6",
        "bàn ăn sáu chỗ",
        "table",
        (
            Part(-900, 710, -450, 1800, 40, 900, _WOOD),
            Part(-900, 0, -450, 60, 710, 60, _DARK),
            Part(840, 0, -450, 60, 710, 60, _DARK),
            Part(-900, 0, 390, 60, 710, 60, _DARK),
            Part(840, 0, 390, 60, 710, 60, _DARK),
        ),
    ),
    CatalogueItem(
        "table-desk",
        "bàn làm việc",
        "table",
        (
            Part(-700, 710, -350, 1400, 40, 700, _WOOD),
            Part(-700, 0, -350, 40, 710, 700, _DARK),
            Part(660, 0, -350, 40, 710, 700, _DARK),
            Part(-660, 300, 310, 1320, 300, 40, _DARK),
        ),
    ),
    CatalogueItem(
        "chair-dining",
        "ghế ăn tựa lưng",
        "chair",
        (
            Part(-225, 430, -260, 450, 40, 520, _RED),
            Part(-225, 0, -260, 40, 430, 40, _WOOD),
            Part(185, 0, -260, 40, 430, 40, _WOOD),
            Part(-225, 0, 220, 40, 880, 40, _WOOD),
            Part(185, 0, 220, 40, 880, 40, _WOOD),
            Part(-185, 600, 220, 370, 240, 40, _WOOD),
        ),
    ),
    CatalogueItem(
        "chair-stool",
        "ghế đẩu",
        "chair",
        (
            Part(-200, 410, -200, 400, 40, 400, _LIGHT),
            Part(-180, 0, -180, 40, 410, 40, _WOOD),
            Part(140, 0, -180, 40, 410, 40, _WOOD),
            Part(-180, 0, 140, 40, 410, 40, _WOOD),
            Part(140, 0, 140, 40, 410, 40, _WOOD),
        ),
    ),
    _bed(1600, "giường đôi 1m6", "bed-double-1600"),
    _bed(1000, "giường đơn 1m", "bed-single-1000"),
    CatalogueItem(
        "sofa-three-seat",
        "sofa ba chỗ",
        "sofa",
        (
            Part(-1000, 0, -400, 60, 100, 60, _DARK),
            Part(940, 0, -400, 60, 100, 60, _DARK),
            Part(-1000, 0, 340, 60, 100, 60, _DARK),
            Part(940, 0, 340, 60, 100, 60, _DARK),
            Part(-1050, 100, -450, 2100, 250, 900, _FABRIC),
            Part(-1050, 350, -450, 200, 250, 900, _FABRIC),
            Part(850, 350, -450, 200, 250, 900, _FABRIC),
            Part(-850, 350, -450, 1700, 500, 200, _FABRIC),
            Part(-850, 350, -250, 560, 100, 700, _CUSHION),
            Part(-280, 350, -250, 560, 100, 700, _CUSHION),
            Part(290, 350, -250, 560, 100, 700, _CUSHION),
        ),
    ),
    CatalogueItem(
        "sofa-armchair",
        "ghế bành",
        "sofa",
        (
            Part(-400, 0, -400, 50, 100, 50, _DARK),
            Part(350, 0, -400, 50, 100, 50, _DARK),
            Part(-400, 0, 350, 50, 100, 50, _DARK),
            Part(350, 0, 350, 50, 100, 50, _DARK),
            Part(-425, 100, -425, 850, 250, 850, _FABRIC),
            Part(-425, 350, -425, 150, 250, 850, _FABRIC),
            Part(275, 350, -425, 150, 250, 850, _FABRIC),
            Part(-275, 350, -425, 550, 500, 180, _FABRIC),
            Part(-275, 350, -245, 550, 100, 670, _CUSHION),
        ),
    ),
    CatalogueItem(
        "storage-wardrobe",
        "tủ quần áo hai cánh",
        "storage",
        (
            Part(-480, 0, -280, 960, 80, 560, _DARK),
            Part(-500, 80, -300, 1000, 1920, 570, _WOOD),
            Part(-495, 100, 270, 490, 1880, 30, _LIGHT),
            Part(5, 100, 270, 490, 1880, 30, _LIGHT),
        ),
    ),
    CatalogueItem(
        "storage-bookshelf",
        "kệ sách năm tầng",
        "storage",
        (
            Part(-400, 0, -150, 30, 1800, 300, _WOOD),
            Part(370, 0, -150, 30, 1800, 300, _WOOD),
            Part(-370, 0, -150, 740, 1800, 20, _DARK),
            Part(-370, 0, -130, 740, 30, 280, _WOOD),
            Part(-370, 350, -130, 740, 30, 280, _WOOD),
            Part(-370, 700, -130, 740, 30, 280, _WOOD),
            Part(-370, 1050, -130, 740, 30, 280, _WOOD),
            Part(-370, 1400, -130, 740, 30, 280, _WOOD),
            Part(-370, 1770, -130, 740, 30, 280, _WOOD),
            Part(-300, 30, -100, 60, 280, 200, _RED),
            Part(-200, 380, -100, 50, 250, 200, _BLUE),
        ),
    ),
    CatalogueItem(
        "sanitary-toilet",
        "bồn cầu",
        "sanitary",
        (
            Part(-200, 150, -350, 400, 630, 150, _WHITE),  # két nước
            Part(-120, 0, -250, 240, 300, 300, _WHITE),  # chân
            Part(-200, 300, -200, 400, 100, 550, _WHITE),  # thân bồn
            Part(-190, 400, -190, 380, 30, 520, _GREY),  # nắp
        ),
    ),
    CatalogueItem(
        "sanitary-basin",
        "chậu rửa mặt",
        "sanitary",
        (
            Part(-150, 0, -150, 300, 20, 300, _GREY),
            Part(-60, 20, -150, 120, 680, 200, _WHITE),
            Part(-300, 700, -225, 600, 150, 450, _WHITE),
        ),
    ),
    CatalogueItem(
        "kitchen-base-cabinet",
        "tủ bếp dưới",
        "kitchen",
        (
            Part(-580, 0, -280, 1160, 100, 560, _DARK),
            Part(-600, 100, -300, 1200, 700, 570, _WHITE),
            Part(-595, 110, 270, 390, 680, 30, _LIGHT),
            Part(-195, 110, 270, 390, 680, 30, _LIGHT),
            Part(205, 110, 270, 390, 680, 30, _LIGHT),
            Part(-600, 800, -300, 1200, 50, 600, _GREY),
        ),
    ),
    CatalogueItem(
        "kitchen-fridge",
        "tủ lạnh",
        "kitchen",
        (
            Part(-350, 0, -350, 700, 1800, 670, _GREY),
            Part(-345, 20, 320, 690, 1100, 20, _WHITE),
            Part(-345, 1130, 320, 690, 650, 20, _WHITE),
            Part(-320, 800, 340, 20, 250, 10, _DARK),
            Part(-320, 1200, 340, 20, 150, 10, _DARK),
        ),
    ),
    CatalogueItem(
        "technical-panel",
        "tủ điện",
        "technical",
        (
            Part(-300, 0, -125, 600, 800, 220, _GREY),
            Part(-290, 10, 95, 580, 780, 20, _WHITE),
            Part(-250, 300, 115, 500, 400, 10, _DARK),
            Part(-40, 650, 115, 80, 60, 10, _RED),
        ),
    ),
    CatalogueItem(
        "technical-water-purifier",
        "máy lọc nước",
        "technical",
        (
            Part(-150, 0, -200, 300, 1000, 360, _WHITE),
            Part(-120, 500, 160, 240, 400, 40, _BLUE),
            Part(-30, 350, 160, 60, 60, 40, _DARK),
            Part(-100, 200, 160, 200, 20, 40, _DARK),
        ),
    ),
)
