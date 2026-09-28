"""`build_preview_png`: chữ ký, IHDR, CRC từng chunk, dữ liệu điểm ảnh, thứ tự vẽ và lỗi `size`."""

import struct
import zlib

import pytest

from packages.domain.library import CATALOGUE, CatalogueItem, Part, build_preview_png

SIGNATURE = b"\x89PNG\r\n\x1a\n"
BACKGROUND = (245, 245, 245)


def read_png(data: bytes) -> tuple[tuple[int, int], list[list[tuple[int, int, int]]]]:
    """Đọc PNG do `build_preview_png` sinh: kiểm chữ ký, CRC, IHDR, filter 0; trả `((w, h), hàng pixel)`."""
    assert data[:8] == SIGNATURE
    offset, chunks = 8, []
    while offset < len(data):
        (length,) = struct.unpack_from(">I", data, offset)
        tag = data[offset + 4 : offset + 8]
        payload = data[offset + 8 : offset + 8 + length]
        (crc,) = struct.unpack_from(">I", data, offset + 8 + length)
        assert crc == zlib.crc32(tag + payload)
        chunks.append((tag, payload))
        offset += 12 + length
    assert offset == len(data)
    assert [t for t, _ in chunks] == [b"IHDR", b"IDAT", b"IEND"]
    assert chunks[2][1] == b""
    width, height, depth, colour, comp, filt, interlace = struct.unpack(">IIBBBBB", chunks[0][1])
    assert (depth, colour, comp, filt, interlace) == (8, 2, 0, 0, 0)
    raw = zlib.decompress(chunks[1][1])
    stride = 1 + 3 * width
    assert len(raw) == height * stride
    rows = []
    for y in range(height):
        line = raw[y * stride : (y + 1) * stride]
        assert line[0] == 0
        rows.append([(line[1 + 3 * x], line[2 + 3 * x], line[3 + 3 * x]) for x in range(width)])
    return (width, height), rows


@pytest.mark.parametrize("item", CATALOGUE, ids=lambda i: i.id)
def test_preview_png_structure(item: CatalogueItem) -> None:
    """128 x 128, có nền và có màu khối; viền ngoài (lề) là nền."""
    (w, h), rows = read_png(build_preview_png(item))
    assert (w, h) == (128, 128)
    pixels = {p for row in rows for p in row}
    assert BACKGROUND in pixels
    assert {p.rgb for p in item.parts} & pixels
    assert all(px == BACKGROUND for px in rows[0] + rows[-1])
    assert all(row[0] == BACKGROUND and row[-1] == BACKGROUND for row in rows)


@pytest.mark.parametrize("item", CATALOGUE, ids=lambda i: i.id)
def test_preview_png_is_deterministic(item: CatalogueItem) -> None:
    """Cùng mục cùng `size` → cùng byte."""
    assert build_preview_png(item) == build_preview_png(item)


def test_preview_png_custom_size_and_aspect() -> None:
    """`size` khác 128 dựng đúng khung; mục dài (giường) giữ tỉ lệ: cao hơn rộng trên ảnh."""
    bed = next(i for i in CATALOGUE if i.id == "bed-single-1000")
    (w, h), rows = read_png(build_preview_png(bed, size=64))
    assert (w, h) == (64, 64)
    filled = [(x, y) for y, row in enumerate(rows) for x, px in enumerate(row) if px != BACKGROUND]
    span_x = max(x for x, _ in filled) - min(x for x, _ in filled) + 1
    span_y = max(y for _, y in filled) - min(y for _, y in filled) + 1
    assert span_y == pytest.approx(2 * span_x, abs=2)


def test_preview_png_taller_part_wins_overlap() -> None:
    """Hai khối chồng nhau: khối có đỉnh cao hơn thắng, bất kể thứ tự khai báo."""
    low = Part(-100, 0, -100, 200, 10, 200, (10, 20, 30))
    high = Part(-50, 0, -50, 100, 500, 100, (200, 100, 50))
    for parts in ((low, high), (high, low)):
        _, rows = read_png(build_preview_png(CatalogueItem("x", "x", "table", parts), size=64))
        assert rows[32][32] == high.rgb
        assert low.rgb in {p for row in rows for p in row}


def test_preview_png_tiny_part_still_visible() -> None:
    """Khối nhỏ hơn một điểm ảnh vẫn chiếm tối thiểu một điểm."""
    big = Part(-5000, 0, -5000, 10000, 10, 10000, (1, 1, 1))
    tiny = Part(0, 0, 0, 1, 500, 1, (9, 9, 9))
    _, rows = read_png(build_preview_png(CatalogueItem("x", "x", "table", (big, tiny)), size=16))
    assert (9, 9, 9) in {p for row in rows for p in row}


@pytest.mark.parametrize("size", [15, 0, -1])
def test_preview_png_rejects_small_size(size: int) -> None:
    """`size` < 16 → `ValueError`; 16 là biên nhỏ nhất hợp lệ."""
    with pytest.raises(ValueError, match="size"):
        build_preview_png(CATALOGUE[0], size=size)
    assert build_preview_png(CATALOGUE[0], size=16)[:8] == SIGNATURE


def test_preview_png_rejects_item_without_parts() -> None:
    """Mục không khối → `ValueError` (không có hộp bao để canh tỉ lệ)."""
    with pytest.raises(ValueError, match="không có khối"):
        build_preview_png(CatalogueItem("empty", "rỗng", "table", ()))
