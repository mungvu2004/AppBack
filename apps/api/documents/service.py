"""Nghiệp vụ tài liệu chưa gán tầng: N39 init và `mark_uploaded` cho nhánh tài liệu của #7 (PHASE-1-CONTRACT §3.2).

Upload tài liệu là một dòng `uploads` có `document_pk`, không `floor_pk`: #6/#7 dùng lại nguyên vẹn,
nhưng nó không bao giờ vào `start_run`/N7/N7b. Tác dụng ngoài (xếp `documents.analyze`) đi sau commit (K17).
"""

from typing import Final

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.auth import Principal
from apps.api.documents.schemas import DocumentInitBody
from apps.api.drawings.settings import get_drawings_settings
from apps.api.drawings.uploads import declared_kind
from packages.core.clock import Clock
from packages.core.error_codes import PAYLOAD_TOO_LARGE
from packages.core.ids import new_id
from packages.db.hooks import on_after_commit
from packages.db.models.documents import DocumentPageRow, DocumentRow
from packages.db.models.drawings import UploadRow
from packages.messaging.celery_app import send_task

ANALYZE_TASK: Final = "documents.analyze"
"""Task của W2 (`apps/worker/documents`), gửi bằng tên, không nhập `apps.worker`."""


class DocumentAnalyzePayload(BaseModel):
    """Payload `documents.analyze` (PHASE-1-CONTRACT §3.5)."""

    model_config = ConfigDict(extra="forbid")

    document_id: str


async def init_document_upload(
    db: AsyncSession, *, project_id: str, body: DocumentInitBody, principal: Principal, clock: Clock
) -> dict[str, object]:
    """N39 — một `documents` `uploading` và một `uploads` `receiving` của nó trong cùng giao dịch.

    Luật đuôi/MIME và trần kích thước như #5 (`declared_kind`, `UPLOAD_MAX_BYTES`); không tầng nên
    không khoá tầng. `chunk_count` theo đúng công thức #5.
    """
    declared_kind(body.file_name, body.mime_type)
    settings = get_drawings_settings()
    if body.size_bytes > settings.upload_max_bytes:
        raise PAYLOAD_TOO_LARGE.error()
    document = DocumentRow(
        id=new_id("doc", clock), project_id=project_id, file_name=body.file_name, created_by=principal.user_id
    )
    db.add(document)
    await db.flush()
    chunk_count = -(-body.size_bytes // settings.upload_chunk_bytes)
    upload = UploadRow(
        id=new_id("upl", clock),
        project_id=project_id,
        floor_pk=None,
        document_pk=document.pk,
        file_name=body.file_name,
        declared_size_bytes=body.size_bytes,
        declared_type=body.mime_type,
        page_index=0,
        chunk_count=chunk_count,
        status="receiving",
        created_by=principal.user_id,
    )
    db.add(upload)
    await db.flush()
    return {
        "document_id": document.id,
        "upload_id": upload.id,
        "chunk_size_bytes": settings.upload_chunk_bytes,
        "chunk_count": chunk_count,
    }


async def mark_uploaded(
    db: AsyncSession, *, upload_id: str, page_count: int, sniffed_kind: str, original_key: str
) -> None:
    """#7 nhánh tài liệu gọi trong giao dịch của nó: tài liệu sang `analyzing`, đủ trang, xếp phân tích sau commit.

    Ghi `page_count`, `sniffed_kind`, `original_key`; upsert `document_pages` `0..page_count-1` (gọi lại
    không nhân đôi trang); không tạo `PipelineRunRow`.
    """
    document = (
        await db.execute(
            select(DocumentRow)
            .join(UploadRow, UploadRow.document_pk == DocumentRow.pk)
            .where(UploadRow.id == upload_id)
            .with_for_update(of=DocumentRow)
        )
    ).scalar_one()
    document.page_count = page_count
    document.sniffed_kind = sniffed_kind
    document.original_key = original_key
    document.status = "analyzing"
    await db.execute(
        pg_insert(DocumentPageRow)
        .values([{"document_pk": document.pk, "page_index": index} for index in range(page_count)])
        .on_conflict_do_nothing(constraint="uq_document_pages_document_page")
    )
    await db.flush()
    payload = DocumentAnalyzePayload(document_id=document.id)
    on_after_commit(db, lambda: send_task(ANALYZE_TASK, payload))
