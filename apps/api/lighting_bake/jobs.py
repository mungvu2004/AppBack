"""Lịch nền của nướng ánh sáng (khuôn BE-00 §7): `sweep_lighting_bakes` mỗi 5 phút.

`apps/worker` nhập module này để chạy beat, nên chỉ nhập `packages.*` và `state`/`settings`
(không `apps.api.core`, `fastapi`, `starlette`). Một lượt quét làm hai việc trong **một** giao dịch:

1. chốt `failed` `LIGHTING_BAKE_STALLED` lượt `queued` cũ hơn 6 giờ (`created_at`) và lượt
   `running` cũ hơn 70 phút (`started_at`) — worker chết hay broker mất tin nhắn;
2. gửi lại task của lượt `queued` có `updated_at` cũ hơn 10 phút, và đẩy `updated_at` lên để
   lượt quét sau không gửi lặp. Task gửi sau commit (K17).
"""

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Final

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.lighting_bake.settings import get_lighting_bake_settings
from apps.api.lighting_bake.state import LIGHTING_BAKE_STALLED
from packages.core.clock import Clock, SystemClock
from packages.db.engine import worker_sessionmaker
from packages.db.hooks import after_commit_idle, on_after_commit
from packages.messaging import periodic, send_task
from packages.messaging.payloads.lighting_bake import LIGHTING_BAKE_TASK, LightingBakePayload

_log: Final = logging.getLogger(__name__)

SWEEP_TASK: Final = "default.lighting_bake.sweep"
SWEEP_EVERY: Final = timedelta(minutes=5)
SWEEP_BATCH: Final = 100

_FAIL_STALLED: Final = text(
    "UPDATE lighting_bakes SET status = 'failed', failure_code = :code, ended_at = :now, updated_at = :now "
    "WHERE (status = 'queued' AND created_at < :queued_cutoff) "
    "OR (status = 'running' AND COALESCE(started_at, updated_at) < :running_cutoff) RETURNING id"
)
_RESEND: Final = text(
    "SELECT id FROM lighting_bakes WHERE status = 'queued' AND updated_at < :cutoff "
    "ORDER BY updated_at, id LIMIT :batch FOR UPDATE SKIP LOCKED"
)
_TOUCH: Final = text("UPDATE lighting_bakes SET updated_at = :now WHERE id = ANY(:ids)")


@dataclass(frozen=True, slots=True)
class SweepResult:
    """Số lượt bị chốt `failed` và số lượt được gửi lại trong một lượt quét."""

    failed: int
    resent: int


def _send_later(db: AsyncSession, bake_id: str) -> None:
    """Đăng ký gửi `bake.lighting.run` cho `bake_id` sau khi giao dịch của `db` commit."""
    on_after_commit(db, lambda: send_task(LIGHTING_BAKE_TASK, LightingBakePayload(bake_id=bake_id)))


async def run_lighting_bake_sweep(
    sessionmaker: async_sessionmaker[AsyncSession], clock: Clock, *, batch: int = SWEEP_BATCH
) -> SweepResult:
    """Một lượt quét: chốt lượt kẹt trước, rồi gửi lại lượt `queued` quá hạn.

    Chốt trước để một lượt vừa quá 6 giờ không bị gửi lại rồi hỏng ngay trong cùng lượt.
    `FOR UPDATE SKIP LOCKED`: hai beat chồng nhau không gửi lặp cùng một lượt.
    """
    settings = get_lighting_bake_settings()
    now = clock.now()
    async with sessionmaker() as db:
        failed = (
            (
                await db.execute(
                    _FAIL_STALLED,
                    {
                        "code": LIGHTING_BAKE_STALLED,
                        "now": now,
                        "queued_cutoff": now - timedelta(seconds=settings.lighting_bake_queued_max_age_s),
                        "running_cutoff": now - timedelta(seconds=settings.lighting_bake_running_max_age_s),
                    },
                )
            )
            .scalars()
            .all()
        )
        cutoff = now - timedelta(seconds=settings.lighting_bake_resend_after_s)
        ids = list((await db.execute(_RESEND, {"cutoff": cutoff, "batch": batch})).scalars())
        if ids:
            await db.execute(_TOUCH, {"now": now, "ids": ids})
        for bake_id in ids:
            _send_later(db, bake_id)
        await db.commit()
        # Gửi sau commit chạy trên executor riêng: chờ xong rồi mới trả (BE-00 §7, như drawings/jobs.py).
        await after_commit_idle(db)
    for bake_id in failed:
        _log.warning("lighting_bake_stalled", extra={"bake_id": bake_id})
    return SweepResult(failed=len(failed), resent=len(ids))


@periodic(SWEEP_TASK, every=SWEEP_EVERY)
async def sweep_lighting_bakes() -> None:
    """Hàm lịch: dựng tài nguyên thật rồi gọi lõi quét."""
    result = await run_lighting_bake_sweep(worker_sessionmaker(), SystemClock())
    _log.info("lighting_bake_sweep", extra={"failed": result.failed, "resent": result.resent})
