"""Lõi task `pipeline.orchestrate.step_done` (B5-06c [6]) và `queue_build` dùng chung với quét bù.

Một giao dịch ngắn: khoá lượt, kiểm kết quả dưới khoá (không tin `apps/ml`, B5-05), đẩy bước
theo thứ tự, xếp bước sau qua `on_after_commit` (J09). Mọi hàm trả `None` của B2-04/B5-06a
nghĩa là lượt đã kết thúc hay bị thay: rollback, log `pipeline_result_ignored`.
"""

from dataclasses import dataclass
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.drawings.drawings import current_drawing
from apps.api.drawings.runs import RunRow, record_step
from apps.api.project_settings.read import read_settings
from apps.worker.pipeline_orchestrate.keys import run_prefix
from apps.worker.pipeline_steps.errors import PIPELINE_RESULT_INVALID
from packages.core.clock import Clock
from packages.db.hooks import on_after_commit
from packages.db.models.drawings import DrawingRow
from packages.db.models.floors import FloorRow
from packages.messaging.celery_app import send_task
from packages.messaging.payloads.pipeline import BuildStepPayload
from packages.ml_contracts.payloads import StepResultPayload

STEP_DONE_TASK: Final = "pipeline.orchestrate.step_done"
BUILD_TASK: Final = "pipeline.build.run"
PERSIST_TASK: Final = "pipeline.persist.run"
QUALITY_TASK: Final = "pipeline.quality.run"
"""Tên task bước sau; tự khai ở đây vì [1] cấm nhập module của B5-06b, B5-07."""
BUILD_STEP: Final = "spatialDataBuild"


@dataclass(frozen=True, slots=True)
class RunContext:
    """Dữ kiện để xếp lại một bước: bản vẽ hiện hành của tầng (thuộc đúng lượt tải) và tiền tố."""

    drawing: DrawingRow
    project_id: str
    level_id: str
    run_prefix: str


async def load_run_context(db: AsyncSession, run: RunRow) -> RunContext | None:
    """Bản vẽ hiện hành của tầng + tiền tố artifact; bản vẽ vắng hay của lượt tải khác → `None`."""
    drawing = await current_drawing(db, run.floor_pk)
    if drawing is None or drawing.upload_id != run.upload_id:
        return None
    stmt = select(FloorRow.project_id, FloorRow.level_id).where(FloorRow.pk == run.floor_pk)
    floor = (await db.execute(stmt)).one()
    prefix = run_prefix(project_id=floor.project_id, level_id=floor.level_id, upload_id=run.upload_id, run_id=run.id)
    return RunContext(drawing=drawing, project_id=floor.project_id, level_id=floor.level_id, run_prefix=prefix)


async def queue_build(db: AsyncSession, run: RunRow, *, clock: Clock) -> bool:
    """Đăng ký gửi `pipeline.build.run` sau commit; bản vẽ không khớp lượt → `failed` và `False`.

    Gọi trong giao dịch đang giữ `lock_run`, không commit. `run` chỉ cần `id`, `upload_id`,
    `floor_pk` (ảnh chụp trước khi đẩy bước vẫn dùng được).
    """
    ctx = await load_run_context(db, run)
    if ctx is None:
        await record_step(
            db, run_id=run.id, step=BUILD_STEP, status="failed", clock=clock, error_code=PIPELINE_RESULT_INVALID
        )
        return False
    scale = (await read_settings(db, ctx.project_id)).default_scale_mm_per_px
    payload = BuildStepPayload(
        run_id=run.id,
        level_id=ctx.level_id,
        run_prefix=ctx.run_prefix,
        width_px=ctx.drawing.width_px,
        height_px=ctx.drawing.height_px,
        fallback_mm_per_px=scale,
    )
    on_after_commit(db, lambda: send_task(BUILD_TASK, payload))
    return True


async def run_pipeline_step_done(
    payload: StepResultPayload, *, sessionmaker: async_sessionmaker[AsyncSession], clock: Clock
) -> None:
    """Nhận kết quả một bước ML hay `spatialDataBuild`, đẩy bước, xếp bước sau ([6] "step_done")."""
    raise NotImplementedError  # việc A thay thân hàm


async def fail_pipeline_step_done_core(
    payload: StepResultPayload, code: str, *, sessionmaker: async_sessionmaker[AsyncSession], clock: Clock
) -> None:
    """Thân `on_failed`: lượt còn sống và họ chưa có trong `used` → `record_step(step, failed, code)`."""
    raise NotImplementedError  # việc A thay thân hàm
