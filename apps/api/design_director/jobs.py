"""Lịch nền của AI chọn phong cách (khuôn `apps/api/lighting_bake/jobs.py`): `sweep_design_concepts` mỗi 5 phút.

`apps/worker` nhập module này để chạy beat, nên chỉ nhập `packages.*` và `state`/`settings`.
Một lượt quét, **một** giao dịch: chốt `failed` `DESIGN_DIRECTOR_STALLED` lượt `queued` cũ hơn 2 giờ
(`created_at`) và `running` cũ hơn 15 phút (`started_at` của lần nhận gần nhất); rồi gửi lại task của lượt
`queued` có `updated_at` cũ hơn 10 phút và đẩy `updated_at` lên. Task gửi sau commit (K17). Không có object để xoá.
"""

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Final

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.design_director.settings import get_design_director_settings
from apps.api.design_director.state import DESIGN_DIRECTOR_STALLED
from packages.core.clock import Clock, SystemClock
from packages.db.engine import worker_sessionmaker
from packages.db.hooks import after_commit_idle, on_after_commit
from packages.messaging import periodic, send_task
from packages.messaging.payloads.design_director import DESIGN_DIRECTOR_TASK, DesignConceptPayload

_log: Final = logging.getLogger(__name__)

SWEEP_TASK: Final = "default.design_director.sweep"
SWEEP_EVERY: Final = timedelta(minutes=5)
SWEEP_BATCH: Final = 100

_FAIL_STALLED: Final = text(
    "UPDATE design_concepts SET status = 'failed', failure_code = :code, ended_at = :now, updated_at = :now "
    "WHERE (status = 'queued' AND created_at < :queued_cutoff) "
    "OR (status = 'running' AND COALESCE(started_at, updated_at) < :running_cutoff) RETURNING id"
)
_RESEND: Final = text(
    "SELECT id FROM design_concepts WHERE status = 'queued' AND updated_at < :cutoff "
    "ORDER BY updated_at, id LIMIT :batch FOR UPDATE SKIP LOCKED"
)
_TOUCH: Final = text("UPDATE design_concepts SET updated_at = :now WHERE id = ANY(:ids)")


@dataclass(frozen=True, slots=True)
class SweepResult:
    """Số lượt bị chốt `failed` và số lượt được gửi lại trong một lượt quét."""

    failed: int
    resent: int


def _send_later(db: AsyncSession, concept_id: str) -> None:
    """Đăng ký gửi `design.director.run` cho `concept_id` sau khi giao dịch của `db` commit."""
    on_after_commit(db, lambda: send_task(DESIGN_DIRECTOR_TASK, DesignConceptPayload(concept_id=concept_id)))


async def run_design_concept_sweep(
    sessionmaker: async_sessionmaker[AsyncSession], clock: Clock, *, batch: int = SWEEP_BATCH
) -> SweepResult:
    """Một lượt quét: chốt lượt kẹt trước (để lượt vừa quá hạn không bị gửi lại), rồi gửi lại lượt `queued` im lâu.

    `FOR UPDATE SKIP LOCKED`: hai beat chồng nhau không gửi lặp cùng một lượt.
    """
    settings = get_design_director_settings()
    now = clock.now()
    async with sessionmaker() as db:
        params = {
            "code": DESIGN_DIRECTOR_STALLED,
            "now": now,
            "queued_cutoff": now - timedelta(seconds=settings.design_director_queued_max_age_s),
            "running_cutoff": now - timedelta(seconds=settings.design_director_running_max_age_s),
        }
        failed = list((await db.execute(_FAIL_STALLED, params)).scalars())
        cutoff = now - timedelta(seconds=settings.design_director_resend_after_s)
        ids = list((await db.execute(_RESEND, {"cutoff": cutoff, "batch": batch})).scalars())
        if ids:
            await db.execute(_TOUCH, {"now": now, "ids": ids})
        for concept_id in ids:
            _send_later(db, concept_id)
        await db.commit()
        await after_commit_idle(db)
    for concept_id in failed:
        _log.warning("design_concept_stalled", extra={"concept_id": concept_id})
    return SweepResult(failed=len(failed), resent=len(ids))


@periodic(SWEEP_TASK, every=SWEEP_EVERY)
async def sweep_design_concepts() -> None:
    """Hàm lịch: dựng tài nguyên thật rồi gọi lõi quét."""
    result = await run_design_concept_sweep(worker_sessionmaker(), SystemClock())
    _log.info("design_concept_sweep", extra={"failed": result.failed, "resent": result.resent})
