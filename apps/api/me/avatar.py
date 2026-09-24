"""Xử lý ảnh đại diện: giải mã, kiểm, mã hoá lại (B1-04 [6] bước N14, BE-00 §8, §11, K13, K14).

- **Nhận dạng loại ảnh:** `sniff()` của `packages/storage/sniff.py` không phân biệt được
  GIF/WebP/BMP/TIFF (đều ra `"unknown"`, gói đó cấm sửa). Ở đây so thêm bảng chữ ký cục bộ:
  trùng một trong bốn loại đó → `AVATAR_TYPE_UNSUPPORTED`; nhận diện được nhưng không phải
  PNG/JPEG khớp `mimeType` khai → `FILE_TYPE_MISMATCH` (đính chính [1].1 của prompt).
- **Kiểm kích thước tường minh trước `load()`:** `Image.open(..., formats=[...])` chỉ đọc
  đầu tệp; so `w x h` với trần **trước khi** gọi `.load()` (K13). Không bao giờ gán
  `Image.MAX_IMAGE_PIXELS` hay `ImageFile.LOAD_TRUNCATED_IMAGES = True` (biến toàn cục
  không an toàn luồng của cả tiến trình API).
- **Semaphore giải mã theo vòng sự kiện:** chép khuôn `apps/api/auth/passwords.py` (K36,
  BE-00 §7): `AVATAR_DECODE_CONCURRENCY` (mặc định 2) chỗ giữ trong executor; chờ quá 2 s →
  503 `DEPENDENCY_UNAVAILABLE`. Toàn bộ pipeline (giải mã base64, kiểm magic bytes, kiểm
  kích thước, giải mã Pillow, mã hoá lại) chạy trong **một** `asyncio.to_thread`, dưới
  semaphore đó — không có bước nào đụng ảnh trên vòng sự kiện.
- **Không giữ EXIF/ICC:** `Image.convert`/`thumbnail` chép `self.info` (kể cả `icc_profile`)
  sang ảnh mới, và bộ ghi PNG/JPEG của Pillow rơi về `im.info` khi không truyền `exif=`/
  `icc_profile=` cho `save()` — nên phải xoá hẳn `final.info` **trước** khi lưu (NO-166), không
  chỉ đơn thuần "không truyền gì vào `save`". GPS trong EXIF gốc và ICC profile gốc vì vậy
  không bao giờ lọt ra ngoài.
"""

import asyncio
import base64
import binascii
import io
import os
import struct
import weakref
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import cache
from typing import Final, Literal

from PIL import Image, ImageFile, ImageOps, UnidentifiedImageError

from packages.core.error_codes import (
    DEPENDENCY_UNAVAILABLE,
    FILE_CORRUPT,
    FILE_TYPE_MISMATCH,
    IMAGE_TOO_LARGE,
    VALIDATION,
)
from packages.core.errors import ERRORS
from packages.storage.keys import server_chosen_kind
from packages.storage.port import ObjectStorage
from packages.storage.sniff import ImageKind, sniff

AVATAR_TYPE_UNSUPPORTED = ERRORS.define("AVATAR_TYPE_UNSUPPORTED", 422)
AVATAR_DIMENSIONS_EXCEEDED = ERRORS.define("AVATAR_DIMENSIONS_EXCEEDED", 422)

MAX_BASE64_LEN: Final = 699_052
"""Đúng `contentBase64` của N14 (HOP-DONG-MOI §3): thân JSON 1 MiB mặc định đủ chỗ."""

MAX_DECODED_BYTES: Final = 512 * 1024
MAX_PIXELS: Final = 40_000_000
MAX_DIMENSION: Final = 4096
THUMBNAIL_SIZE: Final = (512, 512)
JPEG_QUALITY: Final = 90
MAX_STORED_BYTES: Final = 2 * 1024 * 1024

_DEFAULT_DECODE_CONCURRENCY: Final = 2
_DECODE_WAIT_S: Final = 2.0
_DECODE_RETRY_AFTER_S: Final = 1
_ENV_CONCURRENCY: Final = "AVATAR_DECODE_CONCURRENCY"

