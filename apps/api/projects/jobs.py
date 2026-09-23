"""Lịch dọn dự án xoá mềm (BE-00 §7 "khuôn lịch nền", "dọn rác"; B2-01 [6] "Lịch dọn").

`apps/worker` nhập module này để chạy beat, nên nó chỉ nhập `packages.core`,
`packages.db`, `packages.storage`, `packages.messaging` — không `fastapi`, `starlette`,
`jwt`, `argon2` (BE-00 §2.1, K36).

Vòng ngoài chọn id dự án đã xoá mềm quá `PROJECT_PURGE_AFTER_DAYS` bằng một session
**ngắn** rồi đóng lại trước khi gọi mạng ra kho (K36: không giữ giao dịch DB trong lúc
chờ HTTP). Với từng dự án: xoá object trước, xoá dòng sau — lưu trữ hỏng thì dòng còn
lại để lượt sau làm lại; DB hỏng (kể cả `lock_timeout` vì dự án đang bị khoá ở nơi khác)
thì bỏ qua dự án đó, sang dự án kế, không ném lỗi hạ tầng làm chết cả lượt dọn.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Final, cast

from sqlalchemy import CursorResult, delete, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.projects.settings import get_projects_settings
from packages.core.clock import Clock, SystemClock
from packages.core.errors import AppError
from packages.core.settings import get_core_settings
from packages.db.engine import worker_sessionmaker
from packages.db.errors import translate_db_error
from packages.db.models.projects import Project
from packages.messaging import periodic
from packages.storage.keys import project_prefix
from packages.storage.port import ObjectStorage

_log: Final = logging.getLogger(__name__)

TASK_NAME: Final = "default.projects.purge_deleted"
EVERY: Final = timedelta(hours=1)
DELETE_STATEMENT_TIMEOUT_S: Final = 300
"""Trần câu `DELETE` (có CASCADE) — rộng hơn trần request thường vì chạy nền, không chờ người dùng."""


async def _select_batch(
    sessionmaker: async_sessionmaker[AsyncSession], cutoff: datetime, batch: int, after: str | None
) -> list[str]:
    """id các dự án đã xoá mềm trước `cutoff` và **sau** `after`, tối đa `batch`, `id ASC`.

    Session đóng ngay khi trả (K36). `after` là mốc keyset — xem `run_project_purge` để biết
    vì sao lô sau phải bắt đầu **sau** lô trước chứ không chọn lại từ đầu.
    """
    stmt = select(Project.id).where(Project.deleted_at < cutoff).order_by(Project.id).limit(batch)
    if after is not None:
        stmt = stmt.where(Project.id > after)
    async with sessionmaker() as session:
        rows = await session.execute(stmt)
        return list(rows.scalars().all())


async def _purge_one(
    sessionmaker: async_sessionmaker[AsyncSession],
    storage: ObjectStorage,
    project_id: str,
    cutoff: datetime,
    lock_timeout_s: int,
) -> bool:
    """Xoá object rồi dòng của một dự án; `False` = bỏ qua (lưu trữ hay DB hỏng, thử lại lượt sau)."""
    try:
        await storage.delete_prefix(project_prefix(project_id))
    except AppError:
        _log.warning("project_purge_storage_failed", extra={"project_id": project_id})
        return False
    async with sessionmaker() as session:
        try:
            # `SET LOCAL` không nhận tham số bind (Postgres); hai giá trị đều là số nguyên
            # nội bộ (cấu hình), không phải dữ liệu người dùng.
            await session.execute(text(f"SET LOCAL statement_timeout = '{DELETE_STATEMENT_TIMEOUT_S}s'"))
            await session.execute(text(f"SET LOCAL lock_timeout = '{lock_timeout_s}s'"))
            result = cast(
                "CursorResult[Any]",
                await session.execute(delete(Project).where(Project.id == project_id, Project.deleted_at < cutoff)),
            )
            await session.commit()
        except DBAPIError as exc:
            await session.rollback()
            return _handle_delete_error(exc, project_id)
        return result.rowcount > 0


def _handle_delete_error(exc: DBAPIError, project_id: str) -> bool:
    """Hạ tầng hỏng (`translate_db_error`, kể cả `lock_timeout`) → log, bỏ qua dự án; còn lại ném lại."""
    if translate_db_error(exc) is None:
        raise exc
    _log.warning("project_purge_db_failed", extra={"project_id": project_id})
    return False


async def run_project_purge(
    sessionmaker: async_sessionmaker[AsyncSession], storage: ObjectStorage, clock: Clock, *, batch: int
) -> int:
    """Xoá cứng mọi dự án xoá mềm quá hạn, theo lô; trả tổng số dự án đã xoá.

    Phân trang **keyset** (`id > after`), không phải chọn lại từ đầu mỗi lô. Dự án xoá được
    thì biến mất, dự án hỏng (kho hay DB) thì **ở lại**: chọn lại từ đầu sẽ lấy đúng lô cũ
    và lặp vô hạn ngay khi cả một lô hỏng — không trần, không backoff (RES-02). Nhờ `after`,
    mỗi dự án được thử **đúng một lần** mỗi lượt gọi và vòng lặp luôn tiến; dự án hỏng để
    lượt lịch sau (mỗi `EVERY`) làm lại.
    """
    settings = get_projects_settings()
    cutoff = clock.now() - timedelta(days=settings.project_purge_after_days)
    purged = 0
    after: str | None = None
    while True:
        ids = await _select_batch(sessionmaker, cutoff, batch, after)
        for project_id in ids:
            if await _purge_one(sessionmaker, storage, project_id, cutoff, settings.project_purge_lock_timeout_s):
                purged += 1
        if len(ids) < batch:
            break
        after = ids[-1]
    _log.info("project_purge_completed", extra={"purged": purged})
    return purged


@periodic(TASK_NAME, every=EVERY)
async def purge_deleted_projects() -> None:
    """Hàm lịch: chỉ dựng tài nguyên thật rồi gọi lõi (BE-00 §7 "khuôn lịch nền").

    `create_storage` nhập trễ (trong hàm, không ở đầu file): `minio` — dù chỉ dùng cho
    `STORAGE_BACKEND=s3` — tự nhập `argon2` ngay ở `minio/__init__.py` (qua
    `MinioAdmin`/`crypto.py`), nên nhập nó ở đầu module sẽ phá ranh giới "`apps.api.*.jobs`
    không nhập `argon2`" (BE-00 §2.1) dù mã của module này không hề chạm `argon2`.
    """
    from packages.storage.factory import create_storage
    from packages.storage.settings import get_storage_settings

    clock = SystemClock()
    storage = create_storage(get_storage_settings(), get_core_settings(), clock)
    await run_project_purge(worker_sessionmaker(), storage, clock, batch=get_projects_settings().project_purge_batch)
