"""Hai lịch nền của dataset ML: quét lượt dựng treo và dọn object mồ côi (B6-02 [6], khuôn BE-00 §7).

Lõi (`run_…`) tách khỏi hàm lịch để test truyền đồng hồ giả và kho của test; hàm lịch chỉ dựng
tài nguyên thật. Beat của `apps/worker` nhập module này, nên nó chỉ được nhập `packages.*`,
`apps.api.admin_ml_datasets.*` và `apps.worker.datasets.*` — không `fastapi`/`starlette`.

- `run_dataset_build_sweep`: bản `building` mà thông điệp chưa tới worker (`build_started_at IS
  NULL`) quá `DATASET_BUILD_REQUEUE_AFTER_S` → gửi lại, tối đa `MAX_REQUEUES` lượt; bản không
  tiến triển (`updated_at`) quá `DATASET_BUILD_TIMEOUT_S` → `failed` `DATASET_BUILD_TIMEOUT`.
  Gửi lại **trước** khi xét hết giờ: một bản còn lượt gửi lại thì cho nó chạy, chỉ bản đã hết
  lượt hoặc thật sự đứng im mới bị chốt hỏng.
- `run_dataset_orphan_purge`: tiền tố `ml/datasets/{dsv}/` không còn dòng, hay dòng đã `failed`
  → `delete_prefix`. Tiền tố của bản `ready`/`building` không bao giờ bị đụng ([6] bước 9).
"""

from __future__ import annotations

import logging
from collections.abc import Collection
from datetime import timedelta
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.admin_ml_datasets.errors import DATASET_BUILD_TIMEOUT
from apps.api.admin_ml_datasets.settings import get_ml_datasets_settings
from apps.worker.datasets.tasks import (
    BUILD_SOURCE,
    open_storage,
    run_fail_dataset_version,
    version_prefix,
)
from packages.core.clock import Clock, SystemClock
from packages.db.engine import session_scope, worker_sessionmaker
from packages.db.hooks import after_commit_idle, on_after_commit
from packages.db.models.admin_ml_datasets import DatasetVersionRow
from packages.messaging import periodic, send_task
from packages.messaging.payloads.datasets import BUILD_VERSION_TASK, BuildDatasetVersionPayload
from packages.storage.port import ObjectStorage

_log: Final = logging.getLogger(__name__)

SWEEP_TASK: Final = "default.datasets.sweep_builds"
SWEEP_EVERY: Final = timedelta(minutes=5)
PURGE_TASK: Final = "default.datasets.purge_orphans"
PURGE_EVERY: Final = timedelta(hours=24)

SWEEP_BATCH: Final = 100
PURGE_BATCH: Final = 500
MAX_REQUEUES: Final = 3
"""Sau ba lượt gửi lại mà thông điệp vẫn không tới worker, vấn đề không phải thông điệp."""

PURGE_MIN_AGE: Final = timedelta(hours=24)
"""Object trẻ hơn mức này có thể thuộc một lượt dựng đang chạy — không đụng (khuôn B6-01)."""

DATASETS_PREFIX: Final = "ml/datasets/"
_VERSION_DEPTH: Final = 3
"""`ml/datasets/{dsv}/…` — khoá ít đoạn hơn không thuộc một phiên bản nào."""


def _version_of(key: str) -> str | None:
    """`dsv` của một khoá dưới `ml/datasets/`; khoá lạ (thiếu đoạn) → `None` để bỏ qua.

    Không `check_id`: một khoá rác do người khác đặt cũng chỉ dẫn tới một tiền tố rác, mà
    `delete_prefix` của tiền tố rác thì vô hại — ném ở đây sẽ làm cả lượt dọn chết.
    """
    parts = key.split("/")
    return parts[2] if len(parts) > _VERSION_DEPTH and parts[2] else None


def _send_after_commit(db: AsyncSession, version_id: str) -> None:
    """Đăng ký gửi task dựng **sau** commit (K17).

    Hàm riêng chứ không `lambda` trong vòng lặp: `lambda` bắt biến của vòng lặp theo tham chiếu,
    nên cả lô sẽ gửi id của dòng cuối cùng.
    """
    payload = BuildDatasetVersionPayload(dataset_version_id=version_id)
    on_after_commit(db, lambda: send_task(BUILD_VERSION_TASK, payload))


async def _requeue_unstarted(
    sessionmaker: async_sessionmaker[AsyncSession], clock: Clock, *, after_s: int, batch: int
) -> int:
    """Gửi lại bản `building` mà worker chưa nhận; trả số bản đã gửi lại.

    Cả lô trong **một** giao dịch giữ `FOR UPDATE SKIP LOCKED`: hai beat chồng nhau không gửi
    lại cùng một bản. Task gửi sau commit (K17) — chưa commit mà worker đã nhận thì nó đọc
    `requeue_count` cũ và có thể được gửi lại lần nữa.
    """
    now = clock.now()
    stmt = (
        select(DatasetVersionRow)
        .where(
            DatasetVersionRow.status == "building",
            DatasetVersionRow.source == BUILD_SOURCE,
            DatasetVersionRow.build_started_at.is_(None),
            DatasetVersionRow.updated_at < now - timedelta(seconds=after_s),
            DatasetVersionRow.requeue_count < MAX_REQUEUES,
        )
        .order_by(DatasetVersionRow.created_at, DatasetVersionRow.id)
        .limit(batch)
        .with_for_update(skip_locked=True)
    )
    async with session_scope(sessionmaker) as db:
        rows = (await db.execute(stmt)).scalars().all()
        for row in rows:
            row.requeue_count += 1
            row.updated_at = now
            _send_after_commit(db, row.id)
        session = db
    # Chờ callback sau commit **xong** rồi mới trả (`after_commit_idle` nhận cả session đã đóng):
    # một beat trả về khi thông điệp còn nằm trong task chưa chạy thì tiến trình thoát ngay sau đó
    # sẽ đánh mất cả lô — K17 nói "sau commit", không phải "có thể không bao giờ".
    await after_commit_idle(session)
    return len(rows)


