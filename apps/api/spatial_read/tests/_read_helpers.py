"""Nền dựng riêng của ba route đọc (B3-02 việc R); bổ sung cho `_helpers.py`, không thay nó.

Ba thứ lặp lại: đường của từng op, cổng `drawing_pages` giả mà ba file test cùng dùng, và
bộ nghe SQL xoá mềm một tầng **giữa** hai câu lệnh của cùng một request — cách duy nhất
dựng được cuộc đua "tầng biến mất sau `get_floor`" mà [8] đòi cho #33 và N16.

Dựng dữ liệu thì dùng `make_scene` của `_helpers.py`, không có bản thứ hai ở đây;
`headers_of` lấy lại từ `apps/api/projects/tests/test_routes_common.py` (B2-01) — cùng lệ
với `sql_count`.
"""

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any

from sqlalchemy import event, update
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.util import await_only

from apps.api.core import extensions
from apps.api.spatial_read import pages
from packages.db.models.floors import FloorRow
from packages.testing.fixtures.clock import FakeClock


def floor_path(project_id: str, floor_id: str) -> str:
    """#33 — `GET /api/projects/{project_id}/floors/{floor_id}/spatial`."""
    return f"/api/projects/{project_id}/floors/{floor_id}/spatial"


def layer_path(project_id: str, floor_id: str) -> str:
    """N16 — đường của `spatial_read_layer`."""
    return f"{floor_path(project_id, floor_id)}/layer"


def graph_path(project_id: str) -> str:
    """N15 — `GET /api/projects/{project_id}/spatial`."""
    return f"/api/projects/{project_id}/spatial"


class FakePages:
    """Cổng `drawing_pages` giả: chỉ biết những tầng test đưa vào, đúng hợp đồng `Mapping[int, str]`."""

    def __init__(self, known: Mapping[int, str]) -> None:
        """Ghi nhớ bảng trang; tầng ngoài bảng vắng khoá như cổng thật của B2-04."""
        self.known = dict(known)

    async def load(self, db: object, floor_pks: Sequence[int]) -> Mapping[int, str]:
        """Chỉ trả những tầng cổng biết — không bịa khoá cho tầng lạ."""
        return {pk: self.known[pk] for pk in floor_pks if pk in self.known}


def use_pages(app: object, *sources: object) -> None:
    """Cài (hay gỡ) cổng `drawing_pages` cho **một** app test; không tham số = gỡ hẳn."""
    extensions.override(app, pages.SUBMODULE, [("apps.api.spatial_read.tests._read_helpers", tuple(sources))])


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
