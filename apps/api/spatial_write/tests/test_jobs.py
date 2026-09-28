"""Lịch gộp nhật ký `default.spatial_write.compact_change_log` trên Postgres thật (B3-03 [8], J01, J06).

Một tầng, ba trường: `F1` (`thickness_mm`) đổi sáu lượt, mọi lần cách đây 31 ngày, nên năm
dòng đầu có dòng mới hơn cùng khoá và cũ hơn cửa sổ 30 ngày — đúng đối tượng bị gộp; `F2`
(`width_mm` của cửa) chỉ đổi một lần, cũng cũ, nhưng không dòng nào mới hơn → còn nguyên
("dòng cũ duy nhất của một trường"); `F3` (`width_mm` của cửa sổ) đổi một lần trong cửa sổ
30 ngày (giờ thật) → còn nguyên vì chưa đủ cũ, bất kể batch.
"""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.spatial_read.tests._helpers import make_scene
from apps.api.spatial_write.changes import remote_changes_since
from apps.api.spatial_write.jobs import EVERY, TASK_NAME, compact_change_log, run_change_log_compaction
from apps.api.spatial_write.tests._helpers import log_count, log_rows, reread
from packages.db.engine import GATE_CONNECT_TIMEOUT_S, create_engine, create_sessionmaker
from packages.db.settings import DatabaseSettings, reset_database_settings_cache
from packages.domain.spatial import FieldChange
from packages.messaging.schedules import schedule_entries
from packages.testing.factories.auth import make_user
from packages.testing.factories.spatial import make_change_rows, make_floor_document
from packages.testing.fixtures.clock import FakeClock

WALL = "W-WALL0000001"
DOOR = "D-DOOR0000001"
WINDOW = "D-WIND0000001"

_F1_REVISIONS = 6
"""Sáu lượt đổi `thickness_mm`: năm dòng đầu bị gộp, dòng thứ sáu (mới nhất) còn nguyên."""
_DELETED = _F1_REVISIONS - 1


async def _seed_history(db: AsyncSession, clock: FakeClock, *, old: datetime, recent: datetime) -> tuple[int, int]:
    """Tám dòng nhật ký của một tầng (sáu `F1` + một `F2` cũ, một `F3` trong cửa sổ); trả `(floor_pk, revision)`."""
    scene = await make_scene(db)
    floor = scene.floors[0]
    await make_floor_document(db, floor_pk=floor.pk, revision=_F1_REVISIONS + 2, clock=clock)
    writer = await make_user(db, name="Người ghi")
    revision = 0
    clock.set(old)
    for value in range(100, 100 + _F1_REVISIONS * 10, 10):
        revision += 1
        await make_change_rows(
            db,
            floor_pk=floor.pk,
            revision=revision,
            changes=[FieldChange(WALL, "wall", "thickness_mm", value)],
            changed_by=writer.id,
            changed_by_name=writer.name,
            clock=clock,
        )
    revision += 1
    await make_change_rows(
        db,
        floor_pk=floor.pk,
        revision=revision,
        changes=[FieldChange(DOOR, "door", "width_mm", 900)],
        changed_by=writer.id,
        changed_by_name=writer.name,
        clock=clock,
    )
    clock.set(recent)
    revision += 1
    await make_change_rows(
        db,
        floor_pk=floor.pk,
        revision=revision,
        changes=[FieldChange(WINDOW, "window", "width_mm", 1200)],
        changed_by=writer.id,
        changed_by_name=writer.name,
        clock=clock,
    )
    await db.commit()
    return floor.pk, revision


async def _all_bases(
    sessionmaker: async_sessionmaker[AsyncSession], floor_pk: int, revision: int
) -> list[tuple[int, tuple[tuple[object, ...], ...]]]:
    """`remote_changes_since` cho mọi `base` từ 0 tới `revision`, gọn lại để so sánh trước/sau gộp."""
    async with sessionmaker() as session:
        result: list[tuple[int, tuple[tuple[object, ...], ...]]] = []
        for base in range(revision + 1):
            changes = await remote_changes_since(session, floor_pk=floor_pk, base_revision=base, limit=50)
            result.append((base, tuple((c.entity_id, c.field, c.value) for c in changes)))
        return result


