"""Lịch dọn phiên `default.auth.purge_sessions` (BE-00 §7 "Dọn rác", J01, J06)."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Final
from uuid import uuid4

import pytest
from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.auth.jobs import EVERY, TASK_NAME, purge_sessions, run_purge_sessions
from packages.core.clock import SystemClock
from packages.db.engine import GATE_CONNECT_TIMEOUT_S, create_engine, create_sessionmaker
from packages.db.models.auth import RefreshSession
from packages.db.settings import DatabaseSettings, reset_database_settings_cache
from packages.messaging.schedules import schedule_entries
from packages.testing.factories.auth import make_user
from packages.testing.fixtures.clock import FakeClock

DAY: Final = timedelta(days=1)
SMALL_BATCH: Final = 2


async def _seed(db: AsyncSession, now: datetime) -> dict[str, int]:
    """Ba phiên phải xoá, ba phiên phải giữ (còn sống, chết chưa đủ 1 ngày); trả số dòng mỗi nhóm."""
    user = await make_user(db, password=None)

    def row(*, absolute: datetime, revoked: datetime | None = None) -> dict[str, object]:
        """Một dòng phiên với hạn tuyệt đối và mốc thu hồi cho trước."""
        return {
            "id": uuid4(),
            "user_id": user.id,
            "current_token_hash": "0" * 64,
            "remember": True,
            "idle_expires_at": absolute,
            "absolute_expires_at": absolute,
            "revoked_at": revoked,
            "revoked_reason": None if revoked is None else "logout",
        }

    doomed = [
        row(absolute=now - DAY - timedelta(seconds=1)),
        row(absolute=now + DAY, revoked=now - DAY - timedelta(seconds=1)),
        row(absolute=now - 3 * DAY, revoked=now - 2 * DAY),
    ]
    kept = [
        row(absolute=now + DAY),
        row(absolute=now - timedelta(hours=1)),
        row(absolute=now + DAY, revoked=now - timedelta(hours=1)),
    ]
    await db.execute(insert(RefreshSession), doomed + kept)
    await db.commit()
    return {"doomed": len(doomed), "kept": len(kept)}


async def _count_on(session: AsyncSession) -> int:
    """Số phiên còn lại, đọc trên session cho trước."""
    return int((await session.execute(select(func.count()).select_from(RefreshSession))).scalar_one())


async def _count(maker: async_sessionmaker[AsyncSession]) -> int:
    """Số phiên còn lại, đọc trên session mới."""
    async with maker() as session:
        return await _count_on(session)


async def test_purge_sessions__J01(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Chạy đúng: xoá phiên hết hạn tuyệt đối hay thu hồi quá 1 ngày, giữ phần còn lại."""
    counts = await _seed(db_session, fake_clock.now())
    assert await run_purge_sessions(db_sessionmaker, fake_clock) == counts["doomed"]
    assert await _count(db_sessionmaker) == counts["kept"]


async def test_purge_sessions__J06(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Giao lặp: lượt thứ hai không xoá thêm gì và không hỏng."""
    counts = await _seed(db_session, fake_clock.now())
    assert await run_purge_sessions(db_sessionmaker, fake_clock) == counts["doomed"]
    assert await run_purge_sessions(db_sessionmaker, fake_clock) == 0
    assert await _count(db_sessionmaker) == counts["kept"]


async def test_purge_runs_in_batches(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Lô nhỏ hơn số dòng phải xoá: vòng lặp chạy tiếp cho tới hết."""
    counts = await _seed(db_session, fake_clock.now())
    assert await run_purge_sessions(db_sessionmaker, fake_clock, batch=SMALL_BATCH) == counts["doomed"]


def test_schedule_is_registered() -> None:
    """Lịch nằm trong sổ của `packages.messaging` để beat của worker đọc được."""
    entries = {entry.name: entry for entry in schedule_entries()}
    assert entries[TASK_NAME].every == EVERY
    assert entries[TASK_NAME].function == "purge_sessions"


async def _on_fresh_engine[ResultT](db_url: str, work: Callable[[AsyncSession], Awaitable[ResultT]]) -> ResultT:
    """Chạy `work` trên engine riêng của vòng `asyncio.run` hiện tại (test khói là test đồng bộ)."""
    engine = create_engine(DatabaseSettings(database_url=db_url, db_connect_timeout_s=int(GATE_CONNECT_TIMEOUT_S)))
    try:
        async with create_sessionmaker(engine)() as session:
            return await work(session)
    finally:
        await engine.dispose()


def test_purge_sessions_smoke(db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test khói: gọi chính hàm lịch (giờ thật, `worker_sessionmaker()`) và khẳng định lõi đã xoá."""
    counts = asyncio.run(_on_fresh_engine(db_url, lambda session: _seed(session, SystemClock().now())))
    monkeypatch.setenv("DATABASE_URL", db_url)
    reset_database_settings_cache()
    try:
        purge_sessions()
    finally:
        reset_database_settings_cache()
    assert asyncio.run(_on_fresh_engine(db_url, _count_on)) == counts["kept"]
