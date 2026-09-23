"""Lịch dọn tầng xoá mềm `default.floors.purge_deleted` (B2-03 [6] "Lịch dọn", [8], J01, J06)."""

import asyncio
import logging
import secrets
from contextlib import suppress
from datetime import datetime, timedelta
from pathlib import Path
from typing import Final

import pytest
from minio import Minio
from sqlalchemy import BigInteger, Column, ForeignKey, MetaData, Table, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.floors.jobs import (
    EVERY,
    TASK_NAME,
    _delete_row,
    _select_batch,
    check_floor_fk_cascade,
    purge_deleted_floors,
    run_floor_purge,
)
from apps.api.floors.settings import get_floors_settings
from packages.core.clock import SystemClock
from packages.core.object_keys import project_prefix
from packages.db.base import Base
from packages.db.engine import GATE_CONNECT_TIMEOUT_S, create_engine, create_sessionmaker
from packages.db.models import load_all_models
from packages.db.models.floors import FloorRow
from packages.db.models.projects import ProjectFloorSummary
from packages.db.settings import DatabaseSettings, reset_database_settings_cache
from packages.messaging.schedules import schedule_entries
from packages.storage.local import LocalDiskStorage
from packages.storage.s3 import S3Storage, http_client
from packages.storage.settings import reset_storage_settings_cache
from packages.testing.factories.auth import make_user
from packages.testing.factories.floors import make_floor
from packages.testing.factories.projects import make_project
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.services import ephemeral_minio

DAY: Final = timedelta(days=1)


def _marker_key(project_id: str, level_id: str) -> str:
    """Khoá của một object đánh dấu dưới tiền tố tầng — dùng chung cho mọi tầng cùng `level_id`."""
    return f"{project_prefix(project_id)}floors/{level_id}/marker.bin"


async def _put_marker(storage: LocalDiskStorage, project_id: str, level_id: str) -> None:
    await storage.put(_marker_key(project_id, level_id), b"x", content_type="application/octet-stream", max_bytes=10)


async def _soft_delete(db: AsyncSession, pk: int, deleted_at: datetime | None) -> None:
    """Đặt `deleted_at` bằng `UPDATE` trực tiếp, như factory không có tham số này."""
    await db.execute(update(FloorRow).where(FloorRow.pk == pk).values(deleted_at=deleted_at))
    await db.commit()


async def _row_exists(sessionmaker: async_sessionmaker[AsyncSession], pk: int) -> bool:
    """Dòng `floors` còn tồn tại (kể cả đã xoá mềm), đọc trên session mới (K22)."""
    async with sessionmaker() as session:
        count = await session.scalar(select(func.count()).select_from(FloorRow).where(FloorRow.pk == pk))
        return bool(count)


async def _summary_exists(sessionmaker: async_sessionmaker[AsyncSession], project_id: str, level_id: str) -> bool:
    async with sessionmaker() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(ProjectFloorSummary)
            .where(ProjectFloorSummary.project_id == project_id, ProjectFloorSummary.floor_level_id == level_id)
        )
        return bool(count)


def _cutoff(clock: FakeClock) -> datetime:
    settings = get_floors_settings()
    return clock.now() - timedelta(seconds=settings.floor_restore_window_s, days=settings.floor_purge_after_d)


