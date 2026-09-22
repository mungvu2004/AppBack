"""Lịch dọn nhật ký hoạt động `default.access.purge_activity` (BE-00 §7 "Dọn rác", J01, J06)."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Final

import pytest
from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.access.jobs import EVERY, TASK_NAME, purge_activity, run_purge_activity
from apps.api.access.kinds import ActivityKind
from packages.core.clock import SystemClock
from packages.db.engine import GATE_CONNECT_TIMEOUT_S, create_engine, create_sessionmaker
from packages.db.models.access import ActivityLog
from packages.db.settings import DatabaseSettings, reset_database_settings_cache
from packages.messaging.schedules import schedule_entries
from packages.testing.factories.auth import make_user
from packages.testing.fixtures.clock import FakeClock

DAY: Final = timedelta(days=1)
SMALL_BATCH: Final = 2


async def _seed(db: AsyncSession, now: datetime) -> dict[str, int]:
    """5 dòng tuổi 181 ngày (phải xoá), 1 dòng tuổi 179 ngày (phải giữ)."""
    user = await make_user(db, password=None)

    def row(at: datetime) -> dict[str, object]:
        """Một dòng `activity_log` với mốc thời gian `at` cho trước."""
        return {
            "actor_id": user.id,
            "kind": ActivityKind.PROJECT_CREATE.value,
            "object_code": "prj_seed",
            "object_label": "Dự án hạt giống",
            "project_id": None,
            "at": at,
        }

    doomed = [row(now - 181 * DAY) for _ in range(5)]
    kept = [row(now - 179 * DAY)]
    await db.execute(insert(ActivityLog), doomed + kept)
    await db.commit()
    return {"doomed": len(doomed), "kept": len(kept)}


async def _count_on(session: AsyncSession) -> int:
    """Số dòng còn lại, đọc trên session cho trước."""
    return int((await session.execute(select(func.count()).select_from(ActivityLog))).scalar_one())


async def _count(maker: async_sessionmaker[AsyncSession]) -> int:
    """Số dòng còn lại, đọc trên session mới."""
    async with maker() as session:
        return await _count_on(session)


async def test_purge_activity__J01(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Chạy đúng: lô = 2, 5 dòng 181 ngày bị xoá qua 3 lô, dòng 179 ngày còn."""
    caplog.set_level(logging.INFO, logger="apps.api.access.jobs")
    counts = await _seed(db_session, fake_clock.now())
    removed = await run_purge_activity(db_sessionmaker, fake_clock, batch=SMALL_BATCH)
    assert removed == counts["doomed"]
    assert await _count(db_sessionmaker) == counts["kept"]
    record = next(r for r in caplog.records if r.msg == "activity_purged")
    assert record.__dict__["batches"] == 3  # 2 + 2 + 1


async def test_purge_activity__J06(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Giao lặp: lượt thứ hai không xoá thêm gì và không hỏng."""
    counts = await _seed(db_session, fake_clock.now())
    assert await run_purge_activity(db_sessionmaker, fake_clock, batch=SMALL_BATCH) == counts["doomed"]
    assert await run_purge_activity(db_sessionmaker, fake_clock, batch=SMALL_BATCH) == 0
    assert await _count(db_sessionmaker) == counts["kept"]


def test_schedule_is_registered() -> None:
    """Lịch nằm trong sổ của `packages.messaging` để beat của worker đọc được."""
    entries = {entry.name: entry for entry in schedule_entries()}
    assert entries[TASK_NAME].every == EVERY
    assert entries[TASK_NAME].function == "purge_activity"


async def _on_fresh_engine[ResultT](db_url: str, work: Callable[[AsyncSession], Awaitable[ResultT]]) -> ResultT:
    """Chạy `work` trên engine riêng của vòng `asyncio.run` hiện tại (test khói là test đồng bộ)."""
    engine = create_engine(DatabaseSettings(database_url=db_url, db_connect_timeout_s=int(GATE_CONNECT_TIMEOUT_S)))
    try:
        async with create_sessionmaker(engine)() as session:
            return await work(session)
    finally:
        await engine.dispose()


def test_purge_activity_smoke(db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test khói: gọi chính hàm lịch (giờ thật, `worker_sessionmaker()`) và khẳng định lõi đã xoá."""
    counts = asyncio.run(_on_fresh_engine(db_url, lambda session: _seed(session, SystemClock().now())))
    monkeypatch.setenv("DATABASE_URL", db_url)
    reset_database_settings_cache()
    try:
        purge_activity()
    finally:
        reset_database_settings_cache()
    assert asyncio.run(_on_fresh_engine(db_url, _count_on)) == counts["kept"]
