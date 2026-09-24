"""Test đơn vị của `apps/api/me/avatar.py` — pipeline N14 và `avatar_url` (B1-04 [6], CASE T-avatar)."""

import asyncio
import io
import os
import struct
import zlib
from collections.abc import Iterator
from typing import Final

import pytest
from PIL import Image, ImageFile

from apps.api.me import avatar
from apps.api.me.avatar import (
    MAX_DECODED_BYTES,
    ProcessedAvatar,
    avatar_url,
    process_avatar,
    reset_avatar_settings_cache,
)
from apps.api.me.tests.support import (
    b64,
    jpeg_bytes,
    jpeg_with_exif_orientation,
    jpeg_with_icc_and_exif_bytes,
    noisy_jpeg_bytes,
    png_bytes,
    png_with_icc_bytes,
)
from packages.core.errors import AppError
from packages.storage.local import LocalDiskStorage

PNG_SIG: Final = b"\x89PNG\r\n\x1a\n"


def _png_with_declared_size(real_png: bytes, width: int, height: int) -> bytes:
    """Chép một PNG thật nhưng ghi đè `width`/`height` khai trong `IHDR` (CRC tính lại)."""
    assert real_png[:8] == PNG_SIG
    length = int.from_bytes(real_png[8:12], "big")
    ctype = real_png[12:16]
    assert ctype == b"IHDR"
    data = real_png[16 : 16 + length]
    new_data = struct.pack(">II", width, height) + data[8:]
    new_crc = zlib.crc32(ctype + new_data) & 0xFFFFFFFF
    new_chunk = struct.pack(">I", length) + ctype + new_data + struct.pack(">I", new_crc)
    return real_png[:8] + new_chunk + real_png[16 + length + 4 :]


