"""Nguồn duy nhất của `Progress` (BE-BIND §4, bảng "Nguồn trạng thái").

Luật nằm ở **một** hàm thuần `progress_of`: #8 và luồng S1 gọi `progress_wire` (một lượt
tải, một truy vấn), còn N7 dựng cả trang bằng **một** truy vấn rồi gọi thẳng `progress_of`
cho từng dòng — không bản sao thứ hai của bảng §4.

Module này là "hàm worker nhập" (BE-00 §7): không nhập `fastapi`/`starlette`, trả `dict`
khoá dây chứ không `WireModel`.
"""

from datetime import datetime
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.instants import to_wire
from packages.db.models.drawings import PipelineRunRow, UploadRow

LAST_STEP: Final = "qualityCheck"
"""Bước hiển thị của lượt đã xong: FE vẽ mọi bước "xong" khi `completed` (BE-BIND §4)."""

FIRST_STEP: Final = "preprocess"
"""Bước hiển thị khi chưa có gì chạy: `pending` và upload `rejected` đều đứng ở đây."""


def _pending(upload_id: str) -> dict[str, object]:
    """Hàng 1 của bảng §4: upload `receiving`, hoặc lượt mới nhất còn `pending`."""
    return {"id": upload_id, "status": "pending", "step": FIRST_STEP, "progressPercent": 0}


def progress_of(
    upload_id: str,
    *,
    upload_status: str,
    rejected_code: str | None,
    run_status: str | None,
    current_step: str | None,
    progress_percent: int | None,
    error_code: str | None,
    started_at: datetime | None,
    ended_at: datetime | None,
) -> dict[str, object]:
    """Bảng "Nguồn trạng thái" của BE-BIND §4, từ giá trị cột sang dict khoá dây.

    Hàm thuần: người gọi đã có sẵn các cột (một truy vấn cho cả trang ở N7) thì không phải
    vào DB lần nữa. `run_*` là `None` khi lượt tải chưa có lượt chạy nào.

    Ba bất biến của FE: `endedAt` **chỉ** khi `completed` (lượt hỏng không có, K33); `error`
    luôn là mã UPPER_SNAKE; trường vắng thì vắng hẳn, không `null` (W2).
    """
    if upload_status == "rejected":
        return _pending(upload_id) | {"status": "failed", "error": rejected_code or ""}
    if upload_status != "complete" or run_status is None or run_status == "pending":
        return _pending(upload_id)

    wire: dict[str, object] = {
        "id": upload_id,
        "status": run_status,
        "step": LAST_STEP if run_status == "completed" else current_step,
        "progressPercent": 100 if run_status == "completed" else progress_percent,
    }
    if started_at is not None:
        wire["startedAt"] = to_wire(started_at)
    if run_status == "completed" and ended_at is not None:
        wire["endedAt"] = to_wire(ended_at)
    if run_status == "failed":
        wire["error"] = error_code or ""
    return wire


async def progress_wire(db: AsyncSession, upload_id: str) -> dict[str, object]:
    """`Progress` của một lượt tải và lượt chạy **mới nhất** của nó, bằng một truy vấn.

    Không có dòng upload → `ValueError`: mọi người gọi (#5-#8, S1, `record_step`) đã tra
    upload trước đó, nên đây là lỗi lập trình chứ không phải 404 của người dùng.
    """
    latest = (
        select(PipelineRunRow.id)
        .where(PipelineRunRow.upload_id == UploadRow.id)
        .order_by(PipelineRunRow.created_at.desc(), PipelineRunRow.id.desc())
        .limit(1)
        .correlate(UploadRow)
        .scalar_subquery()
    )
    stmt = (
        select(
            UploadRow.status,
            UploadRow.rejected_code,
            PipelineRunRow.status,
            PipelineRunRow.current_step,
            PipelineRunRow.progress_percent,
            PipelineRunRow.error_code,
            PipelineRunRow.started_at,
            PipelineRunRow.ended_at,
        )
        .select_from(UploadRow)
        .outerjoin(PipelineRunRow, PipelineRunRow.id == latest)
        .where(UploadRow.id == upload_id)
    )
    row = (await db.execute(stmt)).first()
    if row is None:
        raise ValueError(f"không có lượt tải {upload_id!r}")
    upload_status, rejected_code, run_status, step, percent, error_code, started_at, ended_at = row
    return progress_of(
        upload_id,
        upload_status=upload_status,
        rejected_code=rejected_code,
        run_status=run_status,
        current_step=step,
        progress_percent=percent,
        error_code=error_code,
        started_at=started_at,
        ended_at=ended_at,
    )
