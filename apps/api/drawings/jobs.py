"""Ba lịch nền của bản vẽ (BE-00 §7 "khuôn lịch nền"; B2-04 [6] "Việc nền"): dọn lượt tải,
dọn object mồ côi, quét bù lượt chạy.

`apps/worker` nhập module này để chạy beat, nên nó chỉ nhập `packages.*`, `apps.api.drawings.{runs,
settings,errors}` và `apps.api.floors.settings` — không `fastapi`, `starlette`, `jwt`, `argon2`
(BE-00 §2.1, K36). Mỗi lõi (`run_*`) nhận tài nguyên qua đối số để test dùng Postgres/kho thật;
hàm lịch chỉ dựng tài nguyên rồi gọi lõi.

Mọi lần gọi kho đi qua mạng nằm **ngoài** giao dịch DB (R-20): chọn ứng viên → đóng session →
gọi kho → mở session ngắn để xoá dòng, với điều kiện xoá lặp lại điều kiện chọn (dòng vừa đổi
giữa hai bước thì không khớp). Lõi quét bù là nơi duy nhất ngoài `runs` ghi `pipeline_runs`
(chỉ `requeue_count`, `updated_at`); trạng thái `failed` luôn do `runs.fail_run` đặt ([9]).
"""

import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Final, cast

from sqlalchemy import CursorResult, delete, func, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.drawings.errors import PIPELINE_STALLED
from apps.api.drawings.runs import fail_run, lock_run, publish_progress_after_commit, send_start_after_commit
from apps.api.drawings.settings import get_drawings_settings
from packages.core.clock import Clock, SystemClock
from packages.core.errors import AppError
from packages.core.object_keys import upload_prefix, upload_prefix_of
from packages.db.engine import worker_sessionmaker
from packages.db.hooks import after_commit_idle
from packages.db.models.drawings import DrawingRow, PipelineRunRow, UploadChunkRow, UploadRow
from packages.db.models.floors import FloorRow
from packages.db.models.projects import Project
from packages.messaging import periodic
from packages.storage.port import ObjectStorage

_log: Final = logging.getLogger(__name__)

PURGE_UPLOADS_TASK: Final = "default.drawings.purge_uploads"
PURGE_UPLOADS_EVERY: Final = timedelta(hours=1)
PURGE_ORPHANS_TASK: Final = "default.drawings.purge_orphans"
PURGE_ORPHANS_EVERY: Final = timedelta(hours=24)
REQUEUE_RUNS_TASK: Final = "default.drawings.requeue_runs"
REQUEUE_RUNS_EVERY: Final = timedelta(minutes=10)

ORPHAN_MIN_AGE: Final = timedelta(hours=24)
"""Object trẻ hơn mốc này chưa bao giờ bị coi là mồ côi: dòng DB của nó có thể chưa commit."""
LOOKUP_BATCH: Final = 500
"""Số khoá tra DB một lần khi dọn mồ côi (một câu `IN` mỗi bảng mỗi lô)."""
REQUEUE_MAX: Final = 6
"""Số lần gửi lại tối đa của một lượt `pending`; hết trần → `PIPELINE_STALLED`."""
_BATCH: Final = 100
_CHUNK_SECTIONS: Final = frozenset({"chunks", "pages"})


# ---------------------------------------------------------------------------
# Dọn lượt tải
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Abandoned:
    """Lượt tải `receiving` quá hạn: id + tiền tố object (cần `level_id` của tầng để dựng)."""

    id: str
    prefix: str


async def _abandoned_batch(
    sessionmaker: async_sessionmaker[AsyncSession], cutoff: datetime, after: str | None
) -> list[_Abandoned]:
    """`_BATCH` lượt `receiving` có `updated_at < cutoff`, `id ASC` (keyset: lượt hỏng kho ở lại bảng)."""
    stmt = (
        select(UploadRow.id, UploadRow.project_id, FloorRow.level_id)
        .join(FloorRow, FloorRow.pk == UploadRow.floor_pk)
        .where(UploadRow.status == "receiving", UploadRow.updated_at < cutoff)
        .order_by(UploadRow.id)
        .limit(_BATCH)
    )
    if after is not None:
        stmt = stmt.where(UploadRow.id > after)
    async with sessionmaker() as session:
        rows = (await session.execute(stmt)).all()
    return [_Abandoned(id=r.id, prefix=upload_prefix(r.project_id, r.level_id, r.id)) for r in rows]


async def _delete_prefix(storage: ObjectStorage, prefix: str) -> bool:
    """Xoá mọi object dưới `prefix`; kho hỏng (`AppError`) → log, `False` để dòng DB ở lại thử lần sau."""
    try:
        await storage.delete_prefix(prefix)
    except AppError:
        _log.warning("upload_purge_failed", extra={"prefix": prefix})
        return False
    return True