@pytest.fixture(autouse=True)
def _reset_concurrency(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """`AVATAR_DECODE_CONCURRENCY` mặc định giữa các test — không rò `monkeypatch.setenv`."""
    monkeypatch.delenv("AVATAR_DECODE_CONCURRENCY", raising=False)
    reset_avatar_settings_cache()
    yield
    reset_avatar_settings_cache()


async def test_process_avatar_png_ok() -> None:
    """PNG 64x64 hợp lệ → xử lý xong, đúng loại/đuôi/content-type, không EXIF."""
    result = await process_avatar(b64(png_bytes((64, 64))), "image/png")
    assert isinstance(result, ProcessedAvatar)
    assert result.kind == "png"
    assert result.ext == "png"
    assert result.content_type == "image/png"
    with Image.open(io.BytesIO(result.data)) as out:
        assert out.size == (64, 64)
        assert out.getexif() == {}


async def test_process_avatar_jpeg_ok() -> None:
    """JPEG 64x64 hợp lệ → xử lý xong."""
    result = await process_avatar(b64(jpeg_bytes((64, 64))), "image/jpeg")
    assert result.kind == "jpeg"
    assert result.ext == "jpg"


async def test_process_avatar_downsizes_large_image() -> None:
    """Ảnh lớn hơn 512x512 được thu nhỏ về trong khung 512x512 (thumbnail)."""
    result = await process_avatar(b64(png_bytes((2000, 1000))), "image/png")
    with Image.open(io.BytesIO(result.data)) as out:
        assert out.width <= 512
        assert out.height <= 512


async def test_process_avatar_exif_orientation_applied_and_stripped() -> None:
    """JPEG có EXIF `Orientation=6` → ảnh lưu đã xoay 90°, không còn EXIF ("Không giữ EXIF")."""
    raw = jpeg_with_exif_orientation((40, 20))
    result = await process_avatar(b64(raw), "image/jpeg")
    with Image.open(io.BytesIO(result.data)) as out:
        assert out.size == (20, 40)  # xoay 90°: rộng↔cao đảo chỗ
        assert out.getexif() == {}


async def test_process_avatar_png_strips_icc_profile() -> None:
    """PNG có `icc_profile` → ảnh lưu không còn `icc_profile` trong `info` (NO-166)."""
    raw = png_with_icc_bytes((64, 64))
    with Image.open(io.BytesIO(raw)) as src:
        assert "icc_profile" in src.info  # ảnh vào thật sự có ICC, không phải test giả
    result = await process_avatar(b64(raw), "image/png")
    with Image.open(io.BytesIO(result.data)) as out:
        assert "icc_profile" not in out.info
        assert "exif" not in out.info


async def test_process_avatar_jpeg_strips_icc_profile_and_exif() -> None:
    """JPEG có cả `icc_profile` và EXIF → ảnh lưu không còn khoá metadata nào (NO-166)."""
    raw = jpeg_with_icc_and_exif_bytes((64, 64))
    with Image.open(io.BytesIO(raw)) as src:
        assert "icc_profile" in src.info  # ảnh vào thật sự có ICC, không phải test giả
    result = await process_avatar(b64(raw), "image/jpeg")
    with Image.open(io.BytesIO(result.data)) as out:
        assert "icc_profile" not in out.info
        assert out.getexif() == {}


async def test_process_avatar_mime_mismatch_is_type_mismatch() -> None:
    """PNG khai `image/jpeg` → `FILE_TYPE_MISMATCH`."""
    with pytest.raises(AppError) as excinfo:
        await process_avatar(b64(png_bytes()), "image/jpeg")
    assert excinfo.value.code.code == "FILE_TYPE_MISMATCH"


@pytest.mark.parametrize(
    "head",
    [b"GIF89a" + b"\x00" * 58, b"RIFF" + b"\x00" * 4 + b"WEBP" + b"\x00" * 54, b"BM" + b"\x00" * 62],
)
async def test_process_avatar_gif_webp_bmp_is_unsupported(head: bytes) -> None:
    """GIF/WebP/BMP → `AVATAR_TYPE_UNSUPPORTED` (đính chính [1].1 của prompt — `sniff()` không nhận ra)."""
    with pytest.raises(AppError) as excinfo:
        await process_avatar(b64(head), "image/png")
    assert excinfo.value.code.code == "AVATAR_TYPE_UNSUPPORTED"


async def test_process_avatar_pdf_is_type_mismatch_not_unsupported() -> None:
    """`sniff()` nhận ra `pdf` (không phải ảnh) → `FILE_TYPE_MISMATCH`, không phải `AVATAR_TYPE_UNSUPPORTED`."""
    with pytest.raises(AppError) as excinfo:
        await process_avatar(b64(b"%PDF-1.4\n" + b"\x00" * 50), "image/png")
    assert excinfo.value.code.code == "FILE_TYPE_MISMATCH"


async def test_process_avatar_unknown_garbage_is_type_mismatch() -> None:
    """Không nhận diện được, không khớp bảng chữ ký phụ → `FILE_TYPE_MISMATCH`."""
    with pytest.raises(AppError) as excinfo:
        await process_avatar(b64(b"\x01\x02\x03" * 20), "image/png")
    assert excinfo.value.code.code == "FILE_TYPE_MISMATCH"


async def test_process_avatar_malformed_base64_is_validation() -> None:
    """Base64 hỏng → 422 `VALIDATION` `field:"contentBase64"`."""
    with pytest.raises(AppError) as excinfo:
        await process_avatar("!!!khong-phai-base64!!!", "image/png")
    assert excinfo.value.code.code == "VALIDATION"
    assert excinfo.value.params["field"] == "contentBase64"


async def test_process_avatar_decoded_too_large_is_image_too_large() -> None:
    """Giải mã > 512 KiB → `IMAGE_TOO_LARGE`, trước cả khi sniff."""
    raw = PNG_SIG + b"\x00" * (MAX_DECODED_BYTES + 1)
    with pytest.raises(AppError) as excinfo:
        await process_avatar(b64(raw), "image/png")
    assert excinfo.value.code.code == "IMAGE_TOO_LARGE"


async def test_process_avatar_wide_dimensions_exceeded() -> None:
    """5000x10 (rộng > 4096) → `AVATAR_DIMENSIONS_EXCEEDED`."""
    with pytest.raises(AppError) as excinfo:
        await process_avatar(b64(png_bytes((5000, 10))), "image/png")
    assert excinfo.value.code.code == "AVATAR_DIMENSIONS_EXCEEDED"


async def test_process_avatar_pixel_count_exceeded_without_pillow_bomb() -> None:
    """6500x6500 (42,25 Mpx > 40 Mpx của ta, dưới trần bom nén mặc định của Pillow) → `IMAGE_TOO_LARGE`."""
    with pytest.raises(AppError) as excinfo:
        await process_avatar(b64(png_bytes((6500, 6500))), "image/png")
    assert excinfo.value.code.code == "IMAGE_TOO_LARGE"


async def test_process_avatar_huge_declared_dims_is_too_large_and_decoder_never_called(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PNG đầu tệp khai 20000x20000 → `IMAGE_TOO_LARGE`; bộ giải mã (`ImageFile.load`) không được gọi."""
    calls = 0
    original_load = ImageFile.ImageFile.load

    def _counting_load(self: ImageFile.ImageFile) -> object:
        nonlocal calls
        calls += 1
        return original_load(self)

    monkeypatch.setattr(ImageFile.ImageFile, "load", _counting_load)
    huge = _png_with_declared_size(png_bytes((1, 1)), 20000, 20000)
    with pytest.raises(AppError) as excinfo:
        await process_avatar(b64(huge), "image/png")
    assert excinfo.value.code.code == "IMAGE_TOO_LARGE"
    assert calls == 0


async def test_process_avatar_cmyk_downgrades_to_8bit_rgb() -> None:
    """Ảnh CMYK → chuẩn hoá RGB 8-bit (U02)."""
    cmyk = Image.new("CMYK", (32, 32), (10, 20, 30, 0))
    buffer = io.BytesIO()
    cmyk.save(buffer, format="JPEG")
    result = await process_avatar(b64(buffer.getvalue()), "image/jpeg")
    with Image.open(io.BytesIO(result.data)) as out:
        assert out.mode == "RGB"


async def test_process_avatar_truncated_before_header_is_file_corrupt() -> None:
    """Tệp cụt ngay đầu (chưa tới `SOF`, `w x h` chưa đọc được) → `FILE_CORRUPT` ở bước kiểm kích thước."""
    truncated = jpeg_bytes((64, 64))[:16]
    with pytest.raises(AppError) as excinfo:
        await process_avatar(b64(truncated), "image/jpeg")
    assert excinfo.value.code.code == "FILE_CORRUPT"


async def test_process_avatar_truncated_after_header_is_file_corrupt() -> None:
    """Tệp cụt sau khi đã đọc được `w x h` nhưng trước khi hết dữ liệu quét → `FILE_CORRUPT` ở bước giải mã (U07)."""
    truncated = noisy_jpeg_bytes((64, 64))[:700]
    with pytest.raises(AppError) as excinfo:
        await process_avatar(b64(truncated), "image/jpeg")
    assert excinfo.value.code.code == "FILE_CORRUPT"


async def test_process_avatar_concurrency_gate_returns_503(monkeypatch: pytest.MonkeyPatch) -> None:
    """`AVATAR_DECODE_CONCURRENCY=1` + một luồng giữ chỗ quá hạn chờ → lượt thứ hai 503."""
    monkeypatch.setenv("AVATAR_DECODE_CONCURRENCY", "1")
    reset_avatar_settings_cache()
    monkeypatch.setattr(avatar, "_DECODE_WAIT_S", 0.05)

    async def _hold_slot() -> None:
        async with avatar._decode_slot():
            await asyncio.sleep(0.2)

    holder = asyncio.create_task(_hold_slot())
    await asyncio.sleep(0.02)
    with pytest.raises(AppError) as excinfo:
        await process_avatar(b64(png_bytes()), "image/png")
    assert excinfo.value.code.code == "DEPENDENCY_UNAVAILABLE"
    await holder


def test_avatar_decode_concurrency_env_invalid_rejects() -> None:
    """`AVATAR_DECODE_CONCURRENCY` < 1 → `ValueError` ngay lúc đọc cấu hình (fail-closed)."""
    old = os.environ.get("AVATAR_DECODE_CONCURRENCY")
    os.environ["AVATAR_DECODE_CONCURRENCY"] = "0"
    reset_avatar_settings_cache()
    try:
        with pytest.raises(ValueError, match="AVATAR_DECODE_CONCURRENCY"):
            avatar._decode_concurrency()
    finally:
        if old is None:
            del os.environ["AVATAR_DECODE_CONCURRENCY"]
        else:
            os.environ["AVATAR_DECODE_CONCURRENCY"] = old
        reset_avatar_settings_cache()


async def test_avatar_url_none_when_no_key(local_storage: LocalDiskStorage) -> None:
    """`avatar_key=None` → `avatar_url` trả `None`."""
    assert await avatar_url(local_storage, None) is None


async def test_avatar_url_absolute_and_no_stat_call(
    local_storage: LocalDiskStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Backend `local` ra URL tuyệt đối `/api/files/…`; không gọi `stat` (B0-04, K15)."""
    key = "users/usr_00000000000000000000000000/avatar/00000000000000000000000000.png"
    await local_storage.put(key, png_bytes(), content_type="image/png", max_bytes=2 * 1024 * 1024)

    calls = 0
    original_stat = local_storage.stat

    async def _counting_stat(k: str) -> object:
        nonlocal calls
        calls += 1
        return await original_stat(k)

    monkeypatch.setattr(local_storage, "stat", _counting_stat)
    url = await avatar_url(local_storage, key)
    assert url is not None
    assert url.startswith("https://appback.test/api/files/")
    assert calls == 0
