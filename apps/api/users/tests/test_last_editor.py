"""G3-13: #41 hạ vai và #42 vô hiệu không được làm dự án mất người sửa cuối (`MEMBER_LAST_EDITOR`).

Kiểm dùng chung `require_editors_left` của `apps/api/project_members` (cùng khoá với N4).
"""

from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.project_members.tests.support import seed_project
from apps.api.users.tests.support import USERS, make_admin, reload, send
from packages.db.models.auth import User
from packages.testing.factories.auth import make_user
from packages.testing.fixtures.access import activity_rows

pytestmark = pytest.mark.usefixtures("api_env")


async def _demote(client: httpx.AsyncClient, actor: User, user_id: str, role: str = "viewer") -> httpx.Response:
    """#41 với tư cách `actor`."""
    return await send(client, actor, "PATCH", f"{USERS}/{user_id}/role", json={"role": role, "userId": user_id})


async def _disable(client: httpx.AsyncClient, actor: User, user_id: str) -> httpx.Response:
    """#42 với tư cách `actor`."""
    return await send(client, actor, "POST", f"{USERS}/{user_id}/disable", json={})


async def test_users_change_role_last_editor_is_rejected(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Hạ người sửa duy nhất (còn viewer) xuống viewer → 422 `MEMBER_LAST_EDITOR`, vai giữ nguyên, không ghi nhật ký."""
    admin, editor, viewer = (
        await make_admin(db_session),
        await make_user(db_session),
        await make_user(db_session, role="viewer"),
    )
    await seed_project(db_session, owner=editor, members=[viewer])
    response = await _demote(api_client, admin, editor.id)
    assert (response.status_code, response.json()["code"]) == (422, "MEMBER_LAST_EDITOR")
    stored = await reload(db_session, editor.id)
    assert (stored.role, stored.token_version) == ("engineer", 0)
    assert await activity_rows(db_sessionmaker) == []


async def test_users_change_role_editor_left_or_still_editor_is_allowed(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Còn người sửa khác → hạ được; người sửa duy nhất lên admin (vẫn sửa được) → được."""
    admin, first, second = await make_admin(db_session), await make_user(db_session), await make_user(db_session)
    await seed_project(db_session, owner=first, members=[second])
    alone = await make_user(db_session)
    await seed_project(db_session, owner=alone)
    assert (await _demote(api_client, admin, first.id)).status_code == 200
    assert (await _demote(api_client, admin, alone.id, "admin")).status_code == 200
    assert (await reload(db_session, first.id)).role == "viewer"
    assert (await reload(db_session, alone.id)).role == "admin"


async def test_users_disable_user_last_editor_is_rejected(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Vô hiệu người sửa duy nhất → 422 `MEMBER_LAST_EDITOR`; người sửa kia đã `disabled` thì không tính."""
    admin, editor, gone = (
        await make_admin(db_session),
        await make_user(db_session),
        await make_user(db_session, status="disabled"),
    )
    await seed_project(db_session, owner=editor, members=[gone])
    response = await _disable(api_client, admin, editor.id)
    assert (response.status_code, response.json()["code"]) == (422, "MEMBER_LAST_EDITOR")
    assert (await reload(db_session, editor.id)).status == "active"
    assert await activity_rows(db_sessionmaker) == []


async def test_users_disable_user_editor_left_or_project_deleted_is_allowed(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Còn người sửa khác → vô hiệu được; dự án đã xoá mềm không chặn; viewer không bao giờ bị chặn."""
    admin, first, second = await make_admin(db_session), await make_user(db_session), await make_user(db_session)
    await seed_project(db_session, owner=first, members=[second])
    alone, viewer = await make_user(db_session), await make_user(db_session, role="viewer")
    await seed_project(db_session, owner=alone, deleted_at=datetime(2026, 1, 1, tzinfo=UTC))
    await seed_project(db_session, owner=second, members=[viewer])
    for user in (first, alone, viewer):
        assert (await _disable(api_client, admin, user.id)).status_code == 200
        assert (await reload(db_session, user.id)).status == "disabled"
