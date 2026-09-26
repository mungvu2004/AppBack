"""Nền dựng riêng của ba route đọc (B3-02 việc R); bổ sung cho `_helpers.py`, không thay nó.

Ba thứ lặp lại: đường của từng op, một dự án đã `commit` kèm người dùng để gọi HTTP, và
bộ nghe SQL xoá mềm một tầng **giữa** hai câu lệnh của cùng một request — cách duy nhất
dựng được cuộc đua "tầng biến mất sau `get_floor`" mà [8] đòi cho #33 và N16.

`headers_of` lấy lại từ `apps/api/projects/tests/test_routes_common.py` (B2-01) chứ không
viết bản thứ hai — cùng lệ với `sql_count`.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from sqlalchemy import event, update
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.util import await_only

from packages.db.models.auth import User
from packages.db.models.floors import FloorRow
from packages.db.models.projects import Project
from packages.testing.factories.auth import make_user
from packages.testing.factories.floors import make_floor
from packages.testing.factories.projects import make_project
from packages.testing.fixtures.clock import FakeClock


@dataclass(frozen=True)
class Stage:
    """Một dự án đã `commit`, người sở hữu nó, và các tầng theo thứ tự tạo."""

    owner: User
    project: Project
    floors: tuple[FloorRow, ...]


def floor_path(project_id: str, floor_id: str) -> str:
    """#33 — `GET /api/projects/{project_id}/floors/{floor_id}/spatial`."""
    return f"/api/projects/{project_id}/floors/{floor_id}/spatial"


def layer_path(project_id: str, floor_id: str) -> str:
    """N16 — đường của `spatial_read_layer`."""
    return f"{floor_path(project_id, floor_id)}/layer"


def graph_path(project_id: str) -> str:
    """N15 — `GET /api/projects/{project_id}/spatial`."""
    return f"/api/projects/{project_id}/spatial"


async def make_stage(db: AsyncSession, *, floors: int = 1, **overrides: Any) -> Stage:
    """Dự án + `floors` tầng đã **commit**: route chạy trên session khác nên phải thấy dữ liệu."""
    owner = await make_user(db)
    project = await make_project(db, owner=owner, **overrides)
    rows = [await make_floor(db, project=project, order=index) for index in range(floors)]
    await db.commit()
    return Stage(owner=owner, project=project, floors=tuple(rows))


@contextmanager
def delete_floor_mid_request(
    sessionmaker: async_sessionmaker[AsyncSession], floor_pk: int, clock: FakeClock
) -> Iterator[None]:
    """Xoá mềm một tầng ngay **sau** câu `SELECT` đầu tiên chạm bảng `floors` của request.

    Phải là `after_cursor_execute`: bắn trước câu lệnh thì chính `get_floor` đã không thấy
    tầng nữa và nhánh "đọc lại rỗng" không bao giờ chạy. `await_only` dùng được vì bộ nghe
    của engine async nằm trong greenlet của chính lượt gọi ấy; session thứ hai `commit` nên
    câu lệnh **tiếp theo** của request — giao dịch khác, mức `read committed` — thấy tầng
    đã biến mất.
    """
    fired = [False]

    async def soft_delete() -> None:
        """Xoá mềm ở một giao dịch riêng rồi commit ngay."""
        async with sessionmaker() as session:
            await session.execute(update(FloorRow).where(FloorRow.pk == floor_pk).values(deleted_at=clock.now()))
            await session.commit()

    def on_execute(_conn: Any, _cursor: Any, statement: str, *_rest: Any) -> None:
        """Bắn đúng một lần, ngay sau câu đầu tiên đọc bảng `floors`."""
        if fired[0] or " floors" not in statement:
            return
        fired[0] = True
        await_only(soft_delete())

    event.listen(Engine, "after_cursor_execute", on_execute)
    try:
        yield
    finally:
        event.remove(Engine, "after_cursor_execute", on_execute)
