"""Hạ tầng dùng chung cho test route #5-#8 và luồng S1 (việc U của B2-04).

Không phải file test (không hàm `test_*`): chỉ dựng đường, thân, byte mẫu và một "sân
khấu" đã commit. Tệp mẫu sinh trong bộ nhớ, không commit nhị phân và không tải mạng —
PDF mượn `packages.vision.preprocess.tests.synthetic.make_pdf` (nơi duy nhất trong repo
biết viết PDF hợp lệ, R-07) thay vì có bản sao thứ hai ở đây.
"""

import asyncio
import base64
import secrets
import struct
import zlib
from collections.abc import AsyncIterable, AsyncIterator, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.drawings.settings import get_drawings_settings
from apps.api.drawings.tests._helpers import Scene, make_scene
from apps.api.projects.tests.test_routes_common import headers_of as headers_of
from packages.storage.port import CHUNK_SIZE, Disposition, ObjectInfo, ObjectStorage, SignedUrl
from packages.storage.sniff import ImageKind
from packages.vision.preprocess.tests.synthetic import Encryption, make_pdf

PNG_SIGNATURE: Final = b"\x89PNG\r\n\x1a\n"
JPEG_SOI: Final = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
JPEG_EOI: Final = b"\xff\xd9"
SMALL_CHUNK_BYTES: Final = 1024
"""`UPLOAD_CHUNK_BYTES` của phần lớn test: 5 MiB thật chỉ cần cho test luồng đầy đủ."""


def init_path(project_id: str, level_id: str) -> str:
    """Đường #5."""
    return f"/api/projects/{project_id}/floors/{level_id}/drawings/uploads"


def chunks_path(project_id: str, upload_id: str) -> str:
    """Đường #6."""
    return f"/api/projects/{project_id}/drawings/uploads/{upload_id}/chunks"


def complete_path(project_id: str, upload_id: str) -> str:
    """Đường #7."""
    return f"/api/projects/{project_id}/drawings/uploads/{upload_id}/complete"


def progress_path(project_id: str, upload_id: str) -> str:
    """Đường #8."""
    return f"/api/projects/{project_id}/drawings/uploads/{upload_id}/progress"


def stream_path(project_id: str, upload_id: str) -> str:
    """Đường luồng S1 (`apps/api/streams/router.py`)."""
    return f"/api/streams/projects/{project_id}/uploads/{upload_id}/progress"


def init_body(
    project_id: str, level_id: str, *, size_bytes: int, file_name: str = "ban-ve.png", **overrides: Any
) -> dict[str, Any]:
    """Thân #5 đầy đủ; `overrides` đổi bất kỳ khoá nào (kể cả thêm khoá lạ cho C03)."""
    body: dict[str, Any] = {
        "fileName": file_name,
        "floorId": level_id,
        "mimeType": "image/png",
        "projectId": project_id,
        "sizeBytes": size_bytes,
    }
    body.update(overrides)
    return body


def chunk_body(data: bytes, index: int) -> dict[str, Any]:
    """Thân #6 cho một khúc byte."""
    return {"chunk": base64.b64encode(data).decode("ascii"), "chunkIndex": index}


def split(data: bytes, chunk_bytes: int | None = None) -> list[bytes]:
    """Cắt tệp thành khúc đúng luật #5 (`ceil(size / UPLOAD_CHUNK_BYTES)`)."""
    size = chunk_bytes if chunk_bytes is not None else get_drawings_settings().upload_chunk_bytes
    return [data[start : start + size] for start in range(0, len(data), size)]


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    """Một chunk PNG hoàn chỉnh (độ dài, tên, dữ liệu, CRC32)."""
    return len(payload).to_bytes(4, "big") + kind + payload + zlib.crc32(kind + payload).to_bytes(4, "big")


def png_bytes(size: int = 0, *, truncated: bool = False) -> bytes:
    """PNG hợp lệ tối giản, đệm tới `size` byte; `truncated=True` bỏ hẳn `IEND` (U07).

    Đệm nằm **sau** `IEND` nên tệp vẫn là PNG đọc được và `sniff_kind` vẫn trả `png`; test
    luồng đầy đủ chỉ cần một tệp đủ lớn để chia ba khúc, không cần ảnh thật.
    """
    ihdr = struct.pack(">IIBBBBB", 8, 8, 8, 2, 0, 0, 0)
    body = PNG_SIGNATURE + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", zlib.compress(b"\x00" * 8))
    data = body if truncated else body + _png_chunk(b"IEND", b"")
    return data + b"\x00" * max(0, size - len(data))


def jpeg_bytes(size: int = 0, *, truncated: bool = False, trailing: int = 0) -> bytes:
    """JPEG tối giản; `trailing` byte rác **sau** `FF D9` vẫn phải được nhận ([8])."""
    data = JPEG_SOI + b"\x00" * 32
    if not truncated:
        data += JPEG_EOI + b"\x00" * trailing
    return data + b"\x00" * max(0, size - len(data))


def pdf_bytes(pages: int = 1, *, leading_garbage: int = 0, encrypt: Encryption = "none") -> bytes:
    """PDF `pages` trang; `leading_garbage` byte rác trước `%PDF-` vẫn phải nhận ([8])."""
    return b"\x7f" * leading_garbage + make_pdf(pages, encrypt=encrypt)


