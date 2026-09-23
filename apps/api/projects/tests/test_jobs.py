"""Lịch dọn dự án xoá mềm `default.projects.purge_deleted` (B2-01 [8] "Việc nền", J01, J06)."""

import asyncio
import logging
import secrets
from collections.abc import Sequence
from contextlib import suppress
from datetime import timedelta
from pathlib import Path
from typing import Final

import pytest
from minio import Minio
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.projects.jobs import EVERY, TASK_NAME, _handle_delete_error, purge_deleted_projects, run_project_purge
from apps.api.projects.settings import reset_projects_settings_cache
from packages.core.clock import SystemClock
from packages.db.engine import GATE_CONNECT_TIMEOUT_S, create_engine, create_sessionmaker
from packages.db.models.projects import Project
from packages.db.settings import DatabaseSettings, reset_database_settings_cache
from packages.messaging.schedules import schedule_entries
from packages.storage.keys import project_prefix
from packages.storage.local import LocalDiskStorage
from packages.storage.s3 import S3Storage, http_client
from packages.storage.settings import reset_storage_settings_cache
from packages.testing.factories.auth import make_user
from packages.testing.factories.projects import make_project
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.services import ephemeral_minio

DAY: Final = timedelta(days=1)
MARKER: Final = "marker.bin"
LOOP_TIMEOUT_S: Final = 60.0
"""Trần của một lượt `run_project_purge` trong test: hồi quy RES-02 làm test hỏng, không treo."""


def _marker_key(project_id: str) -> str:
    """Khoá của một object đánh dấu dưới tiền tố dự án."""
    return f"{project_prefix(project_id)}{MARKER}"


async def _project_exists(sessionmaker: async_sessionmaker[AsyncSession], project_id: str) -> bool:
    """Dòng `projects` còn tồn tại (kể cả đã xoá mềm), đọc trên session mới (K22)."""
    async with sessionmaker() as session:
        count = await session.scalar(select(func.count()).select_from(Project).where(Project.id == project_id))
        return bool(count)


async def _lock_membership_for_update(
    sessionmaker: async_sessionmaker[AsyncSession],
    project_ids: Sequence[str],
    gate: asyncio.Event,
    release: asyncio.Event,
) -> None:
    """Giữ khoá `FOR UPDATE` trên dòng `project_memberships` của các dự án cho tới khi `release` mở.

    Khoá thật trên Postgres thật (K23): `DELETE FROM projects` phải khoá dòng con để CASCADE,
    nên mọi dự án bị khoá ở đây sẽ đụng `lock_timeout` — cách duy nhất dựng được "dự án hỏng"
    mà không giả lập kho hay DB.
    """
    async with sessionmaker() as session:
        await session.execute(
            text("SELECT 1 FROM project_memberships WHERE project_id = ANY(:ids) FOR UPDATE"),
            {"ids": list(project_ids)},
        )
        gate.set()
        await release.wait()
        await session.rollback()


async def _seed_two(
    db_session: AsyncSession, fake_clock: FakeClock, *, doomed_days: int = 31, kept_days: int = 29
) -> tuple[Project, Project]:
    """Một dự án xoá mềm quá hạn (`doomed_days`) và một dự án xoá mềm còn trong hạn (`kept_days`)."""
    owner = await make_user(db_session, password=None)
    now = fake_clock.now()
    doomed = await make_project(db_session, owner=owner, deleted_at=now - doomed_days * DAY)
    kept = await make_project(db_session, owner=owner, deleted_at=now - kept_days * DAY)
    await db_session.commit()
    return doomed, kept


