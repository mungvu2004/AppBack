"""`_checked(None)` khi dự án bị xoá mềm giữa cổng quyền và `UPDATE … RETURNING` (NO-136).

Đường đua thật (một request HTTP #26 chen giữa một request #27 khác) khó dựng bằng HTTP: cần
dừng request thứ nhất đúng lúc giữa `_live_project` và `_write_changes`. Test gọi thẳng
`_write_changes` trên một `Project` đã đọc trước (mô phỏng #26 đã qua cổng quyền), rồi xoá mềm
dòng đó bằng **session khác** trước khi gọi — mô phỏng #27 xen vào giữa hai bước của #26.
"""

from types import SimpleNamespace
from typing import cast

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.core.auth import Principal
from apps.api.projects.schemas import ProjectUpdateIn
from apps.api.projects.service import _project_outs, _storage_of, _write_changes
from apps.api.projects.tests.test_wire import _project, _rollup, _user
from packages.core.errors import AppError
from packages.db.models.projects import Project
from packages.storage.keys import avatar
from packages.storage.local import LocalDiskStorage
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


async def test_storage_of__raises_when_app_has_no_storage() -> None:
    """NO-194: có `app` mà thiếu `app.state.storage` → ném ngay, không lặng lẽ `None` làm mất `avatarUrl`."""
    with pytest.raises(AttributeError):
        _storage_of(SimpleNamespace(state=SimpleNamespace()))


async def test_storage_of__none_without_app_and_returns_state_storage() -> None:
    """NO-194: `app=None` → `None`; có app → đúng `app.state.storage`."""
    sentinel = object()
    assert _storage_of(None) is None
    assert _storage_of(SimpleNamespace(state=SimpleNamespace(storage=sentinel))) is sentinel


async def test_project_outs__splits_the_signed_batch_back_per_project(local_storage: LocalDiskStorage) -> None:
    """NO-207: avatar của thành viên ký một lô rồi chia lại đúng dự án, kể cả dự án 0 thành viên."""
    first, empty, last = _project(), _project(), _project()
    first.id, empty.id, last.id = "prj_" + "1" * 26, "prj_" + "2" * 26, "prj_" + "3" * 26
    users = [_user(f"U{n}") for n in range(3)]
    for n, user in enumerate(users):
        user.id = f"usr_{n:026d}"
        user.avatar_key = avatar(user.id, "0" * 26, "png")
    members = {first.id: users[:2], empty.id: [], last.id: users[2:]}
    rollups = {p.id: _rollup() for p in (first, empty, last)}

    outs = await _project_outs([first, empty, last], members, rollups, {}, local_storage)

    assert [[m.name for m in out.members] for out in outs] == [["U0", "U1"], [], ["U2"]]
    assert all(m.avatar_url for out in outs for m in out.members)