def broken_pdf_bytes() -> bytes:
    """`%PDF-` rồi rác, có `%%EOF` ở cuối: qua được U07 nhưng PDFium không mở nổi (NO-124).

    Cùng mẫu với `packages/vision/preprocess/tests/test_pdf.py` (`FILE_CORRUPT` mang
    `__cause__` là `PdfiumError`), chỉ thêm dấu kết thúc để #7 đi tới được bước đếm trang.
    """
    return b"%PDF-1.4\n" + b"\x01\x02\x03garbage" * 40 + b"%%EOF"


@dataclass(frozen=True, slots=True)
class Stage:
    """Sân khấu đã **commit**: route chạy trên session khác nên dữ liệu phải bền (K22)."""

    scene: Scene
    headers: dict[str, str]

    @property
    def project_id(self) -> str:
        """Id dự án của sân khấu."""
        return self.scene.project.id

    @property
    def level_id(self) -> str:
        """`level_id` của tầng."""
        return self.scene.floor.level_id


async def make_stage(db: AsyncSession, *, level_id: str | None = None) -> Stage:
    """Người dùng + dự án + tầng đã commit, kèm header của chủ dự án."""
    scene = await make_scene(db, level_id=level_id)
    await db.commit()
    return Stage(scene=scene, headers=headers_of(scene.user))


async def send_chunks(
    client: httpx.AsyncClient, stage: Stage, upload_id: str, pieces: Sequence[bytes]
) -> list[httpx.Response]:
    """Gửi #6 cho từng khúc theo thứ tự; trả mọi response để test tự khẳng định."""
    path = chunks_path(stage.project_id, upload_id)
    return [await client.post(path, json=chunk_body(piece, i), headers=stage.headers) for i, piece in enumerate(pieces)]


async def upload_through(
    client: httpx.AsyncClient,
    stage: Stage,
    data: bytes,
    *,
    file_name: str = "ban-ve.png",
    mime_type: str = "image/png",
    page_index: int | None = None,
    chunk_bytes: int | None = None,
) -> tuple[str, httpx.Response]:
    """#5 → #6 (mọi khúc) → #7; trả `(upload_id, response của #7)`.

    Dừng lại và ném `AssertionError` ngay khi một bước không 200: test nào muốn xem lỗi
    của #5 hay #6 thì gọi thẳng từng route, hàm này chỉ cho đường đi suôn sẻ tới #7.
    """
    extra: dict[str, Any] = {} if page_index is None else {"pageIndex": page_index}
    body = init_body(
        stage.project_id, stage.level_id, size_bytes=len(data), file_name=file_name, mimeType=mime_type, **extra
    )
    init = await client.post(init_path(stage.project_id, stage.level_id), json=body, headers=stage.headers)
    assert init.status_code == 200, init.text
    upload_id = str(init.json()["id"])
    for response in await send_chunks(client, stage, upload_id, split(data, chunk_bytes)):
        assert response.status_code == 200, response.text
    complete = await client.post(
        complete_path(stage.project_id, upload_id), json={"uploadId": upload_id}, headers=stage.headers
    )
    return upload_id, complete


def random_level_id() -> str:
    """`level_id` hợp mẫu `^L-[0-9A-Z]{10,64}$` cho test cần tầng thứ hai."""
    return f"L-{secrets.token_hex(6).upper()}"


class GatedStorage:
    """Kho thật, nhưng `put` dừng lại cho tới khi test mở cổng — để dựng cảnh "ghi kho chậm".

    Không phải mock kho: mọi phương thức khác đi thẳng xuống kho thật và `put` cũng ghi
    thật, chỉ thêm một chỗ chờ để test quan sát đúng lúc request đang bận ngoài giao dịch
    (K36, và các nhánh "dữ liệu đổi giữa chừng" của #7). `only` lọc theo khoá: `"original"`
    chặn lượt ghi tệp gốc của #7 mà vẫn cho #6 ghi khúc bình thường.
    """

    def __init__(self, inner: ObjectStorage, *, only: str = "") -> None:
        """Bọc một kho thật; `entered` báo đã vào `put`, `release` cho `put` chạy tiếp."""
        self._inner = inner
        self._only = only
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def put(
        self, key: str, data: bytes | AsyncIterable[bytes], *, content_type: str, max_bytes: int
    ) -> ObjectInfo:
        """Khoá khớp `only` thì báo đã vào và chờ test mở cổng; rồi ghi thật."""
        if self._only in key:
            self.entered.set()
            await self.release.wait()
        return await self._inner.put(key, data, content_type=content_type, max_bytes=max_bytes)

    async def stat(self, key: str) -> ObjectInfo | None:
        """Chuyển tiếp."""
        return await self._inner.stat(key)

    def open_read(self, key: str, *, chunk_size: int = CHUNK_SIZE) -> AsyncIterator[bytes]:
        """Chuyển tiếp."""
        return self._inner.open_read(key, chunk_size=chunk_size)

    async def delete(self, key: str) -> None:
        """Chuyển tiếp."""
        await self._inner.delete(key)

    async def delete_prefix(self, prefix: str) -> None:
        """Chuyển tiếp."""
        await self._inner.delete_prefix(prefix)

    def list_prefix(self, prefix: str, *, older_than: datetime | None = None) -> AsyncIterator[ObjectInfo]:
        """Chuyển tiếp."""
        return self._inner.list_prefix(prefix, older_than=older_than)

    async def signed_url(
        self, key: str, *, disposition: Disposition, filename: str | None = None, kind: ImageKind | None = None
    ) -> SignedUrl:
        """Chuyển tiếp."""
        return await self._inner.signed_url(key, disposition=disposition, filename=filename, kind=kind)