async def _delete_upload_row(sessionmaker: async_sessionmaker[AsyncSession], upload_id: str, cutoff: datetime) -> bool:
    """Xoá dòng nếu vẫn `receiving` và vẫn quá hạn (khúc mới đến giữa hai bước thì `False`); CASCADE lo bảng con."""
    stmt = delete(UploadRow).where(
        UploadRow.id == upload_id, UploadRow.status == "receiving", UploadRow.updated_at < cutoff
    )
    async with sessionmaker() as session:
        result = cast("CursorResult[Any]", await session.execute(stmt))
        await session.commit()
        return result.rowcount > 0


async def _purge_abandoned(
    sessionmaker: async_sessionmaker[AsyncSession], storage: ObjectStorage, cutoff: datetime
) -> int:
    """Xoá object rồi dòng của mọi lượt `receiving` bị bỏ dở; trả số dòng đã xoá."""
    purged = 0
    after: str | None = None
    while batch := await _abandoned_batch(sessionmaker, cutoff, after):
        for upload in batch:
            if await _delete_prefix(storage, upload.prefix) and await _delete_upload_row(
                sessionmaker, upload.id, cutoff
            ):
                purged += 1
        after = batch[-1].id
    return purged


async def _finished_chunks(
    sessionmaker: async_sessionmaker[AsyncSession], after: tuple[str, int] | None
) -> list[tuple[str, int, str]]:
    """`_BATCH` khúc của lượt `complete|rejected`: `(upload_id, chunk_index, object_key)` theo khoá chính."""
    stmt = (
        select(UploadChunkRow.upload_id, UploadChunkRow.chunk_index, UploadChunkRow.object_key)
        .join(UploadRow, UploadRow.id == UploadChunkRow.upload_id)
        .where(UploadRow.status.in_(("complete", "rejected")))
        .order_by(UploadChunkRow.upload_id, UploadChunkRow.chunk_index)
        .limit(_BATCH)
    )
    if after is not None:
        stmt = stmt.where(tuple_(UploadChunkRow.upload_id, UploadChunkRow.chunk_index) > after)
    async with sessionmaker() as session:
        return [(r.upload_id, r.chunk_index, r.object_key) for r in await session.execute(stmt)]


async def _delete_object(storage: ObjectStorage, key: str) -> bool:
    """Xoá một object; kho hỏng → log, `False`."""
    try:
        await storage.delete(key)
    except AppError:
        _log.warning("upload_chunk_purge_failed", extra={"key": key})
        return False
    return True


async def _purge_finished_chunks(sessionmaker: async_sessionmaker[AsyncSession], storage: ObjectStorage) -> int:
    """Xoá object rồi dòng của khúc thuộc lượt đã `complete|rejected` (đã có `original.*` hoặc bị từ chối)."""
    purged = 0
    after: tuple[str, int] | None = None
    while batch := await _finished_chunks(sessionmaker, after):
        gone = [(u, i) for u, i, key in batch if await _delete_object(storage, key)]
        if gone:
            async with sessionmaker() as session:
                await session.execute(
                    delete(UploadChunkRow).where(tuple_(UploadChunkRow.upload_id, UploadChunkRow.chunk_index).in_(gone))
                )
                await session.commit()
            purged += len(gone)
        after = batch[-1][:2]
    return purged


async def run_upload_purge(sessionmaker: async_sessionmaker[AsyncSession], storage: ObjectStorage, clock: Clock) -> int:
    """Dọn lượt tải bỏ dở và khúc đã dùng xong; trả tổng số dòng `uploads` + `upload_chunks` đã xoá.

    `receiving` quá `UPLOAD_ABANDON_AFTER_H` (tính từ `updated_at`) là bỏ dở. Khúc của lượt
    `complete|rejected` không còn ai đọc: bản gốc đã ghép, hoặc lượt đã bị từ chối.
    """
    cutoff = clock.now() - timedelta(hours=get_drawings_settings().upload_abandon_after_h)
    purged = await _purge_abandoned(sessionmaker, storage, cutoff)
    purged += await _purge_finished_chunks(sessionmaker, storage)
    _log.info("upload_purge_completed", extra={"purged": purged})
    return purged


# ---------------------------------------------------------------------------
# Dọn mồ côi
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Found:
    """Khoá object nằm dưới một lượt tải lên: khoá, id lượt và đoạn đầu sau tiền tố (`chunks`, `pages`, …)."""

    key: str
    upload_id: str
    section: str


