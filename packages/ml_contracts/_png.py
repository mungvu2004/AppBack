"""PNG viết tay bằng `zlib` cho mặt nạ 1 bit và ảnh RGB 8 bit (K13).

Không dùng Pillow/OpenCV để **giải** mặt nạ: artifact đi qua ranh giới không tin
(BE-00 §7), nên bộ giải tự kiểm từng thứ trước khi cấp bộ nhớ — chữ ký, CRC mọi chunk,
IHDR đúng khổ đã hẹn, không chunk tới hạn lạ, không rác sau `IEND` — và giải nén với
trần đúng bằng số byte một ảnh khổ đó cần (`h x (1 + ceil(w/8))`), không hơn một byte.
Bộ mã hoá chỉ ghi bộ lọc 0; bộ giải nhận đủ 5 bộ lọc (tệp từ công cụ khác).
"""

import struct
import zlib
from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

MASK_MAX_PIXELS: Final = 40_000_000
PNG_SIGNATURE: Final = b"\x89PNG\r\n\x1a\n"
_IHDR_LENGTH: Final = 13
_KNOWN_CRITICAL: Final = frozenset({b"IHDR", b"IDAT", b"IEND"})
_MAX_CHUNK_LENGTH: Final = 2**31 - 1
_COLOR_GRAY: Final = 0
_COLOR_RGB: Final = 2


@dataclass(frozen=True, slots=True)
class PngHeader:
    """Các trường IHDR cần để quyết định có giải ảnh hay không."""

    width: int
    height: int
    bit_depth: int
    color_type: int
    interlace: int


def _chunk(kind: bytes, data: bytes) -> bytes:
    """Một chunk: độ dài, loại, dữ liệu, CRC-32 của loại + dữ liệu."""
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def _encode(width: int, height: int, bit_depth: int, color_type: int, rows: NDArray[np.uint8]) -> bytes:
    """Ghép PNG từ các dòng đã đóng gói; mọi dòng dùng bộ lọc 0."""
    filtered = np.zeros((height, rows.shape[1] + 1), dtype=np.uint8)
    filtered[:, 1:] = rows
    header = struct.pack(">IIBBBBB", width, height, bit_depth, color_type, 0, 0, 0)
    return b"".join(
        (
            PNG_SIGNATURE,
            _chunk(b"IHDR", header),
            _chunk(b"IDAT", zlib.compress(filtered.tobytes(), 6)),
            _chunk(b"IEND", b""),
        )
    )


def _check_size(height: int, width: int) -> None:
    """Khổ hợp lệ: ít nhất 1x1, không quá `MASK_MAX_PIXELS` điểm."""
    if height < 1 or width < 1 or height * width > MASK_MAX_PIXELS:
        raise ValueError(f"khổ ảnh {width}x{height} ngoài 1..{MASK_MAX_PIXELS} điểm")


def encode_mask(mask: NDArray[np.bool_]) -> bytes:
    """Mặt nạ `(H, W)` bool → PNG xám 1 bit, bit 1 = tường."""
    if mask.ndim != 2 or mask.dtype != np.bool_:
        raise ValueError(f"mặt nạ phải là mảng bool 2 chiều, nhận {mask.dtype} {mask.shape}")
    height, width = mask.shape
    _check_size(height, width)
    return _encode(width, height, 1, _COLOR_GRAY, np.packbits(mask, axis=1))


def encode_rgb_png(pixels: NDArray[np.uint8]) -> bytes:
    """Ảnh `(H, W, 3)` uint8 → PNG RGB 8 bit."""
    if pixels.ndim != 3 or pixels.shape[2] != 3 or pixels.dtype != np.uint8:
        raise ValueError(f"ảnh phải là uint8 (H, W, 3), nhận {pixels.dtype} {pixels.shape}")
    height, width = pixels.shape[:2]
    _check_size(height, width)
    return _encode(width, height, 8, _COLOR_RGB, np.ascontiguousarray(pixels).reshape(height, width * 3))


def read_png_header(data: bytes) -> PngHeader:
    """IHDR của một PNG (chữ ký + chunk đầu, kiểm CRC); không phải PNG → `ValueError`."""
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("thiếu chữ ký PNG")
    kind, body, _ = _read_chunk(data, len(PNG_SIGNATURE))
    if kind != b"IHDR" or len(body) != _IHDR_LENGTH:
        raise ValueError("chunk đầu tiên phải là IHDR 13 byte")
    width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack(">IIBBBBB", body)
    if compression != 0 or filtering != 0:
        raise ValueError("IHDR khai phương pháp nén hay lọc lạ")
    return PngHeader(width, height, bit_depth, color_type, interlace)


def _read_chunk(data: bytes, pos: int) -> tuple[bytes, bytes, int]:
    """(loại, dữ liệu, vị trí chunk kế) — chunk cụt, độ dài quá trần hay sai CRC → `ValueError`."""
    if pos + 12 > len(data):
        raise ValueError("chunk cụt")
    (length,) = struct.unpack(">I", data[pos : pos + 4])
    end = pos + 12 + length
    if length > _MAX_CHUNK_LENGTH or end > len(data):
        raise ValueError("chunk khai độ dài vượt tệp")
    kind = data[pos + 4 : pos + 8]
    if not kind.isalpha():
        raise ValueError(f"loại chunk không phải 4 chữ cái: {kind!r}")
    body = data[pos + 8 : end - 4]
    (crc,) = struct.unpack(">I", data[end - 4 : end])
    if zlib.crc32(kind + body) != crc:
        raise ValueError(f"CRC sai ở chunk {kind!r}")
    return kind, body, end


