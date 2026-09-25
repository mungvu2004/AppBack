"""Helper riêng của test ba lịch nền bản vẽ (việc J của B2-04): đặt object, lượt chạy `pending`, giờ thật.

Ở đây chỉ dựng dữ liệu; mọi khẳng định nằm trong `test_jobs.py`.
"""

from datetime import datetime, timedelta

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.drawings.runs import RunRow, start_run
from apps.api.drawings.tests._helpers import Scene
from packages.core.clock import Clock, SystemClock
from packages.db.hooks import after_commit_idle
from packages.db.models.drawings import UploadChunkRow, UploadRow
from packages.storage.local import LocalDiskStorage
from packages.testing.factories.drawings import chunk_key, make_upload


def real_now() -> datetime:
    """Giờ thật: `mtime` của kho đĩa và `updated_at` do DB đặt đều theo giờ thật, không theo `fake_clock`."""
    return SystemClock().now()


async def put_bytes(storage: LocalDiskStorage, key: str) -> str:
    """Ghi một object nhỏ dưới `key` và trả lại chính `key`."""
    await storage.put(key, b"x", content_type="application/octet-stream", max_bytes=16)
    return key


async def put_chunk(db: AsyncSession, storage: LocalDiskStorage, scene: Scene, upload: UploadRow, index: int) -> str:
    """Khúc thật: object trong kho **và** dòng `upload_chunks` trỏ tới nó; trả khoá object."""
    sha = f"{index:064x}"
    key = chunk_key(scene.project.id, scene.floor.level_id, upload.id, index, sha)
    await put_bytes(storage, key)
    db.add(UploadChunkRow(upload_id=upload.id, chunk_index=index, size_bytes=1, sha256=sha, object_key=key))
    await db.flush()
    return key


async def set_updated_at(db: AsyncSession, upload_id: str, when: datetime) -> None:
    """Đặt `updated_at` của lượt tải (giả một lượt tải cũ hay mới)."""
    await db.execute(update(UploadRow).where(UploadRow.id == upload_id).values(updated_at=when))


async def pending_run(
    sessionmaker: async_sessionmaker[AsyncSession], scene: Scene, clock: Clock, *, upload: UploadRow | None = None
) -> tuple[RunRow, UploadRow]:
    """Lượt tải `complete` + lượt chạy `pending` đã **commit** (lịch nền đọc trên session riêng)."""
    async with sessionmaker() as db:
        upload = upload or await make_upload(db, project=scene.project, floor=scene.floor, status="complete")
        run = await start_run(db, upload_id=upload.id, clock=clock)
        await db.commit()
        await after_commit_idle(db)
    return run, upload


def window(base_s: int, requeue_count: int) -> timedelta:
    """Cửa sổ lùi `PIPELINE_REQUEUE_AFTER_S x 2^requeue_count` — cùng công thức với lõi, viết lại để test độc lập."""
    return timedelta(seconds=base_s * 2**requeue_count)
