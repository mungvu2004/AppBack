"""Lịch nền của registry model ML (B6-01 [6] "Lịch", "Dọn rác"; khuôn BE-00 §7).

`apps/worker` nhập module này để chạy beat, nên chỉ nhập `packages.*` và `registry` (không
`fastapi`, `starlette`, `jwt`, `argon2`). Hai lõi tách khỏi hàm lịch để test truyền đồng hồ và
storage của test; hàm lịch chỉ dựng tài nguyên thật.

- `run_model_evaluation_requeue`: gửi lại đánh giá của bản `pending|running` quá hạn, lùi
  theo luỹ thừa 2; hết `MODEL_EVAL_MAX_ATTEMPTS` thì chốt `failed` (`RETRY_EXHAUSTED`).
- `run_model_orphan_purge`: xoá object dưới `ml/models/` không dòng nào trỏ tới (tải lên
  dở, dòng bị huỷ). Không giữ session DB trong lúc gọi storage (K36).
"""

import logging
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Final

from sqlalchemy import ColumnElement, DateTime, Interval, func, literal, literal_column, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.admin_ml_registry.registry import request_evaluation
from apps.api.admin_ml_registry.settings import get_ml_registry_settings
from packages.core.clock import Clock, SystemClock
from packages.core.object_keys import MODELS_PREFIX
from packages.db.engine import session_scope, worker_sessionmaker
from packages.db.models.admin_ml_registry import ModelVersionRow
from packages.messaging import periodic
from packages.storage.port import ObjectStorage

_log: Final = logging.getLogger(__name__)

REQUEUE_TASK: Final = "default.admin_ml_registry.requeue_evaluations"
REQUEUE_EVERY: Final = timedelta(minutes=5)
PURGE_TASK: Final = "default.admin_ml_registry.purge_orphans"
PURGE_EVERY: Final = timedelta(hours=24)
PURGE_MIN_AGE: Final = timedelta(hours=24)
"""Object trẻ hơn mức này có thể là tải lên đang dở (dòng chưa commit), nên không đụng."""

REQUEUE_BATCH: Final = 100
PURGE_BATCH: Final = 500
EXHAUSTED_CODE: Final = "RETRY_EXHAUSTED"

_ONE_SECOND: Final = literal_column("interval '1 second'", type_=Interval())


def _overdue(now: datetime, after_s: int) -> ColumnElement[bool]:
    """Điều kiện SQL "quá hạn gửi lại": chưa từng gửi, hoặc cũ hơn `after_s * 2^(attempts - 1)` giây."""
    backoff = _ONE_SECOND * (after_s * func.power(2, func.greatest(ModelVersionRow.evaluation_attempts - 1, 0)))
    return or_(
        ModelVersionRow.evaluation_requested_at.is_(None),
        ModelVersionRow.evaluation_requested_at < literal(now, DateTime(timezone=True)) - backoff,
    )


async def run_model_evaluation_requeue(
    sessionmaker: async_sessionmaker[AsyncSession], clock: Clock, *, batch: int = REQUEUE_BATCH
) -> int:
    """Một lượt gửi lại; trả số bản đã xử lý (gửi lại hoặc chốt `failed`).

    Cả lô nằm trong **một** giao dịch giữ `FOR UPDATE SKIP LOCKED`: hai beat chồng nhau không
    xử lý cùng bản. Task gửi sau commit (K17) — trong worker callback chạy ngay khi `commit` trả.
    Bản hết lượt bị `UPDATE` thẳng dưới khoá đang giữ, không qua `set_evaluation` vì hàm đó
    cố ý bỏ qua mã tạm `RETRY_EXHAUSTED`.
    """
    settings = get_ml_registry_settings()
    now = clock.now()
    stmt = (
        select(ModelVersionRow)
        .where(ModelVersionRow.evaluation_status.in_(("pending", "running")))
        .where(_overdue(now, settings.model_eval_requeue_after_s))
        .order_by(ModelVersionRow.created_at, ModelVersionRow.id)
        .limit(batch)
        .with_for_update(skip_locked=True)
    )
    async with session_scope(sessionmaker) as db:
        rows = (await db.execute(stmt)).scalars().all()
        for row in rows:
            if row.evaluation_attempts < settings.model_eval_max_attempts:
                await request_evaluation(db, version_id=row.id, clock=clock)
            else:
                row.evaluation_status = "failed"
                row.evaluation_error_code = EXHAUSTED_CODE
                row.updated_at = now
                _log.warning("model_evaluation_exhausted", extra={"version_id": row.id})
    return len(rows)


async def _referenced(sessionmaker: async_sessionmaker[AsyncSession], keys: Sequence[str]) -> set[str]:
    """Trong `keys`, khoá nào là `weights_key` của một dòng — một truy vấn cho cả lô, session đóng ngay."""
    async with sessionmaker() as db:
        found = await db.execute(select(ModelVersionRow.weights_key).where(ModelVersionRow.weights_key.in_(keys)))
        return {key for key in found.scalars() if key is not None}


async def run_model_orphan_purge(
    sessionmaker: async_sessionmaker[AsyncSession],
    storage: ObjectStorage,
    clock: Clock,
    *,
    batch: int = PURGE_BATCH,
) -> int:
    """Xoá object mồ côi cũ hơn `PURGE_MIN_AGE` dưới `ml/models/`; trả số object đã xoá.

    Duyệt theo lô `batch`, mỗi lô tra DB một lần rồi mới `delete` (không N+1). Tra DB xong
    mới xoá: dòng chèn giữa hai bước chỉ có thể là dòng mới, mà object mới thì `older_than` đã
    loại từ đầu.
    """
    cutoff = clock.now() - PURGE_MIN_AGE
    deleted = 0
    chunk: list[str] = []
    async for info in storage.list_prefix(MODELS_PREFIX, older_than=cutoff):
        chunk.append(info.key)
        if len(chunk) >= batch:
            deleted += await _purge_chunk(sessionmaker, storage, chunk)
            chunk = []
    if chunk:
        deleted += await _purge_chunk(sessionmaker, storage, chunk)
    return deleted


async def _purge_chunk(
    sessionmaker: async_sessionmaker[AsyncSession], storage: ObjectStorage, keys: Sequence[str]
) -> int:
    """Xoá các khoá của lô không có dòng nào trỏ tới; trả số đã xoá."""
    kept = await _referenced(sessionmaker, keys)
    orphans = [key for key in keys if key not in kept]
    for key in orphans:
        await storage.delete(key)
    return len(orphans)


@periodic(REQUEUE_TASK, every=REQUEUE_EVERY)
async def requeue_pending_model_evaluations() -> None:
    """Hàm lịch: dựng tài nguyên thật rồi gọi lõi gửi lại đánh giá."""
    processed = await run_model_evaluation_requeue(worker_sessionmaker(), SystemClock())
    _log.info("model_evaluation_requeue", extra={"processed": processed})


@periodic(PURGE_TASK, every=PURGE_EVERY)
async def purge_ml_model_orphans() -> None:
    """Hàm lịch: dựng storage thật rồi gọi lõi dọn object mồ côi."""
    from apps.api.library.assets import open_storage

    clock = SystemClock()
    deleted = await run_model_orphan_purge(worker_sessionmaker(), open_storage(clock), clock)
    _log.info("model_orphan_purge", extra={"deleted": deleted})
