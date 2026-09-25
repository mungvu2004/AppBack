"""Factory lượt tải bản vẽ cho test (B2-04), theo mẫu `packages/testing/factories/floors.py`.

Ghi thẳng `uploads`/`upload_chunks` và kho object, không qua API: test của `progress`, `runs`
và của ba lịch nền cần một lượt tải ở đúng trạng thái, không cần bốn lượt HTTP để tới đó.
Chỉ `flush` như `make_floor` — test còn ghi tiếp trong cùng giao dịch.

**Không** có `make_drawing` ở đây: khoá trang đã nắn do `drawings.new_page_key` (việc B của
B2-04) sinh, factory sẽ thêm khi hàm ấy tồn tại.
"""

import hashlib
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.drawings.settings import get_drawings_settings
from packages.core.clock import SystemClock
from packages.core.ids import new_id
from packages.core.text import nfc
from packages.db.models.drawings import UploadChunkRow, UploadRow
from packages.db.models.floors import FloorRow
from packages.db.models.projects import Project
from packages.storage.keys import check_key, upload_original, upload_prefix
from packages.storage.port import ObjectStorage

DEFAULT_FILE_NAME: Final = "ban-ve.png"
DEFAULT_SIZE_BYTES: Final = 1024

_EXT_TYPE: Final = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "pdf": "application/pdf"}
_EXT_KIND: Final = {"png": "png", "jpg": "jpeg", "jpeg": "jpeg", "pdf": "pdf"}


def chunk_key(project_id: str, level_id: str, upload_id: str, index: int, sha256: str) -> str:
    """Khoá object của một khúc: `<upload_prefix>chunks/{i}/{sha256}` (B2-04 [5]).

    Bản sao tạm của luật khoá khúc: `packages/storage/keys.py` là chủ của bố cục khoá nhưng
    nằm ngoài whitelist B2-04 (nợ đã nêu trong báo cáo việc D — đường nâng cấp là thêm
    `upload_chunk()` vào `packages/storage/keys.py` rồi cả factory lẫn route #6 gọi nó).
    """
    return check_key(f"{upload_prefix(project_id, level_id, upload_id)}chunks/{index}/{sha256}")


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
