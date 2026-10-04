"""Helper chung của test `pipeline_orchestrate` (NO-295 P2-02, khuôn `apps/api/drawings/tests/_helpers.py`).

Trước đây `_open_run`, `_run_row`, `_drawings`/`_drawing_of`, `"ml.infer"`, `"L-ABCDEFGHIJ"` được
khai lặp ở từng file test (các việc viết song song, không có file helper chung).
"""

from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.drawings.runs import RunRow, start_run
from packages.db.hooks import after_commit_idle
from packages.db.models.drawings import DrawingRow, PipelineRunRow
from packages.testing.fixtures.clock import FakeClock

ML_QUEUE: Final = "ml.infer"
"""Hàng ba bước ML; không worker nào nghe nó trong test nên đọc được bằng `queued_payloads`."""

LEVEL_ID: Final = "L-ABCDEFGHIJ"
"""`level_id` công khai mẫu cho khoá storage của test không dựng tầng thật."""


async def open_run(maker: async_sessionmaker[AsyncSession], upload_id: str, clock: FakeClock) -> RunRow:
    """Mở một lượt chạy và commit (task `start` chỉ chạy sau khi B2-04 đã ghi dòng lượt)."""
    async with maker() as db:
        run = await start_run(db, upload_id=upload_id, clock=clock)
        await db.commit()
    await after_commit_idle(db)
    return run


async def run_row(db: AsyncSession, run_id: str) -> PipelineRunRow:
    """Dòng `pipeline_runs` đọc lại từ DB (không qua ảnh chụp `RunRow`), đã `refresh`."""
    row = (await db.execute(select(PipelineRunRow).where(PipelineRunRow.id == run_id))).scalar_one()
    await db.refresh(row)
    return row


async def floor_drawings(db: AsyncSession, floor_pk: int) -> list[DrawingRow]:
    """Mọi dòng `drawings` của tầng (một tầng nhiều nhất một dòng — test khẳng định điều đó)."""
    return list((await db.execute(select(DrawingRow).where(DrawingRow.floor_pk == floor_pk))).scalars())
