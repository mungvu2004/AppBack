"""Hạ tầng riêng cho test bản vẽ (B2-04 việc B); phần dùng chung cả module ở `_helpers.py`.

`make_drawing` ở đây là **bản tạm**: nó thuộc `packages/testing/factories/drawings.py`
(việc D sở hữu) và được giao lại qua `drawings.py.fragment`; test của việc B nhập từ đây
để không sửa file của người khác giữa chừng.
"""

import zlib
from collections.abc import Iterator, Sequence

import pytest
from httpx import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.drawings.drawings import new_page_key
from apps.api.drawings.urls import use_signer
from packages.core.clock import SystemClock
from packages.core.ids import new_id
from packages.db.models.drawings import DrawingRow, UploadRow
from packages.db.models.floors import FloorRow
from packages.storage.port import ObjectStorage
from packages.testing.golden import attach_context
from packages.testing.golden.recorder import resolve_operation

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _chunk(kind: bytes, body: bytes) -> bytes:
    """Một khúc PNG: độ dài, loại, thân, CRC32 của (loại + thân)."""
    return len(body).to_bytes(4, "big") + kind + body + zlib.crc32(kind + body).to_bytes(4, "big")


def png_bytes(width: int, height: int) -> bytes:
    """PNG hợp lệ tới mức `sniff` nhận ra và `_png_size` đọc được — không có pixel nào.

    Test bản vẽ chỉ cần kích thước và magic bytes; nén một ảnh thật cho mỗi test là
    thời gian CPU không mua được gì.
    """
    ihdr = width.to_bytes(4, "big") + height.to_bytes(4, "big") + bytes([8, 6, 0, 0, 0])
    return PNG_SIGNATURE + _chunk(b"IHDR", ihdr) + _chunk(b"IEND", b"")


def png_size(png: bytes) -> tuple[int, int]:
    """`(width, height)` đọc từ IHDR; không phải PNG → `ValueError`."""
    if len(png) < 24 or not png.startswith(PNG_SIGNATURE):
        raise ValueError("cần một tệp PNG")
    return int.from_bytes(png[16:20], "big"), int.from_bytes(png[20:24], "big")


async def make_drawing(db: AsyncSession, storage: ObjectStorage, *, upload: UploadRow, png: bytes) -> DrawingRow:
    """Bản vẽ đang dùng của tầng chứa `upload`, kèm object trang đã nắn thật trong kho.

    Ghi thẳng dòng như `make_upload`, **không** qua `upsert_drawing`: factory không có
    lượt chạy đang khoá, mà `upsert_drawing` đòi đúng một lượt như thế.
    """
    width, height = png_size(png)
    row = (
        await db.execute(
            select(FloorRow.level_id, UploadRow.updated_at)
            .join(UploadRow, UploadRow.floor_pk == FloorRow.pk)
            .where(UploadRow.id == upload.id)
        )
    ).one()
    level_id, uploaded_at = row
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


@pytest.fixture(autouse=True)
def test_signer(local_storage: ObjectStorage) -> Iterator[ObjectStorage]:
    """`urls.signer()` trỏ vào kho của test; gỡ lại để không rò sang test sau.

    `autouse` trong module nào **nhập** nó: cổng `floor.drawings` và N7 ký URL qua
    `signer()`, mà kho theo biến môi trường của tiến trình trỏ vào `tmp_path` của một
    test khác.
    """
    use_signer(local_storage)
    yield local_storage
    use_signer(None)


def attach_floor_order(response: Response, floor_ids: Sequence[str]) -> None:
    """H1 ngữ cảnh của N7 (`floorOrder`), chỉ khi đường N7 đã có trong `openapi.json`.

    `openapi.json` đã commit chưa có N7 chừng nào `router.py` (việc U) và lượt làm mới hợp
    đồng của người điều phối chưa xong; lúc đó bộ ghi golden không ghi mẫu nào và
    `attach_context` ném `ValueError`. Kiểm bằng chính hàm bộ ghi dùng, nên đến khi hợp
    đồng có N7 thì ngữ cảnh được gắn thật, không cần sửa test.
    """
    if resolve_operation(response.request.method, response.request.url.path) is None:
        return
    attach_context(response, floorOrder=list(floor_ids))
