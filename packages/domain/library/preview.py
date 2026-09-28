"""Ảnh xem trước PNG của một mục danh mục: nhìn từ trên xuống, chỉ thư viện chuẩn.

Bất biến: tất định (cùng mục, cùng `size` → cùng byte), tỉ lệ X:Z giữ nguyên, vừa khung
vuông `size x size` với lề nhỏ. Khối có đỉnh `y + height` cao hơn vẽ sau nên che khối thấp
ở pixel chồng nhau, đúng như nhìn từ trên xuống.
"""

import struct
import zlib

from packages.domain.library.catalogue import CatalogueItem, part_bounds

MIN_PREVIEW_SIZE = 16
_BACKGROUND = (245, 245, 245)
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _chunk(tag: bytes, payload: bytes) -> bytes:
    """Một chunk PNG: độ dài, loại, dữ liệu, CRC32 trên loại + dữ liệu."""
    return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", zlib.crc32(tag + payload))


def build_preview_png(item: CatalogueItem, size: int = 128) -> bytes:
    """PNG RGB 8 bit `size x size` của `item` nhìn từ trên xuống (X sang phải, Z xuống dưới).

    Filter 0 mọi dòng, một IDAT. Ném `ValueError` khi `size` < 16 (ảnh không đọc được) hoặc
    mục không có khối.
    """
    if size < MIN_PREVIEW_SIZE:
        raise ValueError(f"size phải ≥ {MIN_PREVIEW_SIZE}, nhận {size}")
    (min_x, _, min_z), (max_x, _, max_z) = part_bounds(item)
    margin = size // MIN_PREVIEW_SIZE
    scale = (size - 2 * margin) / max(max_x - min_x, max_z - min_z)
    off_x = (size - (max_x - min_x) * scale) / 2
    off_z = (size - (max_z - min_z) * scale) / 2
    rows = [bytearray(bytes(_BACKGROUND) * size) for _ in range(size)]
    for part in sorted(item.parts, key=lambda p: p.y_mm + p.height_mm):
        x0 = round(off_x + (part.x_mm - min_x) * scale)
        x1 = max(round(off_x + (part.x_mm + part.width_mm - min_x) * scale), x0 + 1)
        z0 = round(off_z + (part.z_mm - min_z) * scale)
        z1 = max(round(off_z + (part.z_mm + part.depth_mm - min_z) * scale), z0 + 1)
        span = bytes(part.rgb) * (x1 - x0)
        for z in range(z0, z1):
            rows[z][3 * x0 : 3 * x1] = span
    raw = b"".join(b"\x00" + bytes(row) for row in rows)
    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return _PNG_SIGNATURE + _chunk(b"IHDR", header) + _chunk(b"IDAT", zlib.compress(raw)) + _chunk(b"IEND", b"")