async def test_purge_deleted_projects__J01(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Dự án xoá mềm 31 ngày bị xoá cả dòng lẫn object; dự án 29 ngày còn nguyên."""
    caplog.set_level(logging.INFO, logger="apps.api.projects.jobs")
    doomed, kept = await _seed_two(db_session, fake_clock)
    for project in (doomed, kept):
        await local_storage.put(_marker_key(project.id), b"x", content_type="application/octet-stream", max_bytes=10)
    removed = await run_project_purge(db_sessionmaker, local_storage, fake_clock, batch=10)
    assert removed == 1
    assert not await _project_exists(db_sessionmaker, doomed.id)
    assert await _project_exists(db_sessionmaker, kept.id)
    assert await local_storage.stat(_marker_key(doomed.id)) is None
    assert await local_storage.stat(_marker_key(kept.id)) is not None
    record = next(r for r in caplog.records if r.msg == "project_purge_completed")
    assert record.__dict__["purged"] == 1


async def test_purge_deleted_projects__J06(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """Chạy lặp: lượt thứ hai không xoá thêm gì và không hỏng."""
    doomed, _kept = await _seed_two(db_session, fake_clock)
    assert await run_project_purge(db_sessionmaker, local_storage, fake_clock, batch=10) == 1
    assert await run_project_purge(db_sessionmaker, local_storage, fake_clock, batch=10) == 0
    assert not await _project_exists(db_sessionmaker, doomed.id)


async def test_purge_batches_until_exhausted(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """Lô nhỏ hơn số dự án quá hạn: vòng lặp lo hết mọi lô, không dừng ở lô đầu."""
    owner = await make_user(db_session, password=None)
    now = fake_clock.now()
    for _ in range(5):
        await make_project(db_session, owner=owner, deleted_at=now - 31 * DAY)
    await db_session.commit()
    assert await run_project_purge(db_sessionmaker, local_storage, fake_clock, batch=2) == 5


async def _seed_overdue(db_session: AsyncSession, fake_clock: FakeClock, count: int) -> list[Project]:
    """`count` dự án xoá mềm quá hạn, trả theo đúng thứ tự `id ASC` mà lịch dọn duyệt."""
    owner = await make_user(db_session, password=None)
    now = fake_clock.now()
    projects = [await make_project(db_session, owner=owner, deleted_at=now - 31 * DAY) for _ in range(count)]
    await db_session.commit()
    return sorted(projects, key=lambda project: project.id)


def _purge_failed_ids(caplog: pytest.LogCaptureFixture) -> list[str]:
    """id của mọi dự án bị bỏ qua vì DB hỏng trong lượt vừa chạy."""
    return [r.__dict__["project_id"] for r in caplog.records if r.msg == "project_purge_db_failed"]


async def test_purge_does_not_loop_when_a_whole_batch_fails(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RES-02: `batch + 1` dự án quá hạn mà **mọi** dự án đều hỏng → hàm kết thúc, không lặp vô hạn.

    Chọn lại từ đầu mỗi lô (bản cũ) sẽ lấy đúng lô đã hỏng mãi mãi vì `len(ids) == batch`;
    keyset `id > after` bảo đảm tiến. `asyncio.wait_for` để hồi quy làm test **hỏng** chứ
    không treo cả lượt cổng.
    """
    caplog.set_level(logging.WARNING, logger="apps.api.projects.jobs")
    monkeypatch.setenv("PROJECT_PURGE_LOCK_TIMEOUT_S", "1")
    reset_projects_settings_cache()
    batch = 2
    projects = await _seed_overdue(db_session, fake_clock, batch + 1)
    gate, release = asyncio.Event(), asyncio.Event()
    ids = [project.id for project in projects]
    locker = asyncio.create_task(_lock_membership_for_update(db_sessionmaker, ids, gate, release))
    try:
        await gate.wait()
        removed = await asyncio.wait_for(
            run_project_purge(db_sessionmaker, local_storage, fake_clock, batch=batch), timeout=LOOP_TIMEOUT_S
        )
    finally:
        release.set()
        await locker
        reset_projects_settings_cache()

    assert removed == 0
    for project in projects:
        assert await _project_exists(db_sessionmaker, project.id)
    # Mỗi dự án đúng **một** lần thử trong một lượt gọi: hỏng thì để lượt lịch sau làm lại.
    assert sorted(_purge_failed_ids(caplog)) == [project.id for project in projects]


async def test_purge_skips_failed_projects_and_finishes_later_batches(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lượt pha trộn qua nhiều lô: dự án bị khoá còn lại, mọi dự án khác bị xoá."""
    monkeypatch.setenv("PROJECT_PURGE_LOCK_TIMEOUT_S", "1")
    reset_projects_settings_cache()
    batch = 2
    projects = await _seed_overdue(db_session, fake_clock, 5)
    stuck = [projects[0], projects[3]]
    alive = [project for project in projects if project not in stuck]
    gate, release = asyncio.Event(), asyncio.Event()
    locker = asyncio.create_task(_lock_membership_for_update(db_sessionmaker, [p.id for p in stuck], gate, release))
    try:
        await gate.wait()
        removed = await asyncio.wait_for(
            run_project_purge(db_sessionmaker, local_storage, fake_clock, batch=batch), timeout=LOOP_TIMEOUT_S
        )
    finally:
        release.set()
        await locker
        reset_projects_settings_cache()

    assert removed == len(alive)
    for project in stuck:
        assert await _project_exists(db_sessionmaker, project.id)
    for project in alive:
        assert not await _project_exists(db_sessionmaker, project.id)


async def test_storage_failure_keeps_row_and_logs(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """MinIO dừng giữa lượt dọn: dòng `projects` còn, ghi log `project_purge_storage_failed`."""
    caplog.set_level(logging.WARNING, logger="apps.api.projects.jobs")
    doomed, _kept = await _seed_two(db_session, fake_clock)
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
        removed = await run_project_purge(db_sessionmaker, storage, fake_clock, batch=10)
    finally:
        with suppress(Exception):  # đã dừng giữa test: lượt dừng thứ hai ném lỗi
            container.stop()
    assert removed == 0
    assert await _project_exists(db_sessionmaker, doomed.id)
    record = next(r for r in caplog.records if r.msg == "project_purge_storage_failed")
    assert record.__dict__["project_id"] == doomed.id


async def test_locked_membership_row_defers_only_that_project(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Khoá `FOR UPDATE` một dòng `project_memberships` của dự án A: B vẫn bị xoá, A còn."""
    monkeypatch.setenv("PROJECT_PURGE_LOCK_TIMEOUT_S", "1")
    reset_projects_settings_cache()
    owner = await make_user(db_session, password=None)
    member = await make_user(db_session, password=None)
    now = fake_clock.now()
    project_a = await make_project(db_session, owner=owner, members=[member], deleted_at=now - 31 * DAY)
    project_b = await make_project(db_session, owner=owner, deleted_at=now - 31 * DAY)
    await db_session.commit()
    gate, release = asyncio.Event(), asyncio.Event()
    locker = asyncio.create_task(_lock_membership_for_update(db_sessionmaker, [project_a.id], gate, release))
    try:
        await gate.wait()
        removed = await run_project_purge(db_sessionmaker, local_storage, fake_clock, batch=10)
    finally:
        release.set()
        await locker
        reset_projects_settings_cache()
    assert removed == 1
    assert await _project_exists(db_sessionmaker, project_a.id)
    assert not await _project_exists(db_sessionmaker, project_b.id)


def test_handle_delete_error_reraises_non_infra_db_errors() -> None:
    """`DBAPIError` không dịch được sang hạ tầng (`translate_db_error` trả `None`) → ném lại, không nuốt."""
    exc = DBAPIError("DELETE ...", {}, Exception("mã lỗi nghiệp vụ lạ, không phải hạ tầng"))
    with pytest.raises(DBAPIError):
        _handle_delete_error(exc, "prj_x")


def test_schedule_is_registered() -> None:
    """Lịch nằm trong sổ của `packages.messaging` để beat của worker đọc được."""
    entries = {entry.name: entry for entry in schedule_entries()}
    assert entries[TASK_NAME].every == EVERY
    assert entries[TASK_NAME].function == "purge_deleted_projects"


def test_purge_deleted_projects_smoke(
    db_url: str, tmp_path: Path, storage_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test khói: gọi chính hàm lịch (giờ thật, `worker_sessionmaker()`, kho local thật)."""
    engine = create_engine(DatabaseSettings(database_url=db_url, db_connect_timeout_s=int(GATE_CONNECT_TIMEOUT_S)))
    maker = create_sessionmaker(engine)

    async def _seed() -> str:
        async with maker() as session:
            owner = await make_user(session, password=None)
            project = await make_project(session, owner=owner, deleted_at=SystemClock().now() - 31 * DAY)
            await session.commit()
            return project.id

    project_id = asyncio.run(_seed())
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_LOCAL_ROOT", str(tmp_path / "objects"))
    reset_database_settings_cache()
    reset_storage_settings_cache()
    try:
        purge_deleted_projects()
    finally:
        reset_database_settings_cache()
        reset_storage_settings_cache()
        asyncio.run(engine.dispose())
    assert asyncio.run(_project_exists(maker, project_id)) is False