def _found(key: str) -> _Found | None:
    """`key` nếu khớp bố cục lượt tải lên (theo `upload_prefix_of`, NO-079), ngược lại `None`."""
    try:
        prefix = upload_prefix_of(key)
    except ValueError:
        return None
    return _Found(key=key, upload_id=prefix.split("/")[5], section=key[len(prefix) :].split("/", 1)[0])


async def _references(session: AsyncSession, batch: Sequence[_Found]) -> tuple[set[str], set[str]]:
    """`(upload_id còn dòng, khoá khúc/trang còn dòng trỏ tới)` của lô — hai câu `IN`, không N+1."""
    keys = [f.key for f in batch if f.section in _CHUNK_SECTIONS]
    uploads = await session.scalars(select(UploadRow.id).where(UploadRow.id.in_({f.upload_id for f in batch})))
    chunks = await session.scalars(select(UploadChunkRow.object_key).where(UploadChunkRow.object_key.in_(keys)))
    pages = await session.scalars(select(DrawingRow.page_key).where(DrawingRow.page_key.in_(keys)))
    return set(uploads), {*chunks, *pages}


async def _orphans(sessionmaker: async_sessionmaker[AsyncSession], batch: Sequence[_Found]) -> list[str]:
    """Khoá của lô không ai dùng: lượt tải không còn dòng, hoặc khúc/trang không dòng nào trỏ tới."""
    async with sessionmaker() as session:
        uploads, referenced = await _references(session, batch)
    return [
        f.key for f in batch if f.upload_id not in uploads or (f.section in _CHUNK_SECTIONS and f.key not in referenced)
    ]


async def _delete_all(storage: ObjectStorage, keys: Iterable[str]) -> int:
    """Xoá từng khoá; trả số khoá xoá được (kho hỏng ở khoá nào thì bỏ khoá đó, lượt sau thử lại)."""
    return sum([await _delete_object(storage, key) for key in keys])


async def run_orphan_purge(sessionmaker: async_sessionmaker[AsyncSession], storage: ObjectStorage, clock: Clock) -> int:
    """Xoá object cũ hơn 24 giờ dưới `projects/` mà DB không còn dùng; trả số object đã xoá.

    Khoá ngoài bố cục lượt tải lên (avatar, thư viện, …) không bao giờ vào lô. Khoá của lượt
    tải còn dòng thì chỉ `chunks/…` và `pages/…` không ai trỏ mới bị xoá: `original.*` và
    `runs/…` đi theo vòng đời của lượt tải.
    """
    older_than = clock.now() - ORPHAN_MIN_AGE
    removed = 0
    batch: list[_Found] = []
    async for info in storage.list_prefix("projects/", older_than=older_than):
        if (found := _found(info.key)) is not None:
            batch.append(found)
        if len(batch) >= LOOKUP_BATCH:
            removed += await _delete_all(storage, await _orphans(sessionmaker, batch))
            batch = []
    if batch:
        removed += await _delete_all(storage, await _orphans(sessionmaker, batch))
    _log.info("orphan_purge_completed", extra={"removed": removed})
    return removed


# ---------------------------------------------------------------------------
# Quét bù lượt chạy
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Stale:
    """Lượt `pending` đã quá cửa sổ lùi, kèm trạng thái lúc chọn để so lại dưới khoá."""

    id: str
    upload_id: str
    requeue_count: int
    updated_at: datetime


async def _stale_batch(
    sessionmaker: async_sessionmaker[AsyncSession], now: datetime, after: str | None
) -> list[_Stale]:
    """`_BATCH` lượt `pending` chưa bị thay, tầng và dự án chưa xoá, đã quá `AFTER x 2^requeue_count` giây."""
    base_s = get_drawings_settings().pipeline_requeue_after_s
    window = timedelta(seconds=1) * (base_s * func.power(2, PipelineRunRow.requeue_count))
    stmt = (
        select(PipelineRunRow.id, PipelineRunRow.upload_id, PipelineRunRow.requeue_count, PipelineRunRow.updated_at)
        .join(FloorRow, FloorRow.pk == PipelineRunRow.floor_pk)
        .join(Project, Project.id == FloorRow.project_id)
        .where(
            PipelineRunRow.status == "pending",
            PipelineRunRow.superseded_by.is_(None),
            FloorRow.deleted_at.is_(None),
            Project.deleted_at.is_(None),
            PipelineRunRow.updated_at + window <= now,
        )
        .order_by(PipelineRunRow.id)
        .limit(_BATCH)
    )
    if after is not None:
        stmt = stmt.where(PipelineRunRow.id > after)
    async with sessionmaker() as session:
        return [_Stale(r.id, r.upload_id, r.requeue_count, r.updated_at) for r in await session.execute(stmt)]