_MIME_KIND: Final[dict[str, ImageKind]] = {"image/png": "png", "image/jpeg": "jpeg"}
_KIND_EXT: Final[dict[ImageKind, str]] = {"png": "png", "jpeg": "jpg"}
_KIND_FORMAT: Final[dict[ImageKind, str]] = {"png": "PNG", "jpeg": "JPEG"}
_DECODE_ERRORS: Final = (UnidentifiedImageError, OSError, SyntaxError, ValueError, struct.error, EOFError)
"""Danh sách lỗi giải mã tường minh (BE-00 §4 cấm bắt `Exception` rộng); U07."""

_EXTRA_SIGNATURES: Final[tuple[tuple[bytes, Literal["gif", "webp", "bmp", "tiff"]], ...]] = (
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
    (b"BM", "bmp"),
    (b"II*\x00", "tiff"),
    (b"MM\x00*", "tiff"),
)


@dataclass(frozen=True, slots=True)
class ProcessedAvatar:
    """Kết quả pipeline N14: dữ liệu đã mã hoá lại, sẵn sàng `storage.put`."""

    data: bytes
    kind: ImageKind
    ext: str
    content_type: str


@cache
def _decode_concurrency() -> int:
    """`AVATAR_DECODE_CONCURRENCY`, đọc lười từ biến môi trường (mặc định 2)."""
    raw = os.environ.get(_ENV_CONCURRENCY)
    if raw is None:
        return _DEFAULT_DECODE_CONCURRENCY
    value = int(raw)
    if value < 1:
        raise ValueError(f"{_ENV_CONCURRENCY} phải ≥ 1, nhận {value}")
    return value


def reset_avatar_settings_cache() -> None:
    """Chỉ cho test: đọc lại `AVATAR_DECODE_CONCURRENCY` ở lần gọi sau."""
    _decode_concurrency.cache_clear()


_slots: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore] = weakref.WeakKeyDictionary()


def _semaphore() -> asyncio.Semaphore:
    """Semaphore của vòng sự kiện đang chạy, dựng lười (BE-00 §7: cấm mức module)."""
    loop = asyncio.get_running_loop()
    slots = _slots.get(loop)
    if slots is None:
        slots = asyncio.Semaphore(_decode_concurrency())
        _slots[loop] = slots
    return slots


@asynccontextmanager
async def _decode_slot() -> AsyncIterator[None]:
    """Giữ một chỗ giải mã; chờ quá `_DECODE_WAIT_S` → 503 (không `wait_for` quanh luồng)."""
    slots = _semaphore()
    try:
        await asyncio.wait_for(slots.acquire(), _DECODE_WAIT_S)
    except TimeoutError as exc:
        raise DEPENDENCY_UNAVAILABLE.error(retry_after=_DECODE_RETRY_AFTER_S) from exc
    try:
        yield
    finally:
        slots.release()


def _decode_base64(value: str) -> bytes:
    """Bước 1: giải base64; hỏng → 422 `field:"contentBase64"`; > 512 KiB → `IMAGE_TOO_LARGE`."""
    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise VALIDATION.error(field="contentBase64") from exc
    if len(raw) > MAX_DECODED_BYTES:
        raise IMAGE_TOO_LARGE.error()
    return raw


def _extra_kind(head: bytes) -> Literal["gif", "webp", "bmp", "tiff"] | None:
    """GIF/WebP/BMP/TIFF — `sniff()` không phân biệt được (đính chính [1].1 của prompt)."""
    for signature, kind in _EXTRA_SIGNATURES:
        if head.startswith(signature):
            return kind
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    return None


def _detect_kind(raw: bytes, mime_type: Literal["image/png", "image/jpeg"]) -> ImageKind:
    """Bước 2: magic bytes; PNG/JPEG lệch `mimeType` → mismatch, GIF/WebP/BMP/TIFF → unsupported."""
    sniffed = sniff(raw)
    if sniffed in ("png", "jpeg"):
        if sniffed != _MIME_KIND[mime_type]:
            raise FILE_TYPE_MISMATCH.error()
        return sniffed
    if sniffed == "unknown" and _extra_kind(raw) is not None:
        raise AVATAR_TYPE_UNSUPPORTED.error()
    raise FILE_TYPE_MISMATCH.error()


