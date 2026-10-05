"""Hai lịch nền `default.notifications.*` (B4-02 [6] "Lịch", [8]): J01, J06 của từng hàm lịch và test khói."""

from datetime import timedelta
from typing import Any, Final

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.notifications.jobs import (
    PUBLISH_EVERY,
    PUBLISH_TASK,
    TRIM_EVERY,
    TRIM_TASK,
    publish_unsent_notifications,
    run_notification_publish,
    run_notification_trim,
    trim_notifications,
)
from apps.api.notifications.service import dedupe_scope
from apps.api.notifications.settings import get_notifications_settings, reset_notifications_settings_cache
from apps.api.notifications.tests.support import (
    on_fresh_engine,
    remove_member,
    rows_of,
    run,
    seed_project,
    stream_ids,
)
from packages.core.clock import SystemClock
from packages.db.models.auth import User
from packages.db.models.notifications import NotificationRow
from packages.db.models.projects import Project
from packages.db.settings import reset_database_settings_cache
from packages.messaging.redis import AsyncRedis
from packages.messaging.schedules import schedule_entries
from packages.messaging.settings import reset_messaging_settings_cache
from packages.messaging.streams import EventBus, user_stream
from packages.testing.factories.auth import make_user
from packages.testing.factories.notifications import make_notification
from packages.testing.fixtures.clock import FakeClock

BATCH: Final = 100
DAY: Final = timedelta(days=1)


async def _pair(db: AsyncSession) -> tuple[User, Project]:
    """(người nhận, dự án chứa họ)."""
    user = await make_user(db)
    return user, await seed_project(db, owner=user)


# ---------------------------------------------------------------------------
# publish_unsent_notifications
# ---------------------------------------------------------------------------


async def test_publish_unsent_notifications__J01(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
    streams_client: AsyncRedis,
    event_bus: EventBus,
) -> None:
    """Dòng chưa phát trong cửa sổ được phát và ghi `stream_id`; dòng còn quá mới hay đã quá cũ thì không."""
    user, project = await _pair(db_session)
    now = fake_clock.now()
    fresh = await make_notification(
        db_session, user=user, project=project, stream_id=None, created_at=now - timedelta(seconds=30)
    )
    due = await make_notification(
        db_session, user=user, project=project, stream_id=None, created_at=now - timedelta(minutes=5)
    )
    stale = await make_notification(
        db_session, user=user, project=project, stream_id=None, created_at=now - timedelta(hours=13)
    )
    sent = await make_notification(
        db_session, user=user, project=project, stream_id="0-1", created_at=now - timedelta(minutes=5)
    )
    await db_session.commit()

    published = await run_notification_publish(db_sessionmaker, event_bus, fake_clock, batch=BATCH)

    assert published == 1
    by_id = {row.id: row.stream_id for row in await rows_of(db_session, user.id)}
    assert await stream_ids(streams_client, user_stream(user.id)) == [by_id[due.id]]
    assert (by_id[fresh.id], by_id[stale.id], by_id[sent.id]) == (None, None, "0-1")


async def test_publish_unsent_notifications__J06(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
    streams_client: AsyncRedis,
    event_bus: EventBus,
) -> None:
    """Chạy lại: không XADD thêm; dòng đã được phát sẵn (khoá khử trùng còn) nhận lại id cũ, không mục thứ hai."""
    user, project = await _pair(db_session)
    now = fake_clock.now()
    rows = [
        await make_notification(
            db_session, user=user, project=project, stream_id=None, created_at=now - timedelta(minutes=5 + n)
        )
        for n in range(2)
    ]
    await db_session.commit()
    already = rows[0]
    prior_id = await event_bus.publish_once(
        user_stream(user.id), dedupe_scope(already.dedupe_key), {"id": already.id}, ttl_s=60
    )

    assert await run_notification_publish(db_sessionmaker, event_bus, fake_clock, batch=BATCH) == 2
    assert await run_notification_publish(db_sessionmaker, event_bus, fake_clock, batch=BATCH) == 0

    assert await streams_client.xlen(user_stream(user.id)) == 2
    assert (await rows_of(db_session, user.id))[1].stream_id == prior_id  # rows[0] có `created_at` mới hơn rows[1]


