"""PNG mặt nạ viết tay: khứ hồi, đủ 5 bộ lọc (Pillow làm bộ giải đối chứng), từ chối mọi sai lệch (K13)."""

import io
import random
import struct
import zlib

import numpy as np
import pytest
from numpy.typing import NDArray
from PIL import Image

from packages.ml_contracts._png import MASK_MAX_PIXELS, PNG_SIGNATURE, _chunk, _paeth
from packages.ml_contracts.artifacts import decode_mask, encode_mask, encode_rgb_png, read_png_header


def random_mask(seed: int, height: int, width: int) -> NDArray[np.bool_]:
    """Mặt nạ ngẫu nhiên tất định (BE-00 §9: `random.Random`, không `numpy.random`)."""
    rng = random.Random(seed)  # noqa: S311 — dữ liệu thử tất định
    bits = np.unpackbits(np.frombuffer(rng.randbytes((height * width + 7) // 8), dtype=np.uint8))
    return bits[: height * width].reshape(height, width).astype(np.bool_)


def png(
    width: int,
    height: int,
    stream: bytes,
    *,
    ihdr: bytes | None = None,
    before_idat: tuple[bytes, ...] = (),
    idat_parts: int = 1,
    after: bytes = b"",
) -> bytes:
    """PNG dựng tay từ dòng zlib đã có, để chèn chunk và sai lệch tuỳ ý."""
    header = ihdr if ihdr is not None else struct.pack(">IIBBBBB", width, height, 1, 0, 0, 0, 0)
    size = max(1, -(-len(stream) // idat_parts))
    idats = [_chunk(b"IDAT", stream[i : i + size]) for i in range(0, len(stream), size)]
    return b"".join((PNG_SIGNATURE, _chunk(b"IHDR", header), *before_idat, *idats, _chunk(b"IEND", b""), after))


def filtered_rows(mask: NDArray[np.bool_], kind: int) -> bytes:
    """Dòng đã lọc bằng bộ lọc `kind` (bước 1 byte), cài theo đặc tả PNG làm chiều thuận."""
    packed = np.packbits(mask, axis=1).astype(np.int32)
    prior = np.zeros(packed.shape[1], dtype=np.int32)
    out = bytearray()
    for row in packed:
        left = np.concatenate(([0], row[:-1]))
        up_left = np.concatenate(([0], prior[:-1]))
        if kind == 0:
            guess = np.zeros_like(row)
        elif kind == 1:
            guess = left
        elif kind == 2:
            guess = prior
        elif kind == 3:
            guess = (left + prior) // 2
        else:
            guess = np.array([_paeth(int(a), int(b), int(c)) for a, b, c in zip(left, prior, up_left, strict=True)])
        out += bytes([kind]) + bytes(((row - guess) & 0xFF).astype(np.uint8))
        prior = row
    return bytes(out)


@pytest.mark.parametrize(("height", "width"), [(1, 1), (3, 7), (1200, 1600)])
def test_mask_png_roundtrip(height: int, width: int) -> None:
    mask = random_mask(height * width, height, width)
    data = encode_mask(mask)
    assert read_png_header(data).bit_depth == 1
    assert np.array_equal(decode_mask(data, width_px=width, height_px=height), mask)
    assert np.array_equal(np.array(Image.open(io.BytesIO(data))), mask)


def test_rgb_png_decodes_with_pillow() -> None:
    pixels = (random_mask(7, 5, 9)[:, :, None] * np.array([255, 128, 1], dtype=np.uint8)).astype(np.uint8)
    decoded = np.array(Image.open(io.BytesIO(encode_rgb_png(pixels))).convert("RGB"))
    assert np.array_equal(decoded, pixels)


@pytest.mark.parametrize("kind", [0, 1, 2, 3, 4])
def test_decode_mask_pillow_filters(kind: int) -> None:
    """Mọi bộ lọc PNG cho cùng mặt nạ; Pillow giải cùng tệp làm đối chứng."""
    mask = random_mask(kind, 9, 21)
    data = png(21, 9, zlib.compress(filtered_rows(mask, kind)))
    assert np.array_equal(np.array(Image.open(io.BytesIO(data))), mask)
    assert np.array_equal(decode_mask(data, width_px=21, height_px=9), mask)


def test_decode_mask_reads_pillow_output() -> None:
    mask = random_mask(3, 17, 33)
    buffer = io.BytesIO()
    Image.fromarray(mask).save(buffer, format="PNG")
    assert np.array_equal(decode_mask(buffer.getvalue(), width_px=33, height_px=17), mask)


def test_decode_mask_accepts_ancillary_and_split_idat() -> None:
    mask = random_mask(4, 6, 10)
    stream = zlib.compress(filtered_rows(mask, 0))
    data = png(10, 6, stream, before_idat=(_chunk(b"tEXt", b"k\x00v"),), idat_parts=3)
    assert np.array_equal(decode_mask(data, width_px=10, height_px=6), mask)


GOOD_STREAM = zlib.compress(bytes(3 * 2))  # 3 dòng, mỗi dòng 1 byte lọc + 1 byte điểm


def _flip_last_crc(data: bytes) -> bytes:
    """Đổi một byte trong CRC của IEND."""
    return data[:-1] + bytes([data[-1] ^ 1])


@pytest.mark.parametrize(
    ("data", "match"),
    [
        (b"not a png at all", "chữ ký"),
        (_flip_last_crc(png(5, 3, GOOD_STREAM)), "CRC"),
        (png(5, 3, GOOD_STREAM)[:-4], "chunk"),
        (png(5, 3, GOOD_STREAM, after=b"junk"), "sau IEND"),
        (png(5, 3, GOOD_STREAM, before_idat=(_chunk(b"PLTE", b"\x00\x00\x00"),)), "tới hạn"),
        (png(5, 3, GOOD_STREAM, before_idat=(_chunk(b"ABCD", b""),)), "tới hạn"),
        (png(5, 3, GOOD_STREAM, before_idat=(_chunk(b"IHDR", b"x" * 13),)), "tới hạn"),
        (png(5, 3, GOOD_STREAM, before_idat=(_chunk(b"ab1d", b""),)), "4 chữ cái"),
        (png(5, 3, b"", idat_parts=1), "thiếu IDAT"),
        (png(5, 3, GOOD_STREAM + b"junk"), "rác sau cuối"),
        (png(5, 3, zlib.compress(bytes(5))), "cụt"),
        (png(5, 3, zlib.compress(bytes(7))), "dài hơn"),
        (png(5, 3, b"\x00\x01\x02\x03"), "zlib hỏng"),
        (png(5, 3, zlib.compress(bytes([5, 0] * 3))), "bộ lọc"),
        (png(5, 3, GOOD_STREAM, ihdr=struct.pack(">IIBBBBB", 5, 3, 8, 0, 0, 0, 0)), "1 bit"),
        (png(5, 3, GOOD_STREAM, ihdr=struct.pack(">IIBBBBB", 5, 3, 1, 0, 0, 0, 1)), "1 bit"),
        (png(5, 3, GOOD_STREAM, ihdr=struct.pack(">IIBBBBB", 5, 3, 1, 0, 1, 0, 0)), "nén hay lọc"),
        (png(5, 3, GOOD_STREAM, ihdr=b"short"), "IHDR 13"),
        (png(6, 3, GOOD_STREAM), "khổ hẹn"),
    ],
)
def test_decode_mask_rejects(data: bytes, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        decode_mask(data, width_px=5, height_px=3)


def test_decode_mask_rejects_discontiguous_idat() -> None:
    stream = GOOD_STREAM
    data = b"".join(
        (
            PNG_SIGNATURE,
            _chunk(b"IHDR", struct.pack(">IIBBBBB", 5, 3, 1, 0, 0, 0, 0)),
            _chunk(b"IDAT", stream[:4]),
            _chunk(b"tEXt", b"k\x00v"),
            _chunk(b"IDAT", stream[4:]),
            _chunk(b"IEND", b""),
        )
    )
    with pytest.raises(ValueError, match="liền nhau"):
        decode_mask(data, width_px=5, height_px=3)


def test_decode_mask_rejects_first_chunk_other_than_ihdr() -> None:
    data = PNG_SIGNATURE + _chunk(b"IDAT", GOOD_STREAM) + _chunk(b"IEND", b"")
    with pytest.raises(ValueError, match="IHDR"):
        decode_mask(data, width_px=5, height_px=3)


def test_decode_mask_stops_a_zip_bomb_at_the_cap() -> None:
    """50 MB số 0 nén còn ~50 KB; bộ giải dừng ở trần của khổ 10x10, không bung hết."""
    data = png(10, 10, zlib.compress(bytes(50 * 1024 * 1024), 9))
    with pytest.raises(ValueError, match="dài hơn"):
        decode_mask(data, width_px=10, height_px=10)


@pytest.mark.parametrize(("width", "height"), [(0, 5), (5, 0), (MASK_MAX_PIXELS + 1, 1)])
def test_decode_mask_rejects_size_outside_cap(width: int, height: int) -> None:
    with pytest.raises(ValueError, match="khổ ảnh"):
        decode_mask(png(5, 3, GOOD_STREAM), width_px=width, height_px=height)


@pytest.mark.parametrize(
    "mask",
    [
        np.zeros((3, 3), dtype=np.uint8),
        np.zeros(3, dtype=np.bool_),
        np.zeros((0, 3), dtype=np.bool_),
    ],
)
def test_encode_mask_rejects_bad_arrays(mask: NDArray[np.generic]) -> None:
    with pytest.raises(ValueError, match=r"mặt nạ|khổ ảnh"):
        encode_mask(mask)  # type: ignore[arg-type]  # cố ý truyền sai kiểu


@pytest.mark.parametrize(
    "pixels",
    [np.zeros((2, 2), dtype=np.uint8), np.zeros((2, 2, 4), dtype=np.uint8), np.zeros((2, 2, 3), dtype=np.float32)],
)
def test_encode_rgb_png_rejects_bad_arrays(pixels: NDArray[np.generic]) -> None:
    with pytest.raises(ValueError, match="uint8"):
        encode_rgb_png(pixels)  # type: ignore[arg-type]  # cố ý truyền sai kiểu
