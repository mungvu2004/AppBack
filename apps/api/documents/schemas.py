"""Thân và đáp của N39 (PHASE-1-CONTRACT §4.1); luật `fileName`/`mimeType`/`sizeBytes` lấy từ #5, không chép."""

from pydantic import Field

from apps.api.core.wire import WireModel, WireRequest
from apps.api.drawings.schemas import MIME_TYPE_MAX, FileName


class DocumentInitBody(WireRequest):
    """Thân N39: như `InitUploadBody` của #5 trừ `floorId`, `pageIndex`, `projectId` (dự án lấy từ đường)."""

    file_name: FileName
    mime_type: str = Field(max_length=MIME_TYPE_MAX)
    size_bytes: int = Field(ge=1)


class DocumentInitOut(WireModel):
    """Đáp N39: id tài liệu, id lượt tải, cỡ khúc và số khúc để FE gửi qua #6 rồi #7."""

    document_id: str
    upload_id: str
    chunk_size_bytes: int
    chunk_count: int