def _check_dimensions(raw: bytes, kind: ImageKind) -> None:
    """Bước 3: `w x h` từ đầu tệp, **trước** `load()` (K13, U03)."""
    try:
        with Image.open(io.BytesIO(raw), formats=[_KIND_FORMAT[kind]]) as img:
            width, height = img.size
    except Image.DecompressionBombError as exc:
        raise IMAGE_TOO_LARGE.error() from exc
    except _DECODE_ERRORS as exc:
        raise FILE_CORRUPT.error() from exc
    if width * height > MAX_PIXELS:
        raise IMAGE_TOO_LARGE.error()
    if width > MAX_DIMENSION or height > MAX_DIMENSION:
        raise AVATAR_DIMENSIONS_EXCEEDED.error()


def _has_alpha(img: Image.Image) -> bool:
    """Kênh alpha thật (không chỉ palette có bảng trong suốt rỗng)."""
    return img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)


def _decode_and_reencode(raw: bytes, kind: ImageKind) -> bytes:
    """Bước 4-5: giải mã dưới trần điểm ảnh đã kiểm, xoay theo EXIF, thu nhỏ, mã hoá lại không EXIF."""
    ImageFile.LOAD_TRUNCATED_IMAGES = False
    try:
        with Image.open(io.BytesIO(raw), formats=[_KIND_FORMAT[kind]]) as opened:
            if kind == "jpeg":
                opened.draft("RGB", THUMBNAIL_SIZE)
            opened.load()
            transposed: Image.Image = ImageOps.exif_transpose(opened) or opened
            # Chuyển 8-bit RGB/RGBA **trước** khi thu nhỏ: `Image.thumbnail` dùng đường "reduce"
            # nhanh khi tỉ lệ thu lớn (4096→512), đường đó không hỗ trợ mode thô như "I"/"I;16"
            # (ảnh xám 16-bit) và ném `ValueError` — thu nhỏ sau khi đã convert tránh hẳn lớp lỗi
            # này (U02, "PNG 4096x4096 16-bit"). JPEG không có kênh alpha, `_has_alpha` chỉ thật
            # cho PNG: nhánh JPEG luôn ra "RGB".
            final = transposed.convert("RGBA") if _has_alpha(transposed) else transposed.convert("RGB")
            final.thumbnail(THUMBNAIL_SIZE)
            # `convert`/`thumbnail` chép `self.info` (icc_profile, exif, …) từ ảnh gốc; bộ ghi
            # PNG/JPEG của Pillow rơi về `info` khi `save()` không được truyền gì — xoá hẳn
            # trước khi lưu, không chỉ "không truyền" (NO-166).
            final.info.clear()
            buffer = io.BytesIO()
            if kind == "png":
                final.save(buffer, format="PNG")
            else:
                final.save(buffer, format="JPEG", quality=JPEG_QUALITY)
            return buffer.getvalue()
    except Image.DecompressionBombError as exc:
        raise IMAGE_TOO_LARGE.error() from exc
    except _DECODE_ERRORS as exc:
        raise FILE_CORRUPT.error() from exc


def _process(content_b64: str, mime_type: Literal["image/png", "image/jpeg"]) -> ProcessedAvatar:
    """Thân đồng bộ chạy trong luồng riêng: bước 1-5 trọn vẹn, không đụng vòng sự kiện."""
    raw = _decode_base64(content_b64)
    kind = _detect_kind(raw, mime_type)
    _check_dimensions(raw, kind)
    data = _decode_and_reencode(raw, kind)
    return ProcessedAvatar(data=data, kind=kind, ext=_KIND_EXT[kind], content_type=mime_type)


async def process_avatar(content_b64: str, mime_type: Literal["image/png", "image/jpeg"]) -> ProcessedAvatar:
    """Pipeline N14 trọn vẹn (bước 1-6): dưới semaphore, trên một luồng riêng (K13, K36)."""
    async with _decode_slot():
        return await asyncio.to_thread(_process, content_b64, mime_type)


async def avatar_url(storage: ObjectStorage, avatar_key: str | None) -> str | None:
    """URL `inline` của ảnh đại diện; `None` khi chưa có. Không `stat` (B0-04, K15).

    `kind` suy từ đuôi khoá do server chọn (`keys.server_chosen_kind`) — B1-05 dựng 1.000
    dòng không gọi mạng.
    """
    if avatar_key is None:
        return None
    kind = server_chosen_kind(avatar_key)
    signed = await storage.signed_url(avatar_key, disposition="inline", kind=kind)
    return signed.url
