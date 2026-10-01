"""Lõi lịch quét bù lượt chạy kẹt (B5-06c [6] "run_stuck_pipeline_sweep", BE-00 §7 "Chuỗi nhiều bước").

Một lượt `running` kẹt khi thông điệp bước hiện tại mất (worker chết giữa `acks_late`, rollback
bỏ callback J09): DB vẫn `running`, hàng rỗng, không ai đẩy bước. Lõi gửi **lại** bước đang dở
tối đa `PIPELINE_STEP_REQUEUE_MAX` lần rồi mới đánh `PIPELINE_STEP_TIMEOUT` — gửi lại an toàn vì
mọi bước sau đều bỏ giao lặp (`record_step` trả `None` khi bước lùi, `queue_infer` bỏ họ đã có
trong `used`).

Hai bất biến đắt giá:
- **Redis trước mọi session** (K36): `LLEN` của hai hàng đọc xong mới mở session, nên broker treo
  không giữ một kết nối pool nào; hàng không đọc được coi như **còn việc** (thà chậm một nhịp 5
  phút hơn gửi lại một bước còn đang chạy).
- **Mốc im đọc hai lần**: một lần không khoá để chọn lô, một lần dưới `lock_run` + `load_pins(
  for_update=True)` — kết quả thật tới giữa hai lần đọc thì lượt bị bỏ khỏi lượt quét này.

`pending` không thuộc lõi này (B2-04 lo lượt chưa khởi động).
"""

import asyncio
import logging
from typing import Final

from redis.asyncio import Redis as AsyncRedis
from redis.exceptions import RedisError
from sqlalchemy import ARRAY, Text, bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.drawings.runs import RunRow, lock_run, publish_progress_after_commit, record_step, send_start_after_commit
from apps.worker.pipeline_orchestrate.dispatch import INFER_TASKS, queue_infer
from apps.worker.pipeline_orchestrate.pins import RunPins, load_pins, set_step_requeue
from apps.worker.pipeline_steps.errors import PIPELINE_RESULT_INVALID, PIPELINE_STEP_TIMEOUT
from apps.worker.pipeline_steps.settings import StepsSettings, get_steps_settings
from apps.worker.pipeline_steps.step_done import BUILD_STEP, BUILD_TASK, QUALITY_TASK, load_run_context, queue_build
from packages.core.clock import Clock
from packages.db.engine import session_scope
from packages.db.hooks import after_commit_idle, on_after_commit
from packages.messaging.celery_app import queue_for, send_task
from packages.messaging.payloads.pipeline import RunStepPayload
from packages.ml_contracts.families import MODEL_FAMILIES

_log: Final = logging.getLogger(__name__)

LLEN_TIMEOUT_S: Final = 1.0
"""Trần đọc một `LLEN`; quá hạn → hàng coi như còn việc (`broker` treo không được giữ lịch)."""

ML_QUEUE: Final = queue_for(INFER_TASKS["wallSegmentation"])
CPU_QUEUE: Final = queue_for(BUILD_TASK)
"""Khoá danh sách kombu của hai hàng, suy từ chính tên task sẽ gửi (không chép tên hàng, R-07)."""

_ML_STEPS: Final = list(MODEL_FAMILIES)

_CANDIDATES: Final = text(
    "SELECT r.id FROM pipeline_runs r JOIN pipeline_run_models m ON m.run_id = r.id"
    " WHERE r.status = 'running' AND r.superseded_by IS NULL"
    " AND :now - greatest(r.updated_at, m.updated_at)"
    " >= make_interval(secs => :after * power(2, m.step_requeue_count))"
    " AND (NOT (:cpu_busy OR (:ml_busy AND r.current_step = ANY(:ml_steps)))"
    " OR (r.started_at IS NOT NULL AND :now - r.started_at > make_interval(secs => :run_max)))"
    " ORDER BY greatest(r.updated_at, m.updated_at) LIMIT :batch"
).bindparams(bindparam("ml_steps", type_=ARRAY(Text)))
"""Chọn lô: lượt chờ hàng bị loại **trong** `WHERE` nên không chiếm suất `LIMIT` ([6] bước 2)."""

_IDLE_MARK: Final = text(
    "SELECT greatest(r.updated_at, m.updated_at) FROM pipeline_runs r"
    " JOIN pipeline_run_models m ON m.run_id = r.id WHERE r.id = :run_id"
)


async def _queue_busy(broker: AsyncRedis, key: str) -> bool:
    """`LLEN key > 0`; quá `LLEN_TIMEOUT_S` hay Redis lỗi → `True` (coi như còn việc)."""
    try:
        return await asyncio.wait_for(broker.llen(key), LLEN_TIMEOUT_S) > 0
    except (TimeoutError, RedisError) as exc:
        _log.warning("sweep_queue_unreadable", extra={"queue": key, "reason": type(exc).__name__})
        return True