async def test_compact_change_log__J01(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Năm dòng cũ có dòng mới hơn bị xoá; dòng cũ duy nhất và dòng trong cửa sổ còn nguyên."""
    now = datetime.now(UTC)
    old, recent = now - timedelta(days=31), now
    floor_pk, revision = await _seed_history(db_session, fake_clock, old=old, recent=recent)
    before_document = await reread(db_session, floor_pk)
    before_changes = await _all_bases(db_sessionmaker, floor_pk, revision)
    print(f"nhật ký trước gộp: {await log_count(db_session, floor_pk)}")

    fake_clock.set(recent)
    deleted = await run_change_log_compaction(db_sessionmaker, fake_clock, batch=100)

    assert deleted == _DELETED
    remaining = await log_rows(db_session, floor_pk)
    print(f"nhật ký sau gộp: {len(remaining)}")
    assert [(row.entity_id, row.field, row.value) for row in remaining] == [
        (WALL, "thickness_mm", 100 + (_F1_REVISIONS - 1) * 10),
        (DOOR, "width_mm", 900),
        (WINDOW, "width_mm", 1200),
    ]
    assert await _all_bases(db_sessionmaker, floor_pk, revision) == before_changes
    after_document = await reread(db_session, floor_pk)
    assert (after_document.revision, after_document.layer) == (before_document.revision, before_document.layer)


async def test_compact_change_log__J06(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Lượt gộp thứ hai không xoá gì thêm; số dòng giữ nguyên."""
    now = datetime.now(UTC)
    old, recent = now - timedelta(days=31), now
    floor_pk, _ = await _seed_history(db_session, fake_clock, old=old, recent=recent)
    fake_clock.set(recent)

    first = await run_change_log_compaction(db_sessionmaker, fake_clock, batch=100)
    first_rows = await log_rows(db_session, floor_pk)
    second = await run_change_log_compaction(db_sessionmaker, fake_clock, batch=100)

    assert (first, second) == (_DELETED, 0)
    assert await log_rows(db_session, floor_pk) == first_rows


async def test_compact_change_log_batches_match_single_pass(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Lô nhỏ (2 dòng mỗi giao dịch) xoá đúng bằng một lô lớn — chỉ khác số vòng lặp."""
    now = datetime.now(UTC)
    old, recent = now - timedelta(days=31), now
    floor_pk, _ = await _seed_history(db_session, fake_clock, old=old, recent=recent)
    fake_clock.set(recent)

    deleted = await run_change_log_compaction(db_sessionmaker, fake_clock, batch=2)

    assert deleted == _DELETED
    remaining = await log_rows(db_session, floor_pk)
    assert [(row.entity_id, row.field) for row in remaining] == [
        (WALL, "thickness_mm"),
        (DOOR, "width_mm"),
        (WINDOW, "width_mm"),
    ]


async def test_compact_change_log_leaves_recent_rows_untouched(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Dòng duy nhất trong cửa sổ (giờ thật) không bao giờ bị gộp, dù batch nhỏ."""
    now = datetime.now(UTC)
    floor_pk, _ = await _seed_history(db_session, fake_clock, old=now - timedelta(days=31), recent=now)
    fake_clock.set(now)

    await run_change_log_compaction(db_sessionmaker, fake_clock, batch=1)

    remaining = await log_rows(db_session, floor_pk)
    assert (WINDOW, "width_mm") in [(row.entity_id, row.field) for row in remaining]


def test_schedule_is_registered() -> None:
    """Lịch nằm trong sổ của `packages.messaging` để beat của worker đọc được."""
    entries = {entry.name: entry for entry in schedule_entries()}
    assert entries[TASK_NAME].every == EVERY
    assert entries[TASK_NAME].function == "compact_change_log"


def test_compact_change_log_smoke(db_url: str, monkeypatch: pytest.MonkeyPatch, fake_clock: FakeClock) -> None:
    """Test khói: gọi chính hàm lịch (giờ thật, `worker_sessionmaker()`), dòng cũ bị gộp."""
    settings = DatabaseSettings(database_url=db_url, db_connect_timeout_s=int(GATE_CONNECT_TIMEOUT_S))

    async def _with_maker[T](work: Callable[[async_sessionmaker[AsyncSession]], Awaitable[T]]) -> T:
        """Một vòng sự kiện, một engine riêng: pool không được dùng lại giữa hai `asyncio.run`."""
        engine = create_engine(settings)
        try:
            return await work(create_sessionmaker(engine))
        finally:
            await engine.dispose()

    async def _seed(maker: async_sessionmaker[AsyncSession]) -> int:
        """Mồi tám dòng nhật ký (sáu dòng cũ hơn cửa sổ) rồi trả `floor_pk` để đếm lại sau."""
        now = datetime.now(UTC)
        async with maker() as session:
            floor_pk, _ = await _seed_history(session, fake_clock, old=now - timedelta(days=31), recent=now)
            return floor_pk

    async def _count(maker: async_sessionmaker[AsyncSession]) -> int:
        """Số dòng nhật ký còn lại, đọc bằng engine riêng — hàm lịch chạy ngoài session test."""
        async with maker() as session:
            return await log_count(session, floor_pk)

    floor_pk = asyncio.run(_with_maker(_seed))
    monkeypatch.setenv("DATABASE_URL", db_url)
    reset_database_settings_cache()
    try:
        compact_change_log()
    finally:
        reset_database_settings_cache()
    assert asyncio.run(_with_maker(_count)) == 3