async def _unchanged(db: AsyncSession, stale: _Stale) -> bool:
    """Dưới khoá: lượt vẫn `pending`, chưa bị thay và chưa ai chạm (`requeue_count`, `updated_at` như lúc chọn)."""
    stmt = select(PipelineRunRow.id).where(
        PipelineRunRow.id == stale.id,
        PipelineRunRow.status == "pending",
        PipelineRunRow.superseded_by.is_(None),
        PipelineRunRow.requeue_count == stale.requeue_count,
        PipelineRunRow.updated_at == stale.updated_at,
    )
    return (await db.execute(stmt)).first() is not None


async def _resend(db: AsyncSession, stale: _Stale, clock: Clock) -> None:
    """Tăng `requeue_count`, đặt `updated_at = now`, hẹn gửi lại `start` và phát lại `Progress` sau commit."""
    await db.execute(
        update(PipelineRunRow)
        .where(PipelineRunRow.id == stale.id)
        .values(requeue_count=PipelineRunRow.requeue_count + 1, updated_at=clock.now())
    )
    send_start_after_commit(db, run_id=stale.id, upload_id=stale.upload_id)
    await publish_progress_after_commit(db, stale.upload_id)


async def _requeue_one(sessionmaker: async_sessionmaker[AsyncSession], stale: _Stale, clock: Clock) -> str | None:
    """Xử lý một lượt trong một giao dịch: `"requeued"`, `"stalled"`, hoặc `None` khi lượt đã đổi.

    `lock_run` khoá `floors` rồi lượt (BE-00 §7) trước khi so lại trạng thái, nên worker ghi
    bước chen vào giữa lúc chọn và lúc gửi làm lượt này bị bỏ qua, không bị gửi lại nhầm.
    """
    async with sessionmaker() as db:
        if await lock_run(db, run_id=stale.id) is None or not await _unchanged(db, stale):
            return None
        stalled = stale.requeue_count >= REQUEUE_MAX
        if stalled:
            await fail_run(db, run_id=stale.id, error_code=PIPELINE_STALLED, clock=clock)
        else:
            await _resend(db, stale, clock)
        await db.commit()
        await after_commit_idle(db)
    return "stalled" if stalled else "requeued"


async def run_requeue(sessionmaker: async_sessionmaker[AsyncSession], clock: Clock) -> int:
    """Quét bù lượt `pending`; trả số lượt đã gửi lại (lượt bị đánh `PIPELINE_STALLED` không tính).

    Cửa sổ lùi nhân đôi mỗi lần (`PIPELINE_REQUEUE_AFTER_S x 2^requeue_count`) để worker chậm
    không bị gửi dồn; sau `REQUEUE_MAX` lần mà lượt vẫn `pending` thì nó `failed`.
    """
    now = clock.now()
    outcomes: list[str | None] = []
    after: str | None = None
    while batch := await _stale_batch(sessionmaker, now, after):
        outcomes += [await _requeue_one(sessionmaker, stale, clock) for stale in batch]
        after = batch[-1].id
    requeued, stalled = outcomes.count("requeued"), outcomes.count("stalled")
    _log.info("requeue_completed", extra={"requeued": requeued, "stalled": stalled})
    return requeued


# ---------------------------------------------------------------------------
# Hàm lịch
# ---------------------------------------------------------------------------


def _storage(clock: Clock) -> ObjectStorage:
    """Kho thật của tiến trình; nhập trễ vì `minio` nhập `argon2` ở `__init__` (BE-00 §2.1, như B2-03)."""
    from packages.core.settings import get_core_settings
    from packages.storage.factory import create_storage
    from packages.storage.settings import get_storage_settings

    return create_storage(get_storage_settings(), get_core_settings(), clock)


@periodic(PURGE_UPLOADS_TASK, every=PURGE_UPLOADS_EVERY)
async def purge_uploads() -> None:
    """Hàm lịch: dựng kho thật rồi gọi `run_upload_purge`."""
    clock = SystemClock()
    await run_upload_purge(worker_sessionmaker(), _storage(clock), clock)


@periodic(PURGE_ORPHANS_TASK, every=PURGE_ORPHANS_EVERY)
async def purge_upload_orphans() -> None:
    """Hàm lịch: dựng kho thật rồi gọi `run_orphan_purge`."""
    clock = SystemClock()
    await run_orphan_purge(worker_sessionmaker(), _storage(clock), clock)


@periodic(REQUEUE_RUNS_TASK, every=REQUEUE_RUNS_EVERY)
async def requeue_pipeline_runs() -> None:
    """Hàm lịch: quét bù lượt chạy `pending` bằng giờ thật."""
    await run_requeue(worker_sessionmaker(), SystemClock())
