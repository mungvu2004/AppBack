"""Hai bước đầu của lượt tải: #5 mở lượt, #6 nhận một khúc (B2-04 [6]).

Ba luật giữ file này đứng vững:

- **Tin magic bytes, không tin đuôi tệp** (K14): ở #5 đuôi và `mimeType` chỉ dùng để từ
  chối sớm những thứ chắc chắn sai; lời phán cuối là `sniff_kind` ở #7 (`complete.py`).
- **Không giữ kết nối DB khi chờ việc chậm** (K36): #6 `await db.rollback()` **trước** khi
  giải mã base64, băm SHA-256 và ghi kho; giao dịch thứ hai chỉ mở lại để ghi một dòng.
- **Khử trùng thử lại chứ không chèn hai lần** ([6] #5 bước 5): FE thử lại mỗi lượt tới ba
  lần **không** `Idempotency-Key`, nên hai lượt init giống hệt nhau trong
  `UPLOAD_INIT_DEDUPE_S` phải ra cùng một `upload_id`.
"""

import asyncio
import base64
import hashlib
from dataclasses import dataclass
from datetime import timedelta
from typing import Final

from sqlalchemy import exists, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.access.activity import record_activity
from apps.api.access.kinds import ActivityKind
from apps.api.core.auth import Principal
from apps.api.drawings.errors import UPLOAD_NOT_RECEIVING
from apps.api.drawings.progress import progress_wire
from apps.api.drawings.schemas import InitUploadBody, UploadChunkBody
from apps.api.drawings.settings import get_drawings_settings
from apps.api.floors.lookup import get_floor
from packages.core.clock import Clock
from packages.core.error_codes import (
    CAD_NOT_SUPPORTED,
    FILE_TYPE_MISMATCH,
    NOT_FOUND,
    PAYLOAD_TOO_LARGE,
    VALIDATION,
)
from packages.core.ids import new_id
from packages.db.models.drawings import UploadChunkRow, UploadRow
from packages.db.models.floors import FloorRow
from packages.storage.keys import check_key, upload_original, upload_prefix
from packages.storage.port import ObjectStorage

OCTET_STREAM: Final = "application/octet-stream"
"""`Content-Type` của một khúc: khúc không phải tệp, không ai tải nó về trực tiếp."""

KIND_MIME: Final = {"png": "image/png", "jpeg": "image/jpeg", "pdf": "application/pdf"}
"""MIME chuẩn của ba loại tệp nhận được — dùng cho `Content-Type` của `original.*`."""

EXT_KIND: Final = {"png": "png", "jpg": "jpeg", "jpeg": "jpeg", "pdf": "pdf"}
"""Đuôi tệp → loại nội dung; `sniff_kind` của #7 trả đúng các giá trị bên phải."""

_BLANK_MIMES: Final = frozenset({"", OCTET_STREAM})
"""`File.type` rỗng của trình duyệt (U09): nhận, để magic bytes quyết ở #7."""

_CAD_EXT: Final = "dwg"


@dataclass(frozen=True, slots=True)
class UploadFacts:
    """Ảnh chụp một lượt tải + tầng của nó, đọc **một** truy vấn trước khi `rollback`.

    #6 và #7 thả kết nối DB giữa chừng (K36), nên chúng không được giữ đối tượng ORM: sau
    `rollback` mọi thuộc tính của nó hết hạn và lượt nạp lại lười là IO đồng bộ trong hàm
    async (`MissingGreenlet`). Dataclass đông cứng là bản chụp an toàn cho cả hai chặng.
    """

    id: str
    project_id: str
    floor_pk: int
    level_id: str
    file_name: str
    declared_size_bytes: int
    page_index: int
    chunk_count: int
    status: str

    @property
    def expected_kind(self) -> str:
        """Loại tệp mà đuôi hứa hẹn; `#7` so nó với `sniff_kind` (U08)."""
        return EXT_KIND.get(file_extension(self.file_name), "unknown")

    @property
    def original_key(self) -> str:
        """Khoá `original.<đuôi>` của lượt tải (`keys.upload_original`, B2-04 [5])."""
        return upload_original(self.project_id, self.level_id, self.id, file_extension(self.file_name))


def chunk_key(project_id: str, level_id: str, upload_id: str, index: int, sha256: str) -> str:
    """Khoá object của một khúc: `<upload_prefix>chunks/{i}/{sha256}` (B2-04 [5]).

    Băm nằm **trong** khoá nên gửi lại đúng khúc ấy là ghi đè chính nó, còn gửi lại một
    nội dung khác là một object mới: `#7` so danh sách khoá trước và sau khi nối tệp để
    bắt đúng trường hợp thứ hai (409 `UPLOAD_CHUNKS_CHANGED`).
    """
    return check_key(f"{upload_prefix(project_id, level_id, upload_id)}chunks/{index}/{sha256}")


def file_extension(file_name: str) -> str:
    """Đuôi thường của tên tệp, chuỗi rỗng khi không có dấu chấm nào."""
    return file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""


