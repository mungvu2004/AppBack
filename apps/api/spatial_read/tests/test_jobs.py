"""Lịch đối chiếu `default.spatial_read.reconcile_counts` trên Postgres thật (B3-02 [8], J01, J06)."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.projects.summaries import project_rollups
from apps.api.spatial_read.jobs import EVERY, TASK_NAME, reconcile_floor_counts, run_count_reconcile
from apps.api.spatial_read.tests._helpers import Scene, make_scene
from packages.db.engine import GATE_CONNECT_TIMEOUT_S, create_engine, create_sessionmaker
from packages.db.models.floors import FloorRow
from packages.db.models.projects import ProjectFloorSummary
from packages.db.settings import DatabaseSettings, reset_database_settings_cache
from packages.messaging.schedules import schedule_entries
from packages.testing.factories.spatial import make_floor_document, sample_floor_layer
from packages.testing.fixtures.clock import FakeClock

LEVEL_1_WALLS = 12
LEVEL_1_AREA_M2 = Decimal("68.00")


async def _scene_with_document(db: AsyncSession, clock: FakeClock, *, floors: int = 1) -> Scene:
    """`floors` tầng đã commit, mỗi tầng có tài liệu mẫu 12 tường nhưng dòng đếm còn ở 0."""
    scene = await make_scene(db, floors=floors)
    for index, floor in enumerate(scene.floors):
        layer = sample_floor_layer(0, level_id=floor.level_id, id_suffix=f"Z{index}")
        await make_floor_document(db, floor_pk=floor.pk, layer=layer, clock=clock)
    await db.commit()
    return scene


async def _counts(
    sessionmaker: async_sessionmaker[AsyncSession], project_id: str
) -> list[tuple[int, int, Decimal | None]]:
    """Ba số đếm của mọi tầng dự án, đọc trên session mới (K22), theo thứ tự tầng."""
    async with sessionmaker() as session:
        stmt = (
            select(ProjectFloorSummary.walls_total, ProjectFloorSummary.walls_reviewed, ProjectFloorSummary.area_m2)
            .where(ProjectFloorSummary.project_id == project_id)
            .order_by(ProjectFloorSummary.floor_order)
        )
        return [(total, reviewed, area) for total, reviewed, area in (await session.execute(stmt)).all()]


async def test_reconcile_floor_counts__J01(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Bảng đếm ở 0 mà tài liệu có 12 tường, 4 phòng → sau một lượt số đúng và `project_rollups` khớp."""
    scene = await _scene_with_document(db_session, fake_clock)

    written = await run_count_reconcile(db_sessionmaker, fake_clock, batch=10)

    assert written == 1
    assert await _counts(db_sessionmaker, scene.project.id) == [(LEVEL_1_WALLS, 0, LEVEL_1_AREA_M2)]
    async with db_sessionmaker() as session:
        rollup = (await project_rollups(session, [scene.project.id]))[scene.project.id]
    assert (rollup.walls_total, rollup.area_m2) == (LEVEL_1_WALLS, LEVEL_1_AREA_M2)


async def test_reconcile_floor_counts__J06(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Hai lượt như một: lượt hai không ghi gì và số đếm không đổi."""
    scene = await _scene_with_document(db_session, fake_clock)

    assert await run_count_reconcile(db_sessionmaker, fake_clock, batch=10) == 1
    first = await _counts(db_sessionmaker, scene.project.id)
    assert await run_count_reconcile(db_sessionmaker, fake_clock, batch=10) == 0
    assert await _counts(db_sessionmaker, scene.project.id) == first


async def test_reconcile_batches_until_exhausted(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Lô nhỏ hơn số tầng: keyset đi hết mọi lô, không dừng ở lô đầu."""
    scene = await _scene_with_document(db_session, fake_clock, floors=5)

    assert await run_count_reconcile(db_sessionmaker, fake_clock, batch=2) == 5
    assert await _counts(db_sessionmaker, scene.project.id) == [(LEVEL_1_WALLS, 0, LEVEL_1_AREA_M2)] * 5


async def test_floor_outside_the_window_is_not_read(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """`floors.updated_at` cũ hơn cửa sổ nhìn lại → tầng không được đếm, dòng đếm giữ nguyên."""
    scene = await _scene_with_document(db_session, fake_clock)
    fake_clock.set(datetime.now(UTC) + timedelta(hours=1))

    assert await run_count_reconcile(db_sessionmaker, fake_clock, batch=10) == 0
    assert await _counts(db_sessionmaker, scene.project.id) == [(0, 0, None)]


async def test_soft_deleted_floor_is_skipped(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Tầng đã xoá mềm không được chọn: dòng đếm giữ số cũ cho lượt khôi phục."""
    scene = await _scene_with_document(db_session, fake_clock)
    await db_session.execute(
        update(FloorRow).where(FloorRow.pk == scene.floors[0].pk).values(deleted_at=fake_clock.now())
    )
    await db_session.commit()

    assert await run_count_reconcile(db_sessionmaker, fake_clock, batch=10) == 0
    assert await _counts(db_sessionmaker, scene.project.id) == [(0, 0, None)]


def test_schedule_is_registered() -> None:
    """Lịch nằm trong sổ của `packages.messaging` để beat của worker đọc được."""
    entries = {entry.name: entry for entry in schedule_entries()}
    assert entries[TASK_NAME].every == EVERY
    assert entries[TASK_NAME].function == "reconcile_floor_counts"


def test_reconcile_floor_counts_smoke(db_url: str, monkeypatch: pytest.MonkeyPatch, fake_clock: FakeClock) -> None:
    """Test khói: gọi chính hàm lịch (giờ thật, `worker_sessionmaker()`), bảng đếm về đúng."""
    settings = DatabaseSettings(database_url=db_url, db_connect_timeout_s=int(GATE_CONNECT_TIMEOUT_S))

    async def _with_maker[T](work: Callable[[async_sessionmaker[AsyncSession]], Awaitable[T]]) -> T:
        """Một vòng sự kiện, một engine riêng: pool không được dùng lại giữa hai `asyncio.run`."""
        engine = create_engine(settings)
        try:
            return await work(create_sessionmaker(engine))
        finally:
            await engine.dispose()

    async def _seed(maker: async_sessionmaker[AsyncSession]) -> str:
        """Một tầng có tài liệu mà dòng đếm còn 0; trả `project_id`."""
        async with maker() as session:
            return (await _scene_with_document(session, fake_clock)).project.id

    project_id = asyncio.run(_with_maker(_seed))
    monkeypatch.setenv("DATABASE_URL", db_url)
    reset_database_settings_cache()
    try:
        reconcile_floor_counts()
    finally:
        reset_database_settings_cache()
    counts = asyncio.run(_with_maker(lambda maker: _counts(maker, project_id)))
    assert counts == [(LEVEL_1_WALLS, 0, LEVEL_1_AREA_M2)]
