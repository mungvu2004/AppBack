"""Lịch gộp nhật ký `default.spatial_write.compact_change_log` (B3-03 [6], BE-00 §7).

`apps/worker` nhập module này để chạy beat nên nó không được kéo `fastapi`/`starlette`
(BE-00 §7 "luật hàm worker nhập"): chỉ nhập `changes` (kiểu), `settings` và `packages.*`.
`floor_change_log` chỉ phục vụ 409 W20 qua `remote_changes_since`, vốn chỉ đọc giá trị
**mới nhất** của mỗi `(entity_id, field)`; mọi dòng cũ hơn đã bị một dòng mới hơn cùng
khoá che khuất là rác an toàn để xoá, miễn còn ngoài cửa sổ nhìn lại gần đây (giữ lại vài
chục ngày cho việc tra cứu thủ công/hỗ trợ, không phải vì `remote_changes_since` cần).
"""

import logging
from datetime import timedelta
from typing import Final

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import aliased

from apps.api.spatial_write.settings import get_spatial_write_settings
from packages.core.clock import Clock, SystemClock
from packages.db.engine import worker_sessionmaker
from packages.db.models.spatial import FloorChangeLogRow
from packages.messaging import periodic

_log: Final = logging.getLogger(__name__)

TASK_NAME: Final = "default.spatial_write.compact_change_log"
EVERY: Final = timedelta(hours=24)


async def _select_batch(session: AsyncSession, clock: Clock, after_days: int, batch: int) -> list[int]:
    """`batch` `id` nhật ký cũ hơn `after_days` ngày mà có dòng mới hơn cùng `(floor_pk, entity_id, field)`.

    "Mới hơn" so theo `(revision, id)`, khớp thứ tự `remote_changes_since` dùng để chọn
    giá trị hiện hành — xoá đúng những dòng hàm đó không bao giờ còn đọc tới.
    """
    cutoff = clock.now() - timedelta(days=after_days)
    newer = aliased(FloorChangeLogRow)
    is_newer = or_(
        newer.revision > FloorChangeLogRow.revision,
        and_(newer.revision == FloorChangeLogRow.revision, newer.id > FloorChangeLogRow.id),
    )
    stmt = (
        select(FloorChangeLogRow.id)
        .where(
            FloorChangeLogRow.changed_at < cutoff,
            select(newer.id)
            .where(
                newer.floor_pk == FloorChangeLogRow.floor_pk,
                newer.entity_id == FloorChangeLogRow.entity_id,
                newer.field == FloorChangeLogRow.field,
                is_newer,
            )
            .exists(),
        )
        .order_by(FloorChangeLogRow.id)
        .limit(batch)
    )
    return list((await session.execute(stmt)).scalars())


async def run_change_log_compaction(sessionmaker: async_sessionmaker[AsyncSession], clock: Clock, *, batch: int) -> int:
    """Xoá theo lô (một giao dịch mỗi lô); trả tổng số dòng đã xoá."""
    after_days = get_spatial_write_settings().spatial_log_compact_after_days
    deleted = 0
    while True:
        async with sessionmaker() as session:
            ids = await _select_batch(session, clock, after_days, batch)
            if ids:
                await session.execute(delete(FloorChangeLogRow).where(FloorChangeLogRow.id.in_(ids)))
                await session.commit()
        deleted += len(ids)
        if len(ids) < batch:
            break
    _log.info("change_log_compaction_completed", extra={"deleted": deleted})
    return deleted


@periodic(TASK_NAME, every=EVERY)
async def compact_change_log() -> None:
    """Hàm lịch: chỉ dựng tài nguyên thật rồi gọi lõi (BE-00 §7 "khuôn lịch nền")."""
    await run_change_log_compaction(
        worker_sessionmaker(), SystemClock(), batch=get_spatial_write_settings().spatial_log_compact_batch
    )
