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
from packages.messaging.payloads.lighting_bake import LIGHTING_BAKE_INPUT
from packages.messaging.redis import SyncRedis
from packages.storage.keys import lighting_bake_object, lighting_bake_prefix
from packages.storage.local import LocalDiskStorage
from packages.storage.settings import reset_storage_settings_cache
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


async def _put_input(storage: LocalDiskStorage, project_id: str, bake_id: str) -> None:
    """Một `input.glb` nhỏ dưới tiền tố của lượt."""
    key = lighting_bake_object(project_id, bake_id, LIGHTING_BAKE_INPUT)
    await storage.put(key, b"glTF", content_type="model/gltf-binary", max_bytes=4)


async def _objects(storage: LocalDiskStorage, project_id: str, bake_id: str) -> list[str]:
    """Khoá object còn dưới tiền tố của lượt."""
    return [info.key async for info in storage.list_prefix(lighting_bake_prefix(project_id, bake_id))]


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
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    bake_broker: SyncRedis,
) -> None:
    """Gửi lại `queued` quá 10 phút; chốt `STALLED` `queued` quá 6 giờ và `running` quá 70 phút;
    object của lượt bị chốt bị xoá, của lượt còn chạy giữ nguyên.
    """
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
    for bake, project_id in ((old_queued, projects[2]), (old_running, projects[3]), (young_running, projects[4])):
        await _put_input(local_storage, project_id, bake.id)

    result = await run_lighting_bake_sweep(db_sessionmaker, local_storage, fake_clock)

    assert (result.failed, result.resent) == (2, 1)
    assert [p["bake_id"] for p in queued_payloads(bake_broker, BAKE_QUEUE)] == [resend.id]
    for bake in (old_queued, old_running):
        row = await _row(db_session, bake.id)
        assert (row["status"], row["failure_code"]) == ("failed", state.LIGHTING_BAKE_STALLED)
    assert (await _row(db_session, resend.id))["updated_at"] == now
    assert (await _row(db_session, fresh.id))["status"] == "queued"
    assert (await _row(db_session, young_running.id))["status"] == "running"
    assert await _objects(local_storage, projects[2], old_queued.id) == []
    assert await _objects(local_storage, projects[3], old_running.id) == []
    assert len(await _objects(local_storage, projects[4], young_running.id)) == 1


async def test_sweep_lighting_bakes__J06(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    bake_broker: SyncRedis,
) -> None:
    """Hai lượt quét liền nhau: lượt hai không gửi lặp, không chốt lặp (`updated_at` đã đẩy lên)."""
    now = fake_clock.now()
    project_id = await _project_id(db_session)
    await make_lighting_bake(db_session, project_id=project_id, created_at=now - timedelta(minutes=20))

    first = await run_lighting_bake_sweep(db_sessionmaker, local_storage, fake_clock)
    second = await run_lighting_bake_sweep(db_sessionmaker, local_storage, fake_clock)

    assert (first.resent, second.resent, second.failed) == (1, 0, 0)
    assert len(queued_payloads(bake_broker, BAKE_QUEUE)) == 1


async def test_sweep_spares_a_retry_whose_first_attempt_is_old(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    bake_broker: SyncRedis,
) -> None:
    """Lần thử đầu nhận 60 phút trước (OOM), lần thử lại nhận lúc này: 30 phút sau lịch quét không chốt.

    Trần 70 phút đo từ lần nhận gần nhất; trước đây `started_at` giữ lần đầu nên lượt bị chốt ở phút 90.
    """
    now = fake_clock.now()
    project_id = await _project_id(db_session)
    bake = await make_lighting_bake(
        db_session, project_id=project_id, status="running", created_at=now - timedelta(minutes=60)
    )
    assert await state.claim(db_session, bake.id, fake_clock) == project_id
    await db_session.commit()

    fake_clock.advance(timedelta(minutes=30))
    result = await run_lighting_bake_sweep(db_sessionmaker, local_storage, fake_clock)

    assert result.failed == 0
    row = await _row(db_session, bake.id)
    assert (row["status"], row["started_at"]) == ("running", now)


@pytest.fixture
def process_env(db_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, storage_env: None) -> Iterator[None]:
    """Môi trường của tiến trình beat: DB test riêng, kho local `tmp_path` (broker đã do `messaging_env` đặt)."""
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_LOCAL_ROOT", str(tmp_path / "objects"))
    caches = (
        reset_settings_cache,
        reset_database_settings_cache,
        reset_lighting_bake_settings_cache,
        reset_storage_settings_cache,
    )
    for reset in caches:
        reset()
    yield
    for reset in caches:
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
