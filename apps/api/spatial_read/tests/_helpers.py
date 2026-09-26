"""Nền dựng dùng chung cho mọi test của `apps.api.spatial_read` (B3-02).

Ba việc lặp lại ở gần như mọi file: dựng một dự án + n tầng đã `commit` (các test đồng
thời cần dữ liệu **thấy được từ session khác**), mở một session độc lập thứ hai, và chạy
hai coroutine thật sự song song trên hai session.

Đếm câu SQL thì dùng `apps.api.projects.tests.sql_count.count_sql` của B2-01, không viết
bộ đếm thứ hai.
"""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.db.models.floors import FloorRow
from packages.db.models.projects import Project
from packages.testing.factories.auth import make_user
from packages.testing.factories.floors import make_floor
from packages.testing.factories.projects import make_project


@dataclass(frozen=True)
class Scene:
    """Một dự án đã `commit` kèm các tầng của nó, theo thứ tự tạo."""

    project: Project
    floors: tuple[FloorRow, ...]


async def make_scene(db: AsyncSession, *, floors: int = 1) -> Scene:
    """Dự án + `floors` tầng, đã **commit** để session khác nhìn thấy (test đồng thời)."""
    user = await make_user(db)
    project = await make_project(db, owner=user)
    rows = [await make_floor(db, project=project) for _ in range(floors)]
    await db.commit()
    return Scene(project=project, floors=tuple(rows))


@asynccontextmanager
async def other_session(sessionmaker: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    """Một session thứ hai, giao dịch riêng — kết nối thật, không phải bản sao của session test."""
    async with sessionmaker() as session:
        yield session


async def race[T](
    first: Callable[[], Awaitable[T]], second: Callable[[], Awaitable[T]]
) -> tuple[T | BaseException, ...]:
    """Chạy hai lượt song song và trả kết quả **hoặc** lỗi của từng bên, theo thứ tự truyền vào."""
    return tuple(await asyncio.gather(first(), second(), return_exceptions=True))
