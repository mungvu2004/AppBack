"""Ba lịch nền của bản vẽ (B2-04 [6] "Việc nền", [8], J01, J06).

Postgres, Redis và kho đĩa thật. Kho đĩa lấy `mtime` từ giờ thật, `updated_at` do DB đặt cũng
theo giờ thật, nên "quá hạn" dựng bằng `fake_clock.set(giờ thật + …)` chứ không lùi dữ liệu.
"""

from datetime import timedelta
from pathlib import Path
from typing import Final

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.drawings import jobs
from apps.api.drawings.errors import PIPELINE_STALLED
from apps.api.drawings.jobs import run_orphan_purge, run_requeue, run_upload_purge
from apps.api.drawings.settings import get_drawings_settings
from apps.api.drawings.tests._helpers import Scene, make_scene, read_run, sync_bus_reset
from apps.api.drawings.tests._job_helpers import pending_run, put_bytes, put_chunk, real_now, set_updated_at, window
from packages.core.clock import SystemClock
from packages.core.error_codes import DEPENDENCY_UNAVAILABLE
from packages.core.ids import new_id
from packages.core.object_keys import project_prefix, upload_prefix
from packages.db.models.drawings import DrawingRow, UploadChunkRow, UploadRow
from packages.db.models.floors import FloorRow
from packages.db.models.projects import Project
from packages.db.settings import reset_database_settings_cache
from packages.messaging.redis import broker_redis_sync
from packages.messaging.schedules import schedule_entries
from packages.storage.local import LocalDiskStorage
from packages.storage.settings import reset_storage_settings_cache
from packages.testing.factories.drawings import make_upload
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.messaging import queued_payloads

__all__ = ["sync_bus_reset"]  # fixture nhập từ `_helpers`, pytest tìm theo tên trong module này

PIPELINE_QUEUE: Final = "pipeline.cpu"


class _FailingStorage(LocalDiskStorage):
    """Kho đĩa thật nhưng mọi lệnh xoá báo `DEPENDENCY_UNAVAILABLE` — kho ngoài mất kết nối."""

    async def delete(self, key: str) -> None:
        raise DEPENDENCY_UNAVAILABLE.error(retry_after=1)

    async def delete_prefix(self, prefix: str) -> None:
        raise DEPENDENCY_UNAVAILABLE.error(retry_after=1)


async def _committed_scene(db: AsyncSession) -> Scene:
    """Sân khấu đã `commit` để session của lịch nền nhìn thấy."""
    scene = await make_scene(db)
    await db.commit()
    return scene


async def _count(db: AsyncSession, model: type[UploadRow] | type[UploadChunkRow]) -> int:
    """Số dòng của bảng, đọc trên session của test (không cache: `count(*)` mới mỗi lần)."""
    return int(await db.scalar(select(func.count()).select_from(model)) or 0)


# ---------------------------------------------------------------------------
# purge_uploads
# ---------------------------------------------------------------------------


