"""`state.claim/finish/fail` và lịch `sweep_lighting_bakes` (BE-00 §7, J01, J06) trên Postgres thật."""

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.lighting_bake import state
from apps.api.lighting_bake.jobs import run_lighting_bake_sweep, sweep_lighting_bakes
from apps.api.lighting_bake.settings import reset_lighting_bake_settings_cache
from apps.api.lighting_bake.tests._helpers import BAKE_QUEUE
from apps.api.lighting_bake.tests._helpers import bake_broker as bake_broker
from packages.core.settings import reset_settings_cache
from packages.db.engine import create_engine, create_sessionmaker
from packages.db.settings import get_database_settings, reset_database_settings_cache
from packages.messaging.redis import SyncRedis
from packages.testing.factories.auth import make_user
from packages.testing.factories.lighting_bake import make_lighting_bake
from packages.testing.factories.projects import make_project
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.messaging import queued_payloads


async def _project_id(db: AsyncSession) -> str:
    """Một dự án mới đã commit; trả id."""
    project = await make_project(db, owner=await make_user(db))
    await db.commit()
    return project.id


async def _row(db: AsyncSession, bake_id: str) -> dict[str, object]:
    """Dòng `lighting_bakes` đọc lại từ DB dưới dạng dict."""
    found = await db.execute(text("SELECT * FROM lighting_bakes WHERE id = :id"), {"id": bake_id})
    return dict(found.mappings().one())


async def test_claim_finish_moves_queued_to_done(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """`claim` trả project id và đặt `running`; `finish` chốt `done`; gọi lại là no-op."""
    project_id = await _project_id(db_session)
    bake = await make_lighting_bake(db_session, project_id=project_id)

    assert await state.claim(db_session, bake.id, fake_clock) == project_id
    assert await state.claim(db_session, bake.id, fake_clock) == project_id
    assert await state.finish(db_session, bake.id, fake_clock) is True
    assert await state.finish(db_session, bake.id, fake_clock) is False
    assert await state.claim(db_session, bake.id, fake_clock) is None
    row = await _row(db_session, bake.id)
    assert row["status"] == "done"
    assert row["started_at"] is not None
    assert row["ended_at"] is not None


async def test_fail_sets_code_once_and_rejects_unknown_codes(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """`fail` chốt `failed` với mã; lượt đã kết thúc → `False`; mã lạ → `ValueError`."""
    project_id = await _project_id(db_session)
    bake = await make_lighting_bake(db_session, project_id=project_id, status="running")

    assert await state.fail(db_session, bake.id, state.LIGHTING_BAKE_TIMEOUT, fake_clock) is True
    assert await state.fail(db_session, bake.id, state.LIGHTING_BAKE_FAILED, fake_clock) is False
    assert await state.finish(db_session, bake.id, fake_clock) is False
    assert (await _row(db_session, bake.id))["failure_code"] == state.LIGHTING_BAKE_TIMEOUT
    with pytest.raises(ValueError, match="mã hỏng lạ"):
        await state.fail(db_session, bake.id, "NOPE", fake_clock)


async def test_sweep_lighting_bakes__J01(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
    bake_broker: SyncRedis,
) -> None:
    """Gửi lại `queued` quá 10 phút; chốt `STALLED` `queued` quá 6 giờ và `running` quá 70 phút."""
    now = fake_clock.now()
    projects = [await _project_id(db_session) for _ in range(5)]
    resend = await make_lighting_bake(db_session, project_id=projects[0], created_at=now - timedelta(minutes=11))
    fresh = await make_lighting_bake(db_session, project_id=projects[1], created_at=now - timedelta(minutes=2))
    old_queued = await make_lighting_bake(db_session, project_id=projects[2], created_at=now - timedelta(hours=7))
    old_running = await make_lighting_bake(
        db_session, project_id=projects[3], status="running", created_at=now - timedelta(minutes=71)
    )
    young_running = await make_lighting_bake(
        db_session, project_id=projects[4], status="running", created_at=now - timedelta(minutes=30)
    )

    result = await run_lighting_bake_sweep(db_sessionmaker, fake_clock)

    assert (result.failed, result.resent) == (2, 1)
    assert [p["bake_id"] for p in queued_payloads(bake_broker, BAKE_QUEUE)] == [resend.id]
    for bake in (old_queued, old_running):
        row = await _row(db_session, bake.id)
        assert (row["status"], row["failure_code"]) == ("failed", state.LIGHTING_BAKE_STALLED)
    assert (await _row(db_session, resend.id))["updated_at"] == now
    assert (await _row(db_session, fresh.id))["status"] == "queued"
    assert (await _row(db_session, young_running.id))["status"] == "running"


async def test_sweep_lighting_bakes__J06(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
    bake_broker: SyncRedis,
) -> None:
    """Hai lượt quét liền nhau: lượt hai không gửi lặp, không chốt lặp (`updated_at` đã đẩy lên)."""
    now = fake_clock.now()
    project_id = await _project_id(db_session)
    await make_lighting_bake(db_session, project_id=project_id, created_at=now - timedelta(minutes=20))

    first = await run_lighting_bake_sweep(db_sessionmaker, fake_clock)
    second = await run_lighting_bake_sweep(db_sessionmaker, fake_clock)

    assert (first.resent, second.resent, second.failed) == (1, 0, 0)
    assert len(queued_payloads(bake_broker, BAKE_QUEUE)) == 1


@pytest.fixture
def process_env(db_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Môi trường của tiến trình beat: DB test riêng (broker đã do `messaging_env` đặt)."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", db_url)
    for reset in (reset_settings_cache, reset_database_settings_cache, reset_lighting_bake_settings_cache):
        reset()
    yield
    for reset in (reset_settings_cache, reset_database_settings_cache, reset_lighting_bake_settings_cache):
        reset()


async def _seed_old_queued() -> str:
    """Một lượt `queued` tạo một giờ trước, ghi vào DB của môi trường tiến trình; trả id."""
    engine = create_engine(get_database_settings())
    try:
        async with create_sessionmaker(engine)() as db:
            project_id = await _project_id(db)
            an_hour_ago = datetime.now(UTC) - timedelta(hours=1)
            bake = await make_lighting_bake(db, project_id=project_id, created_at=an_hour_ago)
            await db.commit()
            return bake.id
    finally:
        await engine.dispose()


@pytest.mark.usefixtures("process_env", "celery_test_app")
def test_sweep_lighting_bakes_smoke(bake_broker: SyncRedis) -> None:
    """Hàm lịch thật (đồng bộ, như các test khói lịch khác): lượt `queued` cũ được gửi lại lên hàng `bake`."""
    bake_id = asyncio.run(_seed_old_queued())

    sweep_lighting_bakes()
    reset_database_settings_cache()

    assert [p["bake_id"] for p in queued_payloads(bake_broker, BAKE_QUEUE)] == [bake_id]