def declared_kind(file_name: str, mime_type: str) -> str:
    """Loại tệp theo đuôi, có đối chiếu `mimeType` client khai ([6] #5 bước 2-3).

    `.dwg` hoặc `mimeType` nhắc `dwg` → `CAD_NOT_SUPPORTED` (U12); đuôi ngoài bốn đuôi
    nhận được, hoặc MIME khai lệch đuôi → `FILE_TYPE_MISMATCH` (U08). MIME rỗng và
    `application/octet-stream` được nhận (U09): trình duyệt hay để trống, magic bytes ở #7
    mới là lời phán cuối (K14).
    """
    ext = file_extension(file_name)
    mime = mime_type.strip().lower()
    if ext == _CAD_EXT or _CAD_EXT in mime:
        raise CAD_NOT_SUPPORTED.error()
    kind = EXT_KIND.get(ext)
    if kind is None:
        raise FILE_TYPE_MISMATCH.error()
    if mime not in _BLANK_MIMES and mime != KIND_MIME[kind]:
        raise FILE_TYPE_MISMATCH.error()
    return kind


async def load_upload(db: AsyncSession, *, project_id: str, upload_id: str) -> UploadFacts:
    """Lượt tải của **đúng** dự án trên đường và tầng chưa xoá ([6] #6 bước 1).

    Lượt tải của dự án khác, hay của một tầng đã xoá mềm, trả 404 `resource:"upload"` chứ
    không 403: người gọi không được biết id ấy có thật hay không ([7]).
    """
    stmt = (
        select(
            UploadRow.id,
            UploadRow.project_id,
            UploadRow.floor_pk,
            FloorRow.level_id,
            UploadRow.file_name,
            UploadRow.declared_size_bytes,
            UploadRow.page_index,
            UploadRow.chunk_count,
            UploadRow.status,
        )
        .join(FloorRow, FloorRow.pk == UploadRow.floor_pk)
        .where(UploadRow.id == upload_id, UploadRow.project_id == project_id, FloorRow.deleted_at.is_(None))
    )
    row = (await db.execute(stmt)).first()
    if row is None:
        raise NOT_FOUND.error(resource="upload")
    return UploadFacts(*row)