async def test_purge_deleted_floors__J01(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Tầng xoá mềm 31 ngày (có object) bị xoá cả dòng, object và dòng đếm; tầng 29 ngày còn nguyên."""
    caplog.set_level(logging.INFO, logger="apps.api.floors.jobs")
    user = await make_user(db_session, password=None)
    project = await make_project(db_session, owner=user)
    doomed = await make_floor(db_session, project=project, level_id="L-DOOMED0001")
    kept = await make_floor(db_session, project=project, level_id="L-KEPT000001")
    await db_session.commit()
    now = fake_clock.now()
    await _soft_delete(db_session, doomed.pk, now - 31 * DAY)
    await _soft_delete(db_session, kept.pk, now - 29 * DAY)
    await _put_marker(local_storage, project.id, doomed.level_id)
    await _put_marker(local_storage, project.id, kept.level_id)

    removed = await run_floor_purge(db_sessionmaker, local_storage, fake_clock, batch=10)

    assert removed == 1
    assert not await _row_exists(db_sessionmaker, doomed.pk)
    assert await _row_exists(db_sessionmaker, kept.pk)
    assert await local_storage.stat(_marker_key(project.id, doomed.level_id)) is None
    assert await local_storage.stat(_marker_key(project.id, kept.level_id)) is not None
    assert not await _summary_exists(db_sessionmaker, project.id, doomed.level_id)
    assert await _summary_exists(db_sessionmaker, project.id, kept.level_id)
    record = next(r for r in caplog.records if r.msg == "floor_purge_completed")
    assert record.__dict__["purged"] == 1


async def test_purge_keeps_object_and_summary_when_a_live_floor_shares_the_id(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """Có bản sống trùng `level_id`: dòng cũ (quá hạn) mất, object và dòng đếm giữ nguyên."""
    user = await make_user(db_session, password=None)
    project = await make_project(db_session, owner=user)
    level_id = "L-LIVESIB001"
    old = await make_floor(db_session, project=project, level_id=level_id)
    await db_session.commit()
    await _soft_delete(db_session, old.pk, fake_clock.now() - 31 * DAY)
    live = await make_floor(db_session, project=project, level_id=level_id)
    await db_session.commit()
    await _put_marker(local_storage, project.id, level_id)

    removed = await run_floor_purge(db_sessionmaker, local_storage, fake_clock, batch=10)

    assert removed == 1
    assert not await _row_exists(db_sessionmaker, old.pk)
    assert await _row_exists(db_sessionmaker, live.pk)
    assert await local_storage.stat(_marker_key(project.id, level_id)) is not None
    assert await _summary_exists(db_sessionmaker, project.id, level_id)


async def test_purge_keeps_object_and_summary_when_a_recent_soft_deleted_sibling_shares_the_id(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """Có bản khác cùng `level_id` xoá mềm trong cửa sổ khôi phục: dòng cũ mất, object và dòng đếm giữ."""
    user = await make_user(db_session, password=None)
    project = await make_project(db_session, owner=user)
    level_id = "L-RECENTSIB1"
    old = await make_floor(db_session, project=project, level_id=level_id)
    await db_session.commit()
    await _soft_delete(db_session, old.pk, fake_clock.now() - 31 * DAY)
    recent = await make_floor(db_session, project=project, level_id=level_id)
    await db_session.commit()
    await _soft_delete(db_session, recent.pk, fake_clock.now() - timedelta(seconds=60))
    await _put_marker(local_storage, project.id, level_id)

    removed = await run_floor_purge(db_sessionmaker, local_storage, fake_clock, batch=10)

    assert removed == 1
    assert not await _row_exists(db_sessionmaker, old.pk)
    assert await _row_exists(db_sessionmaker, recent.pk)
    assert await local_storage.stat(_marker_key(project.id, level_id)) is not None
    assert await _summary_exists(db_sessionmaker, project.id, level_id)


async def test_storage_failure_keeps_row_and_logs(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """MinIO dừng giữa lượt dọn: dòng `floors` còn, ghi log `floor_purge_failed` kèm `pk`."""
    caplog.set_level(logging.WARNING, logger="apps.api.floors.jobs")
    user = await make_user(db_session, password=None)
    project = await make_project(db_session, owner=user)
    floor = await make_floor(db_session, project=project, level_id="L-STORAGEERR")
    await db_session.commit()
    await _soft_delete(db_session, floor.pk, fake_clock.now() - 31 * DAY)
    container = ephemeral_minio()
    cfg = container.get_config()
    client = Minio(
        cfg["endpoint"],
        access_key=cfg["access_key"],
        secret_key=cfg["secret_key"],
        secure=False,
        region="us-east-1",
        http_client=http_client(),
    )
    bucket = f"test-{secrets.token_hex(6)}"
    client.make_bucket(bucket)
    storage = S3Storage(client=client, public_client=client, bucket=bucket, clock=fake_clock)
    try:
        container.stop()
        removed = await run_floor_purge(db_sessionmaker, storage, fake_clock, batch=10)
    finally:
        with suppress(Exception):  # đã dừng giữa test: lượt dừng thứ hai ném lỗi
            container.stop()
    assert removed == 0
    assert await _row_exists(db_sessionmaker, floor.pk)
    record = next(r for r in caplog.records if r.msg == "floor_purge_failed")
    assert record.__dict__["pk"] == floor.pk


async def test_purge_deleted_floors__J06(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """Chạy hai lần: lượt thứ hai không lỗi và không xoá thêm gì."""
    user = await make_user(db_session, password=None)
    project = await make_project(db_session, owner=user)
    floor = await make_floor(db_session, project=project, level_id="L-REPEAT0001")
    await db_session.commit()
    await _soft_delete(db_session, floor.pk, fake_clock.now() - 31 * DAY)

    assert await run_floor_purge(db_sessionmaker, local_storage, fake_clock, batch=10) == 1
    assert await run_floor_purge(db_sessionmaker, local_storage, fake_clock, batch=10) == 0
    assert not await _row_exists(db_sessionmaker, floor.pk)


async def test_purge_batches_until_exhausted(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """Lô nhỏ hơn số tầng quá hạn: vòng lặp lo hết mọi lô, không dừng ở lô đầu."""
    user = await make_user(db_session, password=None)
    project = await make_project(db_session, owner=user)
    floors = [await make_floor(db_session, project=project, level_id=f"L-BATCH{i:07d}") for i in range(5)]
    await db_session.commit()
    now = fake_clock.now()
    for floor in floors:
        await db_session.execute(update(FloorRow).where(FloorRow.pk == floor.pk).values(deleted_at=now - 31 * DAY))
    await db_session.commit()

    assert await run_floor_purge(db_sessionmaker, local_storage, fake_clock, batch=2) == 5


async def test_restored_between_select_and_delete_is_not_purged(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Tầng được khôi phục (`deleted_at = NULL`) giữa bước chọn và bước xoá thì không bị xoá."""
    user = await make_user(db_session, password=None)
    project = await make_project(db_session, owner=user)
    floor = await make_floor(db_session, project=project, level_id="L-RESTORED01")
    await db_session.commit()
    await _soft_delete(db_session, floor.pk, fake_clock.now() - 31 * DAY)
    cutoff = _cutoff(fake_clock)
    candidates = await _select_batch(db_sessionmaker, cutoff, 10, None)
    candidate = next(c for c in candidates if c.pk == floor.pk)

    await _soft_delete(db_session, floor.pk, None)  # khôi phục "giữa chừng"

    deleted = await _delete_row(db_sessionmaker, candidate, cutoff)

    assert deleted is False
    assert await _row_exists(db_sessionmaker, floor.pk)


def test_schedule_is_registered() -> None:
    """Lịch nằm trong sổ của `packages.messaging` để beat của worker đọc được."""
    entries = {entry.name: entry for entry in schedule_entries()}
    assert entries[TASK_NAME].every == EVERY
    assert entries[TASK_NAME].function == "purge_deleted_floors"


def test_purge_deleted_floors_smoke(
    db_url: str, tmp_path: Path, storage_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test khói: gọi chính hàm lịch (giờ thật, `worker_sessionmaker()`, kho local thật)."""
    engine = create_engine(DatabaseSettings(database_url=db_url, db_connect_timeout_s=int(GATE_CONNECT_TIMEOUT_S)))
    maker = create_sessionmaker(engine)

    async def _seed() -> int:
        async with maker() as session:
            owner = await make_user(session, password=None)
            project = await make_project(session, owner=owner)
            floor = await make_floor(session, project=project, level_id="L-SMOKE00001")
            await session.commit()
            await session.execute(
                update(FloorRow).where(FloorRow.pk == floor.pk).values(deleted_at=SystemClock().now() - 31 * DAY)
            )
            await session.commit()
            return floor.pk

    floor_pk = asyncio.run(_seed())
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_LOCAL_ROOT", str(tmp_path / "objects"))
    reset_database_settings_cache()
    reset_storage_settings_cache()
    try:
        purge_deleted_floors()
    finally:
        reset_database_settings_cache()
        reset_storage_settings_cache()
        asyncio.run(engine.dispose())
    assert asyncio.run(_row_exists(maker, floor_pk)) is False


def _fake_metadata(*, ondelete: str | None) -> MetaData:
    metadata = MetaData()
    Table("floors", metadata, Column("pk", BigInteger, primary_key=True))
    Table(
        "floor_children",
        metadata,
        Column("id", BigInteger, primary_key=True),
        Column("floor_pk", BigInteger, ForeignKey("floors.pk", ondelete=ondelete)),
    )
    return metadata


def test_check_floor_fk_cascade_rejects_missing_cascade() -> None:
    """FK trỏ `floors.pk` không `ondelete='CASCADE'` → `RuntimeError` nêu bảng/cột."""
    metadata = _fake_metadata(ondelete=None)
    with pytest.raises(RuntimeError, match="floor_children"):
        check_floor_fk_cascade(metadata)


def test_check_floor_fk_cascade_accepts_cascade() -> None:
    """FK đúng `ondelete='CASCADE'` → không ném."""
    check_floor_fk_cascade(_fake_metadata(ondelete="CASCADE"))


def test_check_floor_fk_cascade_accepts_real_metadata() -> None:
    """`Base.metadata` sau `load_all_models()` (mọi FK thật của repo) → đạt."""
    load_all_models()
    check_floor_fk_cascade(Base.metadata)
