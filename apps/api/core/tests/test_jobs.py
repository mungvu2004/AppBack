"""Lịch dọn bản ghi idempotency hết hạn (BE-00 §7 "Dọn rác", J01, J06)."""

from datetime import datetime, timedelta
from typing import Final
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.core.jobs import BATCH, EVERY, TASK_NAME, purge_expired_idempotency, run_purge_expired_idempotency
from packages.db.models.idempotency import STATE_COMPLETED, IdempotencyRecord
from packages.db.settings import reset_database_settings_cache
from packages.messaging.schedules import schedule_entries
from packages.testing.fixtures.clock import FakeClock

SMALL_BATCH: Final = 2


def _record(now: datetime, key: str, *, expires_at: datetime) -> IdempotencyRecord:
    """Một dòng `completed` đã xong, chỉ khác nhau ở hạn xoá."""
    return IdempotencyRecord(
        user_id="usr_01JABCDEFGHJKMNPQRSTVWXYZ0",
        method="POST",
        route_template="/api/sample/items",
        key=key,
        request_hash="0" * 64,
        state=STATE_COMPLETED,
        claim_token=uuid4(),
        lease_until=now,
        status_code=200,
        content_type="application/json",
        response_body=b"{}",
        expires_at=expires_at,
    )


async def _seed(maker: async_sessionmaker[AsyncSession], now: datetime, live: int, expired: int) -> None:
    async with maker() as session:
        for index in range(live):
            session.add(_record(now, f"con-han-{index:03d}", expires_at=now + timedelta(hours=1)))
        for index in range(expired):
            session.add(_record(now, f"het-han-{index:03d}", expires_at=now - timedelta(seconds=1)))
        await session.commit()


async def _count(maker: async_sessionmaker[AsyncSession]) -> int:
    async with maker() as session:
        return int((await session.execute(select(func.count()).select_from(IdempotencyRecord))).scalar_one())


async def test_purge_expired_idempotency__J01(
    db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Chạy đúng: xoá dòng quá hạn, giữ nguyên dòng còn hạn."""
    now = fake_clock.now()
    await _seed(db_sessionmaker, now, live=2, expired=3)
    assert await run_purge_expired_idempotency(db_sessionmaker, fake_clock) == 3
    assert await _count(db_sessionmaker) == 2


async def test_purge_expired_idempotency__J06(
    db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Giao lặp: lượt thứ hai không xoá gì thêm và không hỏng (idempotent)."""
    now = fake_clock.now()
    await _seed(db_sessionmaker, now, live=1, expired=2)
    assert await run_purge_expired_idempotency(db_sessionmaker, fake_clock) == 2
    assert await run_purge_expired_idempotency(db_sessionmaker, fake_clock) == 0
    assert await _count(db_sessionmaker) == 1


async def test_purge_runs_in_batches(db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock) -> None:
    """Lô nhỏ hơn số dòng quá hạn: vòng lặp phải chạy tiếp cho tới hết."""
    now = fake_clock.now()
    await _seed(db_sessionmaker, now, live=0, expired=SMALL_BATCH + 1)
    assert await run_purge_expired_idempotency(db_sessionmaker, fake_clock, batch=SMALL_BATCH) == SMALL_BATCH + 1
    assert await _count(db_sessionmaker) == 0


def test_schedule_is_registered() -> None:
    """Lịch vào sổ của `packages.messaging` để beat của worker đọc được."""
    entries = {entry.name: entry for entry in schedule_entries()}
    assert entries[TASK_NAME].every == EVERY
    assert entries[TASK_NAME].function == "purge_expired_idempotency"
    assert BATCH > 0


def test_purge_expired_idempotency_smoke(db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test khói: gọi chính hàm lịch với biến môi trường của tài nguyên nó tự dựng."""
    monkeypatch.setenv("DATABASE_URL", db_url)
    reset_database_settings_cache()
    try:
        purge_expired_idempotency()
    finally:
        reset_database_settings_cache()