async def test_publish_unsent_notifications__batch_limit(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
    streams_client: AsyncRedis,
    event_bus: EventBus,
) -> None:
    """`batch=1` chỉ phát dòng cũ nhất; lượt sau phát dòng kế."""
    user, project = await _pair(db_session)
    now = fake_clock.now()
    for n in range(2):
        await make_notification(
            db_session, user=user, project=project, stream_id=None, created_at=now - timedelta(minutes=5 + n)
        )
    await db_session.commit()
    assert await run_notification_publish(db_sessionmaker, event_bus, fake_clock, batch=1) == 1
    assert await streams_client.xlen(user_stream(user.id)) == 1
    assert await run_notification_publish(db_sessionmaker, event_bus, fake_clock, batch=1) == 1
    assert await streams_client.xlen(user_stream(user.id)) == 2


# ---------------------------------------------------------------------------
# trim_notifications
# ---------------------------------------------------------------------------


async def test_trim_notifications__J01(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """205 dòng → còn 200 mới nhất; dòng ẩn cũ 31 ngày xoá trước, dòng ẩn 29 ngày còn; người khác không bị đụng."""
    now = fake_clock.now()
    keeper, other, owner = await make_user(db_session), await make_user(db_session), await make_user(db_session)
    visible = await seed_project(db_session, owner=owner, members=[keeper])
    left = await seed_project(db_session, owner=owner, members=[keeper])
    deleted = await seed_project(db_session, owner=owner, members=[keeper], deleted_at=now)
    shared = await seed_project(db_session, owner=other)
    minutes = [
        await make_notification(db_session, user=keeper, project=visible, created_at=now - timedelta(minutes=n))
        for n in range(205)
    ]
    hidden_old = await make_notification(db_session, user=keeper, project=left, created_at=now - 31 * DAY)
    hidden_new = await make_notification(db_session, user=keeper, project=left, created_at=now - 29 * DAY)
    deleted_old = await make_notification(db_session, user=keeper, project=deleted, created_at=now - 31 * DAY)
    untouched = [
        await make_notification(db_session, user=other, project=shared, created_at=now - n * DAY) for n in range(3)
    ]
    await db_session.commit()
    await remove_member(db_session, left, keeper)

    removed = await run_notification_trim(db_sessionmaker, fake_clock, batch=2)

    # Bước 1: `hidden_old`, `deleted_old` (ẩn, > 30 ngày). Bước 2: còn 206 dòng (205 + `hidden_new`), bỏ 6 cũ nhất.
    assert removed == 2 + 6
    assert {row.id for row in await rows_of(db_session, keeper.id)} == {row.id for row in minutes[:200]}
    remaining = {row.id for row in await rows_of(db_session)}
    assert {hidden_old.id, hidden_new.id, deleted_old.id}.isdisjoint(remaining)
    assert {row.id for row in await rows_of(db_session, other.id)} == {row.id for row in untouched}


async def test_trim_notifications__J01_hidden_age(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Dòng ẩn (người nhận bị gỡ) cũ 31 ngày bị xoá, cũ 29 ngày còn — không có gì khác để xoá."""
    now = fake_clock.now()
    user, project = await _pair(db_session)
    owner = await make_user(db_session)
    gone = await seed_project(db_session, owner=owner, members=[user])
    old = await make_notification(db_session, user=user, project=gone, created_at=now - 31 * DAY)
    recent = await make_notification(db_session, user=user, project=gone, created_at=now - 29 * DAY)
    live = await make_notification(db_session, user=user, project=project, created_at=now - 60 * DAY)
    await db_session.commit()
    await remove_member(db_session, gone, user)

    assert await run_notification_trim(db_sessionmaker, fake_clock, batch=BATCH) == 1

    assert {row.id for row in await rows_of(db_session, user.id)} == {recent.id, live.id}
    assert old.id not in {row.id for row in await rows_of(db_session)}


async def test_trim_notifications__J06(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Chạy lại không xoá thêm; theo lô nhỏ (`batch=2`) cũng đúng tổng."""
    now = fake_clock.now()
    user, project = await _pair(db_session)
    for n in range(205):
        await make_notification(db_session, user=user, project=project, created_at=now - timedelta(minutes=n))
    await db_session.commit()

    assert await run_notification_trim(db_sessionmaker, fake_clock, batch=2) == 5
    assert await run_notification_trim(db_sessionmaker, fake_clock, batch=2) == 0
    count = (await db_session.execute(select(func.count()).select_from(NotificationRow))).scalar_one()
    assert count == get_notifications_settings().notifications_keep_max


# ---------------------------------------------------------------------------
# Sổ lịch và test khói
# ---------------------------------------------------------------------------


def test_schedules_are_registered() -> None:
    """Hai lịch nằm trong sổ của `packages.messaging` với đúng chu kỳ và tên hàm."""
    entries = {entry.name: entry for entry in schedule_entries()}
    assert (entries[PUBLISH_TASK].every, entries[PUBLISH_TASK].function) == (
        PUBLISH_EVERY,
        "publish_unsent_notifications",
    )
    assert (entries[TRIM_TASK].every, entries[TRIM_TASK].function) == (TRIM_EVERY, "trim_notifications")


def test_publish_unsent_notifications_smoke(
    db_url: str, redis_broker_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test khói: gọi chính hàm lịch (giờ thật, `worker_sessionmaker()`, `streams_redis()`), lõi phải đã phát."""
    clock = SystemClock()

    async def seed(session: AsyncSession) -> str:
        """Một dòng chưa phát, tuổi 3 phút; trả id thông báo."""
        user, project = await _pair(session)
        row = await make_notification(
            session, user=user, project=project, stream_id=None, created_at=clock.now() - timedelta(minutes=3)
        )
        await session.commit()
        return row.id

    async def read(session: AsyncSession, notification_id: str) -> str | None:
        """`stream_id` hiện tại của dòng."""
        return (
            await session.execute(select(NotificationRow.stream_id).where(NotificationRow.id == notification_id))
        ).scalar_one()

    notification_id = run(on_fresh_engine(db_url, seed))
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("REDIS_BROKER_URL", redis_broker_url)
    reset_database_settings_cache()
    reset_messaging_settings_cache()
    try:
        publish_unsent_notifications()
    finally:
        reset_database_settings_cache()
        reset_messaging_settings_cache()
    assert run(on_fresh_engine(db_url, lambda session: read(session, notification_id))) is not None


def test_trim_notifications_smoke(db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test khói: `trim_notifications()` với `KEEP_MAX=2` xoá dòng thứ ba (giờ thật, `worker_sessionmaker()`)."""
    clock = SystemClock()

    async def seed(session: AsyncSession) -> str:
        """Ba dòng của một người; trả id người nhận."""
        user, project = await _pair(session)
        for n in range(3):
            await make_notification(session, user=user, project=project, created_at=clock.now() - timedelta(minutes=n))
        await session.commit()
        return user.id

    async def count(session: AsyncSession, user_id: str) -> int:
        """Số dòng còn lại của người nhận."""
        stmt = select(func.count()).select_from(NotificationRow).where(NotificationRow.user_id == user_id)
        return int((await session.execute(stmt)).scalar_one())

    user_id = run(on_fresh_engine(db_url, seed))
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("NOTIFICATIONS_KEEP_MAX", "2")
    reset_database_settings_cache()
    reset_notifications_settings_cache()
    try:
        trim_notifications()
    finally:
        reset_database_settings_cache()
        reset_notifications_settings_cache()
    assert run(on_fresh_engine(db_url, lambda session: count(session, user_id))) == 2


async def test_run_notification_trim__overflow_ranks_only_over_cap_users(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """NO-253 (2): bước giữ `KEEP_MAX` chỉ xếp hạng người vượt trần (`HAVING count(*) > KEEP_MAX`), không cả bảng."""
    user, project = await _pair(db_session)
    await make_notification(db_session, user=user, project=project, created_at=fake_clock.now())
    await db_session.commit()
    seen: list[str] = []

    def capture(_conn: Any, _cursor: Any, statement: str, *_rest: Any) -> None:
        """Ghi lại câu SQL có `row_number` (bước xếp hạng)."""
        if "row_number" in statement:
            seen.append(statement)

    engine = db_sessionmaker.kw["bind"].sync_engine
    event.listen(engine, "before_cursor_execute", capture)
    try:
        await run_notification_trim(db_sessionmaker, fake_clock, batch=BATCH)
    finally:
        event.remove(engine, "before_cursor_execute", capture)

    assert seen
    assert all("HAVING" in statement for statement in seen)