async def _fail_stalled(
    sessionmaker: async_sessionmaker[AsyncSession],
    storage: ObjectStorage,
    clock: Clock,
    *,
    timeout_s: int,
    batch: int,
) -> int:
    """Chốt `DATASET_BUILD_TIMEOUT` cho bản `building` không tiến triển; trả số bản đã chốt.

    Không khoá dòng lúc đọc: `run_fail_dataset_version` lọc `status = 'building'` trong câu
    `UPDATE`, nên hai beat cùng thấy một bản thì đúng một bên thắng và chỉ bên đó xoá tiền tố.
    """
    cutoff = clock.now() - timedelta(seconds=timeout_s)
    stmt = (
        select(DatasetVersionRow.id)
        .where(DatasetVersionRow.status == "building", DatasetVersionRow.updated_at < cutoff)
        .order_by(DatasetVersionRow.created_at, DatasetVersionRow.id)
        .limit(batch)
    )
    async with sessionmaker() as db:
        version_ids = list((await db.execute(stmt)).scalars().all())
    for version_id in version_ids:
        _log.warning("dataset_build_timeout", extra={"version_id": version_id})
        await run_fail_dataset_version(sessionmaker, storage, clock, version_id=version_id, code=DATASET_BUILD_TIMEOUT)
    return len(version_ids)


async def run_dataset_build_sweep(
    sessionmaker: async_sessionmaker[AsyncSession],
    storage: ObjectStorage,
    clock: Clock,
    *,
    batch: int = SWEEP_BATCH,
) -> int:
    """Một lượt quét lượt dựng treo; trả số bản đã xử lý (gửi lại cộng chốt hết giờ)."""
    settings = get_ml_datasets_settings()
    requeued = await _requeue_unstarted(
        sessionmaker, clock, after_s=settings.dataset_build_requeue_after_s, batch=batch
    )
    failed = await _fail_stalled(sessionmaker, storage, clock, timeout_s=settings.dataset_build_timeout_s, batch=batch)
    return requeued + failed


async def _orphans(sessionmaker: async_sessionmaker[AsyncSession], version_ids: Collection[str]) -> list[str]:
    """Trong lô, id nào không còn dòng hay dòng đã `failed` — **một** truy vấn, session đóng ngay."""
    async with sessionmaker() as db:
        stmt = select(DatasetVersionRow.id).where(
            DatasetVersionRow.id.in_(version_ids), DatasetVersionRow.status != "failed"
        )
        alive = set((await db.execute(stmt)).scalars().all())
    return sorted(version_id for version_id in version_ids if version_id not in alive)


async def _purge_chunk(
    sessionmaker: async_sessionmaker[AsyncSession], storage: ObjectStorage, version_ids: Collection[str]
) -> int:
    """Xoá tiền tố của các phiên bản mồ côi trong lô; trả số tiền tố đã xoá."""
    dead = await _orphans(sessionmaker, version_ids)
    for version_id in dead:
        await storage.delete_prefix(version_prefix(version_id))
    return len(dead)


async def run_dataset_orphan_purge(
    sessionmaker: async_sessionmaker[AsyncSession],
    storage: ObjectStorage,
    clock: Clock,
    *,
    batch: int = PURGE_BATCH,
) -> int:
    """Dọn tiền tố dataset mồ côi cũ hơn `PURGE_MIN_AGE`; trả số tiền tố đã xoá.

    Gom theo `dsv` rồi tra DB một lần mỗi `batch` phiên bản (không N+1), và `delete_prefix`
    một lần cho cả phiên bản thay vì từng khoá. Tra DB xong mới xoá: dòng chèn giữa hai bước
    chỉ có thể là dòng mới, mà object mới thì `older_than` đã loại từ đầu.
    """
    cutoff = clock.now() - PURGE_MIN_AGE
    deleted = 0
    chunk: set[str] = set()
    async for info in storage.list_prefix(DATASETS_PREFIX, older_than=cutoff):
        version_id = _version_of(info.key)
        if version_id is None:
            continue
        chunk.add(version_id)
        if len(chunk) >= batch:
            deleted += await _purge_chunk(sessionmaker, storage, chunk)
            chunk = set()
    if chunk:
        deleted += await _purge_chunk(sessionmaker, storage, chunk)
    return deleted


@periodic(SWEEP_TASK, every=SWEEP_EVERY)
async def sweep_dataset_version_builds() -> None:
    """Hàm lịch: dựng tài nguyên thật rồi gọi lõi quét lượt dựng treo."""
    clock = SystemClock()
    processed = await run_dataset_build_sweep(worker_sessionmaker(), open_storage(clock), clock)
    _log.info("dataset_build_sweep", extra={"processed": processed})


@periodic(PURGE_TASK, every=PURGE_EVERY)
async def purge_dataset_orphans() -> None:
    """Hàm lịch: dựng tài nguyên thật rồi gọi lõi dọn tiền tố mồ côi."""
    clock = SystemClock()
    deleted = await run_dataset_orphan_purge(worker_sessionmaker(), open_storage(clock), clock)
    _log.info("dataset_orphan_purge", extra={"deleted": deleted})
