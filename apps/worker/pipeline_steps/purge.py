"""Lõi lịch dọn artifact `runs/` của lượt đã kết thúc (B5-06c [6] "run_pipeline_artifact_purge")."""

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.worker.pipeline_orchestrate.keys import run_prefix
from apps.worker.pipeline_orchestrate.pins import mark_artifacts_purged
from apps.worker.pipeline_steps.settings import get_steps_settings
from packages.core.clock import Clock
from packages.db.models.drawings import PipelineRunRow, UploadRow
from packages.db.models.floors import FloorRow
from packages.db.models.pipeline_orchestrate import PipelineRunModelsRow
from packages.storage.port import ObjectStorage


@dataclass(frozen=True, slots=True)
class _DueRun:
    """Một dòng đến hạn dọn: đủ ba phần khoá kho (`run_prefix`) cộng `run_id` để đánh dấu."""

    run_id: str
    project_id: str
    level_id: str
    upload_id: str


async def _select_due(sessionmaker: async_sessionmaker[AsyncSession], clock: Clock, *, batch: int) -> list[_DueRun]:
    """Một `SELECT` không khoá: tối đa `batch` lượt `completed|failed` quá hạn giữ, cũ nhất trước.

    Mở và đóng session ngay trong hàm này — không giữ nó qua lượt xoá kho ở người gọi (K36).
    """
    cutoff = clock.now() - timedelta(seconds=get_steps_settings().PIPELINE_ARTIFACT_RETENTION_S)
    stmt = (
        select(
            PipelineRunModelsRow.run_id,
            UploadRow.project_id,
            FloorRow.level_id,
            PipelineRunRow.upload_id,
        )
        .select_from(PipelineRunModelsRow)
        .join(PipelineRunRow, PipelineRunRow.id == PipelineRunModelsRow.run_id)
        .join(UploadRow, UploadRow.id == PipelineRunRow.upload_id)
        .join(FloorRow, FloorRow.pk == PipelineRunRow.floor_pk)
        .where(
            PipelineRunModelsRow.artifacts_purged_at.is_(None),
            PipelineRunRow.status.in_(("completed", "failed")),
            PipelineRunRow.updated_at < cutoff,
        )
        .order_by(PipelineRunRow.updated_at, PipelineRunModelsRow.run_id)
        .limit(batch)
    )
    async with sessionmaker() as db:
        rows = (await db.execute(stmt)).all()
    return [_DueRun(run_id=r, project_id=p, level_id=lvl, upload_id=u) for r, p, lvl, u in rows]


async def run_pipeline_artifact_purge(
    sessionmaker: async_sessionmaker[AsyncSession], storage: ObjectStorage, clock: Clock, *, batch: int
) -> None:
    """Xoá `run_prefix(…)` của lượt `completed|failed` quá hạn giữ, rồi đánh dấu đã dọn.

    Mỗi dòng: xoá kho trước (ngoài mọi session), rồi một giao dịch ngắn đánh dấu — không gộp
    hai việc vào một giao dịch vì lượt xoá kho không phải SQL (K36). Lỗi kho (`delete_prefix`
    ném) cố ý **không** bị bắt: để nó lan ra ngoài dừng cả lượt dọn, vì một kho chập chờn ở
    dòng thứ `n` không nên khiến các dòng trước nó bị đánh dấu "đã dọn" sai sự thật — lượt lịch
    sau (24h) sẽ chọn lại đúng dòng còn nguyên `artifacts_purged_at IS NULL`.
    """
    for due in await _select_due(sessionmaker, clock, batch=batch):
        await storage.delete_prefix(
            run_prefix(project_id=due.project_id, level_id=due.level_id, upload_id=due.upload_id, run_id=due.run_id)
        )
        async with sessionmaker() as db:
            await mark_artifacts_purged(db, run_id=due.run_id, at=clock.now())
            await db.commit()
