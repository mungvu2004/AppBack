"""Lịch dọn ảnh đại diện cũ/mồ côi (B1-04 [6] "Dọn rác", BE-00 §7 "Khuôn lịch nền").

`apps/worker` nhập module này để chạy beat, nên chỉ nhập `packages.core`, `packages.db`,
`packages.storage`, `packages.messaging` — không `fastapi`, `starlette`, `jwt`, `argon2`
(BE-00 §2.1 "apps.api.*.jobs").

Duyệt `list_prefix("users/", older_than=…)`, chỉ xét khoá khớp đúng mẫu ảnh đại diện
(`^users/usr_<ULID>/avatar/<ULID>\\.(png|jpg)$`), rồi đọc `avatar_key`/`deleted_at` của mọi
người liên quan trong một lô **theo `IN (...)`** (R-20) thay vì một truy vấn mỗi object. Object
khác `avatar_key` hiện tại (ảnh cũ, hay object mồ côi từ một giao dịch N14 đã hỏng) hay của
người đã xoá mềm → xoá.
"""

import logging
import re
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.core.clock import Clock, SystemClock
from packages.core.settings import get_core_settings
from packages.db.engine import worker_sessionmaker
from packages.db.models.auth import User
from packages.messaging import periodic
from packages.storage.port import ObjectInfo, ObjectStorage

_log: Final = logging.getLogger(__name__)

TASK_NAME: Final = "default.me.purge_avatars"
EVERY: Final = timedelta(hours=24)
RETENTION: Final = timedelta(days=1)
BATCH: Final = 1000

_AVATAR_KEY_RE: Final = re.compile(r"^users/(usr_[0-9A-HJKMNP-TV-Z]{26})/avatar/[0-9A-HJKMNP-TV-Z]{26}\.(png|jpg)$")


async def _batches(items: AsyncIterator[ObjectInfo], size: int) -> AsyncIterator[list[tuple[str, str]]]:
    """Khoá ảnh đại diện hợp mẫu, gom theo lô `size` — khoá không khớp mẫu bị bỏ ngay tại đây."""
    chunk: list[tuple[str, str]] = []
    async for item in items:
        match = _AVATAR_KEY_RE.match(item.key)
        if match is None:
            continue
        chunk.append((match.group(1), item.key))
        if len(chunk) >= size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


async def _purge_chunk(
    sessionmaker: async_sessionmaker[AsyncSession], storage: ObjectStorage, chunk: list[tuple[str, str]]
) -> int:
    """Đọc `avatar_key`/`deleted_at` của mọi người trong lô bằng một `IN (...)`, rồi xoá object thừa."""
    user_ids = {user_id for user_id, _ in chunk}
    async with sessionmaker() as session:
        rows = await session.execute(select(User.id, User.avatar_key, User.deleted_at).where(User.id.in_(user_ids)))
        by_user = {row.id: row for row in rows}
    removed = 0
    for user_id, key in chunk:
        row = by_user.get(user_id)
        stale = row is None or row.deleted_at is not None or row.avatar_key != key
        if stale:
            await storage.delete(key)
            removed += 1
    return removed


async def run_purge_avatars(
    sessionmaker: async_sessionmaker[AsyncSession], storage: ObjectStorage, clock: Clock, *, batch: int = BATCH
) -> int:
    """Xoá ảnh đại diện cũ hơn `RETENTION` mà không còn là ảnh hiện tại; trả số object đã xoá."""
    cutoff = clock.now() - RETENTION
    removed = 0
    async for chunk in _batches(storage.list_prefix("users/", older_than=cutoff), batch):
        removed += await _purge_chunk(sessionmaker, storage, chunk)
    _log.info("me_avatars_purged", extra={"removed": removed})
    return removed


@periodic(TASK_NAME, every=EVERY)
async def purge_avatars() -> None:
    """Hàm lịch: chỉ dựng tài nguyên thật rồi gọi lõi (BE-00 §7 "Khuôn lịch nền").

    `create_storage` nhập trễ (trong hàm): `minio` tự nhập `argon2` (qua `MinioAdmin`), nên
    nhập nó ở đầu module sẽ phá ranh giới "`apps.api.*.jobs` không nhập `argon2`" (BE-00 §2.1),
    dù mã của module này không hề chạm `argon2` (mẫu `apps/api/projects/jobs.py`).
    """
    from packages.storage.factory import create_storage
    from packages.storage.settings import get_storage_settings

    clock = SystemClock()
    storage = create_storage(get_storage_settings(), get_core_settings(), clock)
    await run_purge_avatars(worker_sessionmaker(), storage, clock)