async def _twin_upload(db: AsyncSession, *, floor_pk: int, created_by: str, body: InitUploadBody) -> str | None:
    """Lượt init trước đó **giống hệt** và còn trong cửa sổ khử trùng ([6] #5 bước 5).

    "Giống hệt" = cùng tầng, người tạo, tên tệp, kích thước, MIME khai và `pageIndex`, còn
    `receiving` và **chưa nhận khúc nào**: đã có khúc nghĩa là lượt cũ đang chạy thật, lượt
    mới là một tệp khác của cùng người. So thời gian bằng `now()` của Postgres vì
    `created_at` cũng do Postgres đặt — trộn hai đồng hồ là một cửa sổ sai.
    """
    window = timedelta(seconds=get_drawings_settings().upload_init_dedupe_s)
    no_chunks = ~exists().where(UploadChunkRow.upload_id == UploadRow.id)
    stmt = (
        select(UploadRow.id)
        .where(
            UploadRow.floor_pk == floor_pk,
            UploadRow.created_by == created_by,
            UploadRow.file_name == body.file_name,
            UploadRow.declared_size_bytes == body.size_bytes,
            UploadRow.declared_type == body.mime_type,
            UploadRow.page_index == body.page_index,
            UploadRow.status == "receiving",
            UploadRow.created_at >= func.now() - window,
            no_chunks,
        )
        .order_by(UploadRow.created_at.desc(), UploadRow.id.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def init_upload(
    db: AsyncSession,
    *,
    project_id: str,
    level_id: str,
    body: InitUploadBody,
    principal: Principal,
    clock: Clock,
) -> dict[str, object]:
    """#5 — mở một lượt tải cho một tầng và trả `Progress` `pending` của nó.

    Tầng bị khoá ngay từ đầu (`for_update`) để hai lượt init song song của cùng người xếp
    hàng và lượt thứ hai thấy được lượt thứ nhất trong câu khử trùng. Lỗi: 404 tầng,
    `CAD_NOT_SUPPORTED`/`FILE_TYPE_MISMATCH` (đuôi, MIME), 413 (quá trần), 422
    `field:"pageIndex"` (trang khác 0 cho ảnh).
    """
    floor = await get_floor(db, project_id=project_id, level_id=level_id, for_update=True)
    if floor is None:
        raise NOT_FOUND.error(resource="floor")
    kind = declared_kind(body.file_name, body.mime_type)
    settings = get_drawings_settings()
    if body.size_bytes > settings.upload_max_bytes:
        raise PAYLOAD_TOO_LARGE.error()
    if body.page_index != 0 and kind != "pdf":
        raise VALIDATION.error(field="pageIndex")

    twin = await _twin_upload(db, floor_pk=floor.pk, created_by=principal.user_id, body=body)
    if twin is not None:
        return await progress_wire(db, twin)

    upload = UploadRow(
        id=new_id("upl", clock),
        project_id=project_id,
        floor_pk=floor.pk,
        file_name=body.file_name,
        declared_size_bytes=body.size_bytes,
        declared_type=body.mime_type,
        page_index=body.page_index,
        chunk_count=-(-body.size_bytes // settings.upload_chunk_bytes),
        status="receiving",
        created_by=principal.user_id,
    )
    db.add(upload)
    await db.flush()
    await record_activity(
        db,
        actor_id=principal.user_id,
        kind=ActivityKind.FLOOR_UPLOAD,
        object_code=floor.level_id,
        object_label=floor.name,
        clock=clock,
        project_id=project_id,
    )
    return await progress_wire(db, upload.id)


def _decode_chunk(raw: str, *, index: int, chunk_count: int, chunk_bytes: int) -> bytes:
    """Base64 của một khúc → byte, kèm mọi luật độ dài ([6] #6 bước 2).

    Khúc **không phải khúc cuối** phải đủ `UPLOAD_CHUNK_BYTES`: thiếu byte ở giữa tệp là
    một lượt cắt ghép, và `#7` nối theo thứ tự chỉ số nên nó sẽ ra một tệp lệch mà tổng
    kích thước vẫn có thể khớp. Mọi vi phạm → 422 `field:"chunk"`.
    """
    try:
        data = base64.b64decode(raw, validate=True)
    except ValueError as exc:
        raise VALIDATION.error(field="chunk") from exc
    if not data or len(data) > chunk_bytes:
        raise VALIDATION.error(field="chunk")
    if index < chunk_count - 1 and len(data) != chunk_bytes:
        raise VALIDATION.error(field="chunk")
    return data


async def _save_chunk(db: AsyncSession, *, upload_id: str, index: int, size: int, sha256: str, key: str) -> None:
    """Giao dịch ngắn của #6: khoá lượt tải, còn `receiving` thì upsert dòng khúc.

    Upsert chứ không insert: gửi lại một khúc là chuyện thường của FE (U10), và khoá
    object đã đổi theo băm nên dòng cũ phải trỏ sang object mới. Lượt tải biến mất giữa
    chừng → 404; đã `complete`/`rejected` → 422 `UPLOAD_NOT_RECEIVING`.
    """
    status = (
        await db.execute(select(UploadRow.status).where(UploadRow.id == upload_id).with_for_update())
    ).scalar_one_or_none()
    if status is None:
        raise NOT_FOUND.error(resource="upload")
    if status != "receiving":
        raise UPLOAD_NOT_RECEIVING.error()
    stmt = pg_insert(UploadChunkRow).values(
        upload_id=upload_id, chunk_index=index, size_bytes=size, sha256=sha256, object_key=key
    )
    await db.execute(
        stmt.on_conflict_do_update(
            index_elements=[UploadChunkRow.upload_id, UploadChunkRow.chunk_index],
            set_={"size_bytes": size, "sha256": sha256, "object_key": key, "updated_at": func.now()},
        )
    )


async def upload_chunk(
    db: AsyncSession, storage: ObjectStorage, *, project_id: str, upload_id: str, body: UploadChunkBody
) -> dict[str, object]:
    """#6 — nhận một khúc: kiểm dưới giao dịch, ghi kho **ngoài** giao dịch, rồi ghi dòng.

    `await db.rollback()` ở giữa là bắt buộc (K36): giải mã base64, băm SHA-256 và một
    lượt PUT lên MinIO có thể mất nhiều giây, và `DB_POOL_SIZE` nhỏ hơn số khúc song song
    của một dự án. Lỗi: 404, `UPLOAD_NOT_RECEIVING`, 422 `field:"chunkIndex"`/`"chunk"`.
    """
    facts = await load_upload(db, project_id=project_id, upload_id=upload_id)
    if facts.status != "receiving":
        raise UPLOAD_NOT_RECEIVING.error()
    if body.chunk_index >= facts.chunk_count:
        raise VALIDATION.error(field="chunkIndex")
    chunk_bytes = get_drawings_settings().upload_chunk_bytes

    await db.rollback()
    data = _decode_chunk(body.chunk, index=body.chunk_index, chunk_count=facts.chunk_count, chunk_bytes=chunk_bytes)
    sha256 = await asyncio.to_thread(_digest, data)
    key = chunk_key(facts.project_id, facts.level_id, facts.id, body.chunk_index, sha256)
    await storage.put(key, data, content_type=OCTET_STREAM, max_bytes=chunk_bytes)

    await _save_chunk(db, upload_id=facts.id, index=body.chunk_index, size=len(data), sha256=sha256, key=key)
    return await progress_wire(db, facts.id)


def _digest(data: bytes) -> str:
    """SHA-256 hex của một khúc; hàm rời để `asyncio.to_thread` gọi được (K36)."""
    return hashlib.sha256(data).hexdigest()
