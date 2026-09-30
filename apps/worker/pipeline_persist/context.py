"""Dữ kiện một lượt chạy cần để ghi kết quả pipeline (B5-06b [2], [6] bước 1).

Một `SELECT` không khoá nối `pipeline_runs` → `uploads` → `floors` → `projects`: lõi gọi nó
hai lần (lần đầu ngoài giao dịch ghi để rồi nhả session trước khi đọc kho — K36; lần hai dưới
khoá của `lock_run`) nên phải rẻ và không tự ý lọc. Cố ý **không** lọc xoá mềm: hai trạng thái
xoá là dữ kiện trả về (`floor_deleted_at`, `project_deleted`), còn quyết định hoãn hay đánh
hỏng là của `service.py` — nơi duy nhất biết cửa sổ khôi phục.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.drawings import PipelineRunRow, UploadRow
from packages.db.models.floors import FloorRow
from packages.db.models.projects import Project


@dataclass(frozen=True, slots=True)
class PersistContext:
    """Ảnh chụp dữ kiện của một lượt chạy; đông cứng để không ai ghi DB qua nó.

    `uploader_id` là `uploads.created_by` (K05, [7]): chỉ người tải lên mới được báo.
    `floor_deleted_at`/`project_deleted` nguyên trạng — cửa sổ khôi phục do lõi so.
    """

    run_id: str
    upload_id: str
    floor_pk: int
    project_id: str
    project_name: str
    level_id: str
    floor_name: str
    uploader_id: str
    floor_deleted_at: datetime | None
    project_deleted: bool


async def load_context(db: AsyncSession, run_id: str) -> PersistContext | None:
    """Đọc dữ kiện của lượt; không có dòng lượt (hay dòng liên quan đã biến mất) → `None`."""
    stmt = (
        select(
            PipelineRunRow.id,
            PipelineRunRow.upload_id,
            PipelineRunRow.floor_pk,
            FloorRow.project_id,
            Project.name,
            FloorRow.level_id,
            FloorRow.name,
            UploadRow.created_by,
            FloorRow.deleted_at,
            Project.deleted_at,
        )
        .join(UploadRow, UploadRow.id == PipelineRunRow.upload_id)
        .join(FloorRow, FloorRow.pk == PipelineRunRow.floor_pk)
        .join(Project, Project.id == FloorRow.project_id)
        .where(PipelineRunRow.id == run_id)
    )
    row = (await db.execute(stmt)).first()
    if row is None:
        return None
    return PersistContext(
        run_id=row[0],
        upload_id=row[1],
        floor_pk=row[2],
        project_id=row[3],
        project_name=row[4],
        level_id=row[5],
        floor_name=row[6],
        uploader_id=row[7],
        floor_deleted_at=row[8],
        project_deleted=row[9] is not None,
    )