def _idat_parts(data: bytes) -> list[bytes]:
    """Các khúc IDAT liền nhau; chunk tới hạn lạ, IDAT rời rạc, rác sau `IEND` → `ValueError`."""
    _, _, pos = _read_chunk(data, len(PNG_SIGNATURE))
    parts: list[bytes] = []
    idat_closed = False
    while True:
        kind, body, pos = _read_chunk(data, pos)
        if kind == b"IEND":
            break
        if kind == b"IDAT":
            if idat_closed:
                raise ValueError("các chunk IDAT phải liền nhau")
            parts.append(body)
        elif parts:
            idat_closed = True
        if (kind[0:1].isupper() and kind not in _KNOWN_CRITICAL) or kind == b"IHDR":
            raise ValueError(f"chunk tới hạn không nhận: {kind!r}")
    if pos != len(data):
        raise ValueError("có dữ liệu sau IEND")
    if not parts:
        raise ValueError("thiếu IDAT")
    return parts


def _inflate(parts: list[bytes], expected: int) -> bytes:
    """Giải nén với trần `expected` byte: dòng dữ liệu dài hơn, ngắn hơn hay cụt → `ValueError`."""
    inflater = zlib.decompressobj()
    out = bytearray()
    for part in parts:
        try:
            out += inflater.decompress(part, expected - len(out) + 1)
        except zlib.error as exc:
            raise ValueError("dòng zlib hỏng") from exc
        if len(out) > expected:
            raise ValueError("dữ liệu ảnh dài hơn khổ đã khai")
    if not inflater.eof or inflater.unused_data or len(out) != expected:
        raise ValueError("dòng zlib cụt hoặc có rác sau cuối")
    return bytes(out)


def _paeth(left: int, up: int, up_left: int) -> int:
    """Bộ đoán Paeth của PNG."""
    estimate = left + up - up_left
    distances = (abs(estimate - left), abs(estimate - up), abs(estimate - up_left))
    if distances[0] <= distances[1] and distances[0] <= distances[2]:
        return left
    return up if distances[1] <= distances[2] else up_left


def _unfilter_row(kind: int, row: NDArray[np.uint8], prior: NDArray[np.uint8]) -> NDArray[np.uint8]:
    """Bỏ lọc một dòng với bước 1 byte (ảnh 1 bit).

    Bộ lọc 3, 4 đi từng byte bằng Python: chậm có chủ ý, vì bộ mã hoá của ta và Pillow
    (1 bit) chỉ ghi bộ lọc 0. Ngưỡng: mặt nạ 40 MP toàn Paeth ≈ 5 MB → vài giây;
    nâng cấp khi có nguồn thật ghi bộ lọc 3/4 thì viết lại bằng vòng numpy theo cột.
    """
    if kind == 0:
        return row
    if kind == 1:
        return np.add.accumulate(row, dtype=np.uint8)
    if kind == 2:
        return row + prior
    out = np.empty_like(row)
    left = 0
    for index in range(row.shape[0]):
        up = int(prior[index])
        up_left = int(prior[index - 1]) if index else 0
        guess = (left + up) // 2 if kind == 3 else _paeth(left, up, up_left)
        left = (int(row[index]) + guess) & 0xFF
        out[index] = left
    return out


def decode_mask(data: bytes, *, width_px: int, height_px: int) -> NDArray[np.bool_]:
    """PNG xám 1 bit của `encode_mask` → mặt nạ `(height_px, width_px)`; mọi sai lệch → `ValueError`.

    Khổ phải **đúng** khổ người gọi hẹn: artifact của lượt khác hay bị tráo không lọt qua.
    """
    _check_size(height_px, width_px)
    header = read_png_header(data)
    if (header.width, header.height) != (width_px, height_px):
        raise ValueError(f"IHDR {header.width}x{header.height} ≠ khổ hẹn {width_px}x{height_px}")
    if (header.bit_depth, header.color_type, header.interlace) != (1, _COLOR_GRAY, 0):
        raise ValueError("mặt nạ phải là PNG xám 1 bit, không đan xen")
    stride = (width_px + 7) // 8
    raw = np.frombuffer(_inflate(_idat_parts(data), height_px * (1 + stride)), dtype=np.uint8)
    rows = raw.reshape(height_px, stride + 1)
    if int(rows[:, 0].max()) > 4:
        raise ValueError("bộ lọc PNG lạ")
    packed = np.empty((height_px, stride), dtype=np.uint8)
    prior = np.zeros(stride, dtype=np.uint8)
    for index in range(height_px):
        prior = _unfilter_row(int(rows[index, 0]), rows[index, 1:], prior)
        packed[index] = prior
    return np.unpackbits(packed, axis=1)[:, :width_px].astype(np.bool_)