async def test_purge_uploads__J01(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """`receiving` quá hạn mất cả object lẫn dòng; `receiving` mới còn; khúc của `complete` mất, dòng lượt còn."""
    scene = await _committed_scene(db_session)
    fake_clock.set(real_now() + timedelta(days=2))
    stale = await make_upload(db_session, project=scene.project, floor=scene.floor)
    fresh = await make_upload(db_session, project=scene.project, floor=scene.floor)
    done = await make_upload(db_session, project=scene.project, floor=scene.floor, status="complete")
    stale_key = await put_chunk(db_session, local_storage, scene, stale, 0)
    fresh_key = await put_chunk(db_session, local_storage, scene, fresh, 0)
    done_key = await put_chunk(db_session, local_storage, scene, done, 0)
    await set_updated_at(db_session, fresh.id, fake_clock.now() - timedelta(hours=1))
    await db_session.commit()

    purged = await run_upload_purge(db_sessionmaker, local_storage, fake_clock)

    assert purged == 2  # một lượt bỏ dở + một khúc của lượt complete
    assert await local_storage.stat(stale_key) is None
    assert await local_storage.stat(done_key) is None
    assert await local_storage.stat(fresh_key) is not None
    remaining = set((await db_session.scalars(select(UploadRow.id))).all())
    assert remaining == {fresh.id, done.id}
    assert await _count(db_session, UploadChunkRow) == 1


async def test_purge_uploads__J06(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """Chạy hai lần: lần hai không lỗi và không xoá thêm; lượt `rejected` cũng mất khúc."""
    scene = await _committed_scene(db_session)
    fake_clock.set(real_now() + timedelta(days=2))
    stale = await make_upload(db_session, project=scene.project, floor=scene.floor)
    rejected = await make_upload(db_session, project=scene.project, floor=scene.floor, status="rejected")
    await put_chunk(db_session, local_storage, scene, stale, 0)
    await put_chunk(db_session, local_storage, scene, rejected, 0)
    await db_session.commit()

    assert await run_upload_purge(db_sessionmaker, local_storage, fake_clock) == 2
    assert await run_upload_purge(db_sessionmaker, local_storage, fake_clock) == 0


async def test_purge_uploads_keeps_rows_when_storage_is_down(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    tmp_path: Path,
) -> None:
    """Kho báo lỗi: dòng `uploads` và `upload_chunks` ở lại để lượt sau thử lại, không lỗi ra ngoài."""
    scene = await _committed_scene(db_session)
    fake_clock.set(real_now() + timedelta(days=2))
    stale = await make_upload(db_session, project=scene.project, floor=scene.floor)
    done = await make_upload(db_session, project=scene.project, floor=scene.floor, status="complete")
    await put_chunk(db_session, local_storage, scene, done, 0)
    await db_session.commit()
    failing = _FailingStorage(tmp_path / "objects", fake_clock, "http://test")

    assert await run_upload_purge(db_sessionmaker, failing, fake_clock) == 0
    assert {stale.id, done.id} <= set((await db_session.scalars(select(UploadRow.id))).all())
    assert await _count(db_session, UploadChunkRow) == 1


async def test_purge_uploads_skips_a_row_touched_between_select_and_delete(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Khúc mới đến (`updated_at` mới) sau bước chọn: `_delete_upload_row` không khớp, dòng còn."""
    scene = await _committed_scene(db_session)
    upload = await make_upload(db_session, project=scene.project, floor=scene.floor)
    await db_session.commit()
    cutoff = real_now() - timedelta(hours=1)  # `updated_at` (giờ thật) mới hơn mốc → không quá hạn

    assert await jobs._delete_upload_row(db_sessionmaker, upload.id, cutoff) is False
    assert await _count(db_session, UploadRow) == 1


# ---------------------------------------------------------------------------
# purge_upload_orphans
# ---------------------------------------------------------------------------


async def _orphan_fixture(db: AsyncSession, storage: LocalDiskStorage) -> tuple[dict[str, str], dict[str, str]]:
    """Dựng kho có lẫn mồ côi và object đang dùng; trả `(khoá bị xoá, khoá phải còn)` theo tên."""
    scene = await _committed_scene(db)
    upload = await make_upload(db, project=scene.project, floor=scene.floor, status="complete")
    ghost = new_id("upl", SystemClock())
    live = upload_prefix(scene.project.id, scene.floor.level_id, upload.id)
    dead = upload_prefix(scene.project.id, scene.floor.level_id, ghost)
    used_page, spare_page = f"{live}pages/0-01USED.png", f"{live}pages/1-01SPARE.png"
    db.add(
        DrawingRow(
            id=new_id("drw", SystemClock()),
            floor_pk=scene.floor.pk,
            upload_id=upload.id,
            name="ban-ve",
            page_key=used_page,
            width_px=10,
            height_px=10,
            uploaded_at=real_now(),
            uploader_id=scene.user.id,
        )
    )
    used_chunk = await put_chunk(db, storage, scene, upload, 0)
    await db.commit()
    doomed = {
        "no_upload_row": await put_bytes(storage, f"{dead}original.png"),
        "chunk_without_row": await put_bytes(storage, f"{live}chunks/9/{9:064x}"),
        "page_nobody_uses": await put_bytes(storage, spare_page),
    }
    kept = {
        "original": await put_bytes(storage, f"{live}original.png"),
        "run_artifact": await put_bytes(storage, f"{live}runs/x.bin"),
        "chunk_with_row": used_chunk,
        "page_in_use": await put_bytes(storage, used_page),
        "outside_pattern": await put_bytes(storage, f"{project_prefix(scene.project.id)}avatars/a.png"),
        "bad_id": await put_bytes(
            storage, f"{project_prefix(scene.project.id)}floors/{scene.floor.level_id}/uploads/nope/x"
        ),
    }
    return doomed, kept


async def test_purge_upload_orphans__J01(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """Mồ côi mất; khoá ngoài bố cục, trang đang dùng, khúc còn dòng và tệp của lượt còn dòng ở lại."""
    doomed, kept = await _orphan_fixture(db_session, local_storage)
    fake_clock.set(real_now() + timedelta(days=2))

    removed = await run_orphan_purge(db_sessionmaker, local_storage, fake_clock)

    assert removed == len(doomed)
    for name, key in doomed.items():
        assert await local_storage.stat(key) is None, name
    for name, key in kept.items():
        assert await local_storage.stat(key) is not None, name


async def test_purge_upload_orphans_spares_young_objects(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """Object mới hơn 24 giờ chưa bao giờ bị coi là mồ côi (dòng DB của nó có thể chưa commit)."""
    doomed, _ = await _orphan_fixture(db_session, local_storage)
    fake_clock.set(real_now() + timedelta(hours=1))

    assert await run_orphan_purge(db_sessionmaker, local_storage, fake_clock) == 0
    for key in doomed.values():
        assert await local_storage.stat(key) is not None


async def test_purge_upload_orphans__J06(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Chạy hai lần, lô tra DB nhỏ hơn số object: lần hai không xoá thêm, không lỗi."""
    doomed, kept = await _orphan_fixture(db_session, local_storage)
    fake_clock.set(real_now() + timedelta(days=2))
    monkeypatch.setattr(jobs, "LOOKUP_BATCH", 2)

    assert await run_orphan_purge(db_sessionmaker, local_storage, fake_clock) == len(doomed)
    assert await run_orphan_purge(db_sessionmaker, local_storage, fake_clock) == 0
    for key in kept.values():
        assert await local_storage.stat(key) is not None


async def test_purge_upload_orphans_survives_storage_errors(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    tmp_path: Path,
) -> None:
    """Xoá lỗi: lượt dọn không ném, đếm 0 và object còn để lượt sau thử lại."""
    doomed, _ = await _orphan_fixture(db_session, local_storage)
    fake_clock.set(real_now() + timedelta(days=2))
    failing = _FailingStorage(tmp_path / "objects", fake_clock, "http://test")

    assert await run_orphan_purge(db_sessionmaker, failing, fake_clock) == 0
    for key in doomed.values():
        assert await local_storage.stat(key) is not None


# ---------------------------------------------------------------------------
# requeue_pipeline_runs
# ---------------------------------------------------------------------------


def _sent(client_queue: list[dict[str, object]]) -> list[str]:
    """`run_id` của mọi thông điệp `start` trên hàng, theo thứ tự gửi."""
    return [str(p["run_id"]) for p in client_queue]


async def test_requeue_pipeline_runs__J01(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    messaging_env: None,
    sync_bus_reset: None,
    fake_clock: FakeClock,
) -> None:
    """Lượt `pending` quá cửa sổ đầu được gửi lại đúng một lần: payload đúng, đếm tăng, `updated_at` = now."""
    broker = broker_redis_sync()
    broker.delete(PIPELINE_QUEUE)
    scene = await _committed_scene(db_session)
    run, upload = await pending_run(db_sessionmaker, scene, fake_clock)
    broker.delete(PIPELINE_QUEUE)  # bỏ thông điệp của `start_run`
    base = get_drawings_settings().pipeline_requeue_after_s
    assert await run_requeue(db_sessionmaker, fake_clock) == 0  # chưa tới hạn (giờ giả 2026-01-01 < updated_at)
    fake_clock.set(real_now() + window(base, 0) + timedelta(seconds=5))

    assert await run_requeue(db_sessionmaker, fake_clock) == 1

    assert queued_payloads(broker, PIPELINE_QUEUE) == [{"schema_version": 1, "run_id": run.id, "upload_id": upload.id}]
    row = await read_run(db_session, run.id)
    assert (row.requeue_count, row.updated_at, row.status) == (1, fake_clock.now(), "pending")
    broker.close()


async def test_requeue_pipeline_runs__J06(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    messaging_env: None,
    sync_bus_reset: None,
    fake_clock: FakeClock,
) -> None:
    """Cửa sổ lùi nhân đôi: 6 lần gửi đúng hạn, lần quét kế → `failed` `PIPELINE_STALLED`, không gửi thêm."""
    broker = broker_redis_sync()
    broker.delete(PIPELINE_QUEUE)
    scene = await _committed_scene(db_session)
    run, _ = await pending_run(db_sessionmaker, scene, fake_clock)
    broker.delete(PIPELINE_QUEUE)
    base = get_drawings_settings().pipeline_requeue_after_s
    fake_clock.set(real_now() + window(base, 0) + timedelta(seconds=5))
    assert await run_requeue(db_sessionmaker, fake_clock) == 1

    for count in range(1, jobs.REQUEUE_MAX):
        fake_clock.advance(window(base, count) - timedelta(seconds=1))
        assert await run_requeue(db_sessionmaker, fake_clock) == 0, f"chưa tới hạn ở lần {count}"
        fake_clock.advance(timedelta(seconds=1))
        assert await run_requeue(db_sessionmaker, fake_clock) == 1

    assert _sent(queued_payloads(broker, PIPELINE_QUEUE)) == [run.id] * jobs.REQUEUE_MAX
    fake_clock.advance(window(base, jobs.REQUEUE_MAX))
    assert await run_requeue(db_sessionmaker, fake_clock) == 0

    row = await read_run(db_session, run.id)
    assert (row.status, row.error_code, row.requeue_count) == ("failed", PIPELINE_STALLED, jobs.REQUEUE_MAX)
    assert len(queued_payloads(broker, PIPELINE_QUEUE)) == jobs.REQUEUE_MAX
    broker.close()


async def test_requeue_skips_superseded_runs(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    messaging_env: None,
    sync_bus_reset: None,
    fake_clock: FakeClock,
) -> None:
    """Lượt bị lượt tải mới thay (đã `failed`) không được gửi lại; chỉ lượt mới nhất."""
    broker = broker_redis_sync()
    scene = await _committed_scene(db_session)
    await pending_run(db_sessionmaker, scene, fake_clock)
    newest, _ = await pending_run(db_sessionmaker, scene, fake_clock)
    broker.delete(PIPELINE_QUEUE)
    fake_clock.set(real_now() + timedelta(days=2))

    assert await run_requeue(db_sessionmaker, fake_clock) == 1
    assert _sent(queued_payloads(broker, PIPELINE_QUEUE)) == [newest.id]
    broker.close()


@pytest.mark.parametrize("target", ["floor", "project"])
async def test_requeue_skips_deleted_floor_or_project(
    target: str,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    messaging_env: None,
    sync_bus_reset: None,
    fake_clock: FakeClock,
) -> None:
    """Tầng hay dự án xoá mềm: không gửi lại, lượt để nguyên `pending`."""
    broker = broker_redis_sync()
    scene = await _committed_scene(db_session)
    run, _ = await pending_run(db_sessionmaker, scene, fake_clock)
    broker.delete(PIPELINE_QUEUE)
    deleted = real_now()
    if target == "floor":
        await db_session.execute(update(FloorRow).where(FloorRow.pk == scene.floor.pk).values(deleted_at=deleted))
    else:
        await db_session.execute(update(Project).where(Project.id == scene.project.id).values(deleted_at=deleted))
    await db_session.commit()
    fake_clock.set(real_now() + timedelta(days=2))

    assert await run_requeue(db_sessionmaker, fake_clock) == 0
    assert queued_payloads(broker, PIPELINE_QUEUE) == []
    assert (await read_run(db_session, run.id)).requeue_count == 0
    broker.close()


async def test_requeue_one_skips_a_run_that_changed_under_the_lock(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    messaging_env: None,
    sync_bus_reset: None,
    fake_clock: FakeClock,
) -> None:
    """Ảnh chụp lúc chọn lỗi thời (worker đã ghi bước) hoặc lượt không còn → `None`, không gửi, không đổi."""
    scene = await _committed_scene(db_session)
    run, upload = await pending_run(db_sessionmaker, scene, fake_clock)
    row = await read_run(db_session, run.id)
    outdated = jobs._Stale(run.id, upload.id, row.requeue_count + 1, row.updated_at)
    ghost = jobs._Stale("run_nope", upload.id, 0, row.updated_at)

    assert await jobs._requeue_one(db_sessionmaker, outdated, fake_clock) is None
    assert await jobs._requeue_one(db_sessionmaker, ghost, fake_clock) is None
    assert (await read_run(db_session, run.id)).requeue_count == 0


# ---------------------------------------------------------------------------
# Đăng ký lịch
# ---------------------------------------------------------------------------


def test_schedules_are_registered() -> None:
    """Ba lịch nằm trong sổ của `packages.messaging` với đúng chu kỳ và hàm."""
    entries = {entry.name: entry for entry in schedule_entries()}
    expected = {
        jobs.PURGE_UPLOADS_TASK: (jobs.PURGE_UPLOADS_EVERY, "purge_uploads"),
        jobs.PURGE_ORPHANS_TASK: (jobs.PURGE_ORPHANS_EVERY, "purge_upload_orphans"),
        jobs.REQUEUE_RUNS_TASK: (jobs.REQUEUE_RUNS_EVERY, "requeue_pipeline_runs"),
    }
    assert {name: (entries[name].every, entries[name].function) for name in expected} == expected


def test_scheduled_functions_smoke(
    db_url: str, tmp_path: Path, storage_env: None, messaging_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test khói: gọi chính ba hàm lịch (giờ thật, `worker_sessionmaker()`, kho local thật) trên DB rỗng."""
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_LOCAL_ROOT", str(tmp_path / "objects"))
    reset_database_settings_cache()
    reset_storage_settings_cache()
    try:
        jobs.purge_uploads()
        jobs.purge_upload_orphans()
        jobs.requeue_pipeline_runs()
    finally:
        reset_database_settings_cache()
        reset_storage_settings_cache()
