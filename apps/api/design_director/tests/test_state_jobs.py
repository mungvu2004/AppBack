"""`state.*`, `enqueue_auto`, `compute_input_key` và lịch `sweep_design_concepts` (J01, J06) trên Postgres thật."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Final

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.design_director import state
from apps.api.design_director.jobs import run_design_concept_sweep
from packages.db.hooks import after_commit_idle
from packages.db.models.projects import Project
from packages.messaging.redis import SyncRedis, broker_redis_sync
from packages.testing.factories.auth import make_user
from packages.testing.factories.design_concept import make_design_concept
from packages.testing.factories.floors import make_floor
from packages.testing.factories.projects import make_project
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.design_director import TEST_QUOTA
from packages.testing.fixtures.messaging import queued_payloads

QUEUE: Final = "default"


@pytest.fixture
def broker(messaging_env: None) -> Iterator[SyncRedis]:
    """Broker thật với hàng `default` rỗng ở đầu và cuối test."""
    client = broker_redis_sync()
    client.delete(QUEUE)
    try:
        yield client
    finally:
        client.delete(QUEUE)
        client.close()


def _tasks(broker: SyncRedis) -> list[object]:
    """Id concept của mọi task `design.director.run` đang chờ."""
    return [p["concept_id"] for p in queued_payloads(broker, QUEUE) if "concept_id" in p]


async def _project(db: AsyncSession) -> Project:
    """Một dự án mới đã commit."""
    project = await make_project(db, owner=await make_user(db))
    await db.commit()
    return project


async def _project_id(db: AsyncSession) -> str:
    """Id một dự án mới đã commit."""
    return (await _project(db)).id


async def _row(db: AsyncSession, concept_id: str) -> dict[str, object]:
    """Dòng `design_concepts` đọc lại."""
    found = await db.execute(text("SELECT * FROM design_concepts WHERE id = :id"), {"id": concept_id})
    return dict(found.mappings().one())


async def test_claim_finish_moves_queued_to_done(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """`claim` trả đầu vào và đặt `running`; `finish` ghi `result`/`usage`/`style_id`; gọi lại là no-op."""
    project_id = await _project_id(db_session)
    concept = await make_design_concept(db_session, project_id=project_id, suggested=True, input_key="k1")

    claimed = await state.claim(db_session, concept.id, clock=fake_clock)
    assert claimed == state.ConceptInput(project_id=project_id, style_id=None, suggested=True, input_key="k1")
    assert await state.finish(
        db_session, concept.id, result={"nameVi": "Gỗ"}, usage={"calls": 2}, style_id="rustic", clock=fake_clock
    )
    assert not await state.finish(db_session, concept.id, result={}, usage={}, style_id="rustic", clock=fake_clock)
    assert await state.claim(db_session, concept.id, clock=fake_clock) is None
    row = await _row(db_session, concept.id)
    assert (row["status"], row["style_id"], row["result"], row["usage"]) == (
        "done",
        "rustic",
        {"nameVi": "Gỗ"},
        {"calls": 2},
    )
    assert row["started_at"] == row["ended_at"] == fake_clock.now()


async def test_fail_sets_code_once_and_rejects_bad_input(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """`fail` chốt mã một lần; mã ngoài `DESIGN_DIRECTOR_*` hay kiểu lạ → `ValueError`."""
    project_id = await _project_id(db_session)
    concept = await make_design_concept(db_session, project_id=project_id, status="running")

    assert await state.fail(db_session, concept.id, state.DESIGN_DIRECTOR_OUTPUT_INVALID, clock=fake_clock)
    assert not await state.fail(db_session, concept.id, state.DESIGN_DIRECTOR_FAILED, clock=fake_clock)
    assert (await _row(db_session, concept.id))["failure_code"] == state.DESIGN_DIRECTOR_OUTPUT_INVALID
    with pytest.raises(ValueError, match="mã hỏng"):
        await state.fail(db_session, concept.id, "OOPS", clock=fake_clock)
    with pytest.raises(ValueError, match="phong cách"):
        await state.finish(db_session, concept.id, result={}, usage={}, style_id="baroque")


async def test_unique_partial_index_blocks_a_second_active_concept_with_the_same_key(db_session: AsyncSession) -> None:
    """Hai lượt `queued|running` cùng (dự án, khoá) → DB chặn; lượt `done` cùng khoá thì không."""
    project_id = await _project_id(db_session)
    await make_design_concept(db_session, project_id=project_id, input_key="same")
    await make_design_concept(db_session, project_id=project_id, input_key="same", status="done")
    with pytest.raises(IntegrityError):
        await make_design_concept(db_session, project_id=project_id, input_key="same", status="running")
    await db_session.rollback()


async def test_compute_input_key_follows_style_floors_and_library(db_session: AsyncSession) -> None:
    """Khoá đổi theo kiểu và khi thêm tầng; gọi lại cùng đầu vào → cùng khoá."""
    project = await _project(db_session)
    project_id = project.id
    auto = await state.compute_input_key(db_session, project_id, None)
    assert auto == await state.compute_input_key(db_session, project_id, None)
    assert auto != await state.compute_input_key(db_session, project_id, "japandi")
    await make_floor(db_session, project=project)
    await db_session.commit()
    assert auto != await state.compute_input_key(db_session, project_id, None)


async def test_enqueue_auto_queues_once_and_skips_when_not_allowed(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
    broker: SyncRedis,
    fake_clock: FakeClock,
    design_director_on: None,
) -> None:
    """Lượt đầu xếp `queued` đề xuất (đã chọn) + task sau commit; lần hai cùng khoá bỏ qua."""
    project_id = await _project_id(db_session)

    async with db_sessionmaker() as db:
        first = await state.enqueue_auto(db, project_id, clock=fake_clock)
        await db.commit()
        await after_commit_idle(db)
    async with db_sessionmaker() as db:
        second = await state.enqueue_auto(db, project_id, clock=fake_clock)
        await db.commit()

    assert first is not None
    assert second is None
    row = await _row(db_session, first)
    assert (row["suggested"], row["style_id"], row["created_by"], row["status"]) == (True, None, None, "queued")
    assert row["selected_at"] is not None
    assert _tasks(broker) == [first]


async def test_enqueue_auto_keeps_a_user_pick_active_and_respects_quota(
    db_session: AsyncSession, fake_clock: FakeClock, design_director_on: None
) -> None:
    """Người dùng đã tự chọn kiểu → lượt tự chạy không được `selected_at`; hết hạn mức → bỏ qua."""
    project_id = await _project_id(db_session)
    await make_design_concept(db_session, project_id=project_id, status="done", selected_at=fake_clock.now())

    concept_id = await state.enqueue_auto(db_session, project_id, clock=fake_clock)
    await db_session.commit()

    assert concept_id is not None
    assert (await _row(db_session, concept_id))["selected_at"] is None
    other = await _project_id(db_session)
    now = datetime.now(UTC)
    owner_of = text("UPDATE projects SET created_by = (SELECT created_by FROM projects WHERE id = :a) WHERE id = :b")
    await db_session.execute(owner_of, {"a": project_id, "b": other})
    await db_session.commit()
    for _ in range(TEST_QUOTA):
        await make_design_concept(db_session, project_id=project_id, status="failed", created_at=now)
    assert await state.enqueue_auto(db_session, other) is None


async def test_enqueue_auto_skips_when_disabled(db_session: AsyncSession, design_director_off: None) -> None:
    """Thiếu khoá → không chèn gì."""
    project_id = await _project_id(db_session)
    assert await state.enqueue_auto(db_session, project_id) is None


async def test_sweep_design_concepts__J01(
    db_sessionmaker: async_sessionmaker[AsyncSession], db_session: AsyncSession, broker: SyncRedis
) -> None:
    """Chốt `STALLED` lượt queued > 2 h và running > 15 phút; gửi lại lượt queued im > 10 phút; lượt mới để yên."""
    project_id = await _project_id(db_session)
    now = datetime.now(UTC)
    old_queued = await make_design_concept(db_session, project_id=project_id, created_at=now - timedelta(hours=3))
    old_running = await make_design_concept(
        db_session, project_id=project_id, status="running", created_at=now - timedelta(minutes=20)
    )
    quiet = await make_design_concept(db_session, project_id=project_id, created_at=now - timedelta(minutes=11))
    fresh = await make_design_concept(db_session, project_id=project_id, created_at=now)

    result = await run_design_concept_sweep(db_sessionmaker, FakeClock(start=now))

    assert (result.failed, result.resent) == (2, 1)
    for stalled in (old_queued, old_running):
        row = await _row(db_session, stalled.id)
        assert (row["status"], row["failure_code"]) == ("failed", state.DESIGN_DIRECTOR_STALLED)
    assert (await _row(db_session, fresh.id))["status"] == "queued"
    assert _tasks(broker) == [quiet.id]


async def test_sweep_design_concepts__J06(
    db_sessionmaker: async_sessionmaker[AsyncSession], db_session: AsyncSession, broker: SyncRedis
) -> None:
    """Hai lượt quét liền nhau: lượt hai không gửi lặp, không chốt lặp (`updated_at` đã đẩy lên)."""
    project_id = await _project_id(db_session)
    now = datetime.now(UTC)
    quiet = await make_design_concept(db_session, project_id=project_id, created_at=now - timedelta(minutes=11))

    first = await run_design_concept_sweep(db_sessionmaker, FakeClock(start=now))
    second = await run_design_concept_sweep(db_sessionmaker, FakeClock(start=now))

    assert (first.resent, second.resent, second.failed) == (1, 0, 0)
    assert _tasks(broker) == [quiet.id]
    assert (await _row(db_session, quiet.id))["status"] == "queued"
