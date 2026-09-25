"""Factory lượt tải bản vẽ cho test (B2-04), theo mẫu `packages/testing/factories/floors.py`.

Ghi thẳng `uploads`/`upload_chunks` và kho object, không qua API: test của `progress`, `runs`
và của ba lịch nền cần một lượt tải ở đúng trạng thái, không cần bốn lượt HTTP để tới đó.
Chỉ `flush` như `make_floor` — test còn ghi tiếp trong cùng giao dịch.

`make_drawing` ghi thẳng dòng `drawings` chứ không qua `upsert_drawing`: hàm ấy đòi một lượt
chạy đang khoá, thứ mà test mồi dữ liệu không có.
"""

import hashlib
import zlib
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.drawings.drawings import new_page_key
from apps.api.drawings.settings import get_drawings_settings
from apps.api.drawings.uploads import chunk_key as chunk_key
from packages.core.clock import SystemClock
from packages.core.ids import new_id
from packages.core.text import nfc
from packages.db.models.drawings import DrawingRow, UploadChunkRow, UploadRow
from packages.db.models.floors import FloorRow
from packages.db.models.projects import Project
from packages.storage.keys import upload_original
from packages.storage.port import ObjectStorage

DEFAULT_FILE_NAME: Final = "ban-ve.png"
DEFAULT_SIZE_BYTES: Final = 1024

_EXT_TYPE: Final = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "pdf": "application/pdf"}
_EXT_KIND: Final = {"png": "png", "jpg": "jpeg", "jpeg": "jpeg", "pdf": "pdf"}

PNG_SIGNATURE: Final = b"\x89PNG\r\n\x1a\n"

"""`chunk_key` xuất lại từ `apps.api.drawings.uploads`: một luật khoá khúc, một chủ (đính chính §15)."""


def _extension(file_name: str) -> str:
    """Đuôi thường của tên tệp; không có đuôi biết → `png` (tên mặc định của factory)."""
    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else "png"
    return ext if ext in _EXT_TYPE else "png"


async def make_upload(
    db: AsyncSession,
    *,
    project: Project,
    floor: FloorRow,
    status: str = "receiving",
    file_name: str = DEFAULT_FILE_NAME,
    size_bytes: int = DEFAULT_SIZE_BYTES,
    page_index: int = 0,
    rejected_code: str | None = None,
) -> UploadRow:
    """Một dòng `uploads` đã `flush`, **không** khúc và **không** object nào trong kho.

    `chunk_count` suy từ `size_bytes` đúng luật #5 (`ceil(size / UPLOAD_CHUNK_BYTES)`), nên
    test của #6/#7 đếm khúc thiếu ra cùng số với route thật.
    """
    chunk_bytes = get_drawings_settings().upload_chunk_bytes
    upload = UploadRow(
        id=new_id("upl", SystemClock()),
        project_id=project.id,
        floor_pk=floor.pk,
        file_name=nfc(file_name),
        declared_size_bytes=size_bytes,
        declared_type=_EXT_TYPE[_extension(file_name)],
        page_index=page_index,
        chunk_count=-(-size_bytes // chunk_bytes),
        status=status,
        rejected_code=rejected_code,
        created_by=project.created_by,
    )
    db.add(upload)
    await db.flush()
    return upload


async def make_complete_upload(
    db: AsyncSession,
    storage: ObjectStorage,
    *,
    project: Project,
    floor: FloorRow,
    data: bytes,
    file_name: str = DEFAULT_FILE_NAME,
    page_index: int = 0,
) -> UploadRow:
    """Lượt tải đã `complete`: khúc thật trong kho, dòng `upload_chunks`, `original.<đuôi>` thật.

    Dùng cho test cần một lượt tải **có** tệp gốc đọc được (lịch dọn, `start_run`, N7);
    `data` rỗng → `ValueError` vì `declared_size_bytes > 0` là CHECK của bảng.
    """
    if not data:
        raise ValueError("make_complete_upload cần ít nhất một byte")
    ext = _extension(file_name)
    upload = await make_upload(
        db, project=project, floor=floor, file_name=file_name, size_bytes=len(data), page_index=page_index
    )
    chunk_bytes = get_drawings_settings().upload_chunk_bytes
    for index in range(upload.chunk_count):
        piece = data[index * chunk_bytes : (index + 1) * chunk_bytes]
        digest = hashlib.sha256(piece).hexdigest()
        key = chunk_key(project.id, floor.level_id, upload.id, index, digest)
        await storage.put(key, piece, content_type="application/octet-stream", max_bytes=chunk_bytes)
        db.add(
            UploadChunkRow(upload_id=upload.id, chunk_index=index, size_bytes=len(piece), sha256=digest, object_key=key)
        )
    original_key = upload_original(project.id, floor.level_id, upload.id, ext)
    await storage.put(original_key, data, content_type=_EXT_TYPE[ext], max_bytes=len(data))
    upload.status = "complete"
    upload.sniffed_kind = _EXT_KIND[ext]
    upload.original_key = original_key
    await db.flush()
    return upload


def _png_chunk(kind: bytes, body: bytes) -> bytes:
    """Một khúc PNG: độ dài, loại, thân, CRC32 của (loại + thân)."""
    return len(body).to_bytes(4, "big") + kind + body + zlib.crc32(kind + body).to_bytes(4, "big")


def png_bytes(width: int, height: int) -> bytes:
    """PNG hợp lệ tới mức `sniff` nhận ra và `png_size` đọc được — không có pixel nào.

    Test bản vẽ chỉ cần kích thước và magic bytes; nén một ảnh thật cho mỗi test là thời
    gian CPU không mua được gì.
    """
    ihdr = width.to_bytes(4, "big") + height.to_bytes(4, "big") + bytes([8, 6, 0, 0, 0])
    return PNG_SIGNATURE + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IEND", b"")


def png_size(png: bytes) -> tuple[int, int]:
    """`(width, height)` đọc từ IHDR; không phải PNG → `ValueError`."""
    if len(png) < 24 or not png.startswith(PNG_SIGNATURE):
        raise ValueError("cần một tệp PNG")
    return int.from_bytes(png[16:20], "big"), int.from_bytes(png[20:24], "big")


async def make_drawing(db: AsyncSession, storage: ObjectStorage, *, upload: UploadRow, png: bytes) -> DrawingRow:
    """Bản vẽ đang dùng của tầng chứa `upload`, kèm object trang đã nắn thật trong kho.

    Ghi thẳng dòng như `make_upload`, **không** qua `upsert_drawing`: factory không có lượt
    chạy đang khoá, mà `upsert_drawing` đòi đúng một lượt như thế.
    """
    width, height = png_size(png)
    level_id, uploaded_at = (
        await db.execute(
            select(FloorRow.level_id, UploadRow.updated_at)
            .join(UploadRow, UploadRow.floor_pk == FloorRow.pk)
            .where(UploadRow.id == upload.id)
        )
    ).one()
    key = new_page_key(
        project_id=upload.project_id,
        level_id=level_id,
        upload_id=upload.id,
        page_index=upload.page_index,
        clock=SystemClock(),
    )
    await storage.put(key, png, content_type="image/png", max_bytes=len(png))
    drawing = DrawingRow(
        id=new_id("drw", SystemClock()),
        floor_pk=upload.floor_pk,
        upload_id=upload.id,
        name=upload.file_name,
        page_key=key,
        width_px=width,
        height_px=height,
        uploaded_at=uploaded_at,
        uploader_id=upload.created_by,
    )
    db.add(drawing)
    await db.flush()
    return drawing