async def _candidates(
    db: AsyncSession, clock: Clock, settings: StepsSettings, *, batch: int, cpu_busy: bool, ml_busy: bool
) -> list[str]:
    """Id các lượt im quá ngưỡng lùi, cũ trước; không khoá dòng nào."""
    params = {
        "now": clock.now(),
        "after": float(settings.PIPELINE_STEP_REQUEUE_AFTER_S),
        "run_max": float(settings.PIPELINE_RUN_MAX_S),
        "cpu_busy": cpu_busy,
        "ml_busy": ml_busy,
        "ml_steps": _ML_STEPS,
        "batch": batch,
    }
    return list((await db.execute(_CANDIDATES, params)).scalars())


async def _idle_seconds(db: AsyncSession, run_id: str, clock: Clock) -> float | None:
    """Số giây lượt đã im, đọc lại dưới khoá; dòng ghim mất → `None`."""
    mark = (await db.execute(_IDLE_MARK, {"run_id": run_id})).scalar_one_or_none()
    return None if mark is None else (clock.now() - mark).total_seconds()


async def _resend(db: AsyncSession, run: RunRow, pins: RunPins, clock: Clock) -> bool:
    """Xếp lại bước `run.current_step` sau commit; bản vẽ không khớp lượt → `False` (đã `record_step`)."""
    if run.current_step == "preprocess":
        send_start_after_commit(db, run_id=run.id, upload_id=run.upload_id)
        return True
    if run.current_step == BUILD_STEP:
        return await queue_build(db, run, clock=clock)
    if run.current_step == "qualityCheck":
        payload = RunStepPayload(run_id=run.id)
        on_after_commit(db, lambda: send_task(QUALITY_TASK, payload))
        return True
    ctx = await load_run_context(db, run)
    if ctx is None:
        await record_step(
            db,
            run_id=run.id,
            step=run.current_step,
            status="failed",
            clock=clock,
            error_code=PIPELINE_RESULT_INVALID,
        )
        return False
    queue_infer(
        db,
        pins=pins,
        run_prefix=ctx.run_prefix,
        page_key=ctx.drawing.page_key,
        width_px=ctx.drawing.width_px,
        height_px=ctx.drawing.height_px,
        px_per_paper_mm=None,
    )
    return True


async def _requeue_one(
    sessionmaker: async_sessionmaker[AsyncSession], run_id: str, clock: Clock, settings: StepsSettings
) -> None:
    """Một giao dịch cho một lượt: khoá, kiểm lại mốc im, gửi lại hay đánh hết trần."""
    async with session_scope(sessionmaker) as db:
        run = await lock_run(db, run_id=run_id)
        if run is None:
            return
        pins = await load_pins(db, run_id, for_update=True)
        idle = None if pins is None else await _idle_seconds(db, run_id, clock)
        if pins is None or idle is None:
            return
        count = pins.step_requeue_count
        if idle < settings.PIPELINE_STEP_REQUEUE_AFTER_S * 2**count:
            _log.info("sweep_run_fresh", extra={"run_id": run_id, "idle_s": idle})
            return
        if count >= settings.PIPELINE_STEP_REQUEUE_MAX:
            _log.info("sweep_run_timeout", extra={"run_id": run_id, "step": run.current_step, "idle_s": idle})
            await record_step(
                db,
                run_id=run_id,
                step=run.current_step,
                status="failed",
                clock=clock,
                error_code=PIPELINE_STEP_TIMEOUT,
            )
            return
        await set_step_requeue(db, run_id=run_id, count=count + 1)
        _log.info(
            "sweep_run_requeued",
            extra={"run_id": run_id, "step": run.current_step, "attempt": count + 1, "idle_s": idle},
        )
        if await _resend(db, run, pins, clock):
            await publish_progress_after_commit(db, run.upload_id)
    await after_commit_idle(db)


async def run_stuck_pipeline_sweep(
    sessionmaker: async_sessionmaker[AsyncSession], broker: AsyncRedis, clock: Clock, *, batch: int
) -> None:
    """Gửi lại bước đang dở của lượt im quá ngưỡng; hết trần → `PIPELINE_STEP_TIMEOUT`.

    `broker` của người gọi không bị đóng ở đây (lịch nền dùng lại client của tiến trình).
    """
    settings = get_steps_settings()
    cpu_busy, ml_busy = await asyncio.gather(_queue_busy(broker, CPU_QUEUE), _queue_busy(broker, ML_QUEUE))
    async with session_scope(sessionmaker) as db:
        run_ids = await _candidates(db, clock, settings, batch=batch, cpu_busy=cpu_busy, ml_busy=ml_busy)
    _log.info("sweep_scan", extra={"found": len(run_ids), "cpu_busy": cpu_busy, "ml_busy": ml_busy})
    for run_id in run_ids:
        await _requeue_one(sessionmaker, run_id, clock, settings)
