"""`_checked(None)` khi dự án bị xoá mềm giữa cổng quyền và `UPDATE … RETURNING` (NO-136).

Đường đua thật (một request HTTP #26 chen giữa một request #27 khác) khó dựng bằng HTTP: cần
dừng request thứ nhất đúng lúc giữa `_live_project` và `_write_changes`. Test gọi thẳng
`_write_changes` trên một `Project` đã đọc trước (mô phỏng #26 đã qua cổng quyền), rồi xoá mềm
dòng đó bằng **session khác** trước khi gọi — mô phỏng #27 xen vào giữa hai bước của #26.
"""

from typing import cast

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.core.auth import Principal
from apps.api.projects.schemas import ProjectUpdateIn
from apps.api.projects.service import _write_changes
from packages.core.errors import AppError
from packages.db.models.projects import Project
from packages.testing.factories.auth import make_user
from packages.testing.factories.projects import make_project
from packages.testing.fixtures.clock import FakeClock


async def test_write_changes_raises_not_found_when_deleted_between_gate_and_update(
    db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """NO-136: `_checked(None)` ném 404 `resource:"project"` khi `UPDATE … RETURNING` không
    khớp dòng nào vì dự án đã bị xoá mềm ở một giao dịch khác sau khi cổng quyền đã cho qua."""
    async with db_sessionmaker() as setup:
        user = await make_user(setup)
        project = await make_project(setup, owner=user)
        await setup.commit()
        stale = cast("Project", await setup.get(Project, project.id))

        async with db_sessionmaker() as concurrent:
            await concurrent.execute(
                update(Project).where(Project.id == project.id).values(deleted_at=fake_clock.now())
            )
            await concurrent.commit()

        principal = Principal(user_id=user.id, session_id="sid-race", role="engineer")
        body = ProjectUpdateIn(name="Tên mới sau khi bị xoá")
        changes = {"name": body.name}

        with pytest.raises(AppError) as excinfo:
            await _write_changes(setup, stale, changes, principal, fake_clock)
        assert excinfo.value.code.code == "NOT_FOUND"
        assert excinfo.value.wire_params() == {"resource": "project"}
