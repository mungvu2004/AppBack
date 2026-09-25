"""N4 `members_remove_member` (B2-02 [2], [8]): C01 C06 C07 C08 C17 C18 + case theo việc."""

from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.access.kinds import ActivityKind
from apps.api.project_members.tests.support import headers_of, member_ids, remove, seed_project, updated_at
from packages.core.clock import SystemClock
from packages.core.ids import new_id
from packages.testing.factories.auth import make_user
from packages.testing.fixtures.access import activity_rows, assert_one_activity


async def test_members_remove_member__C01(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Gỡ viewer: 200 `UserOut` của người đó, hết membership, một dòng nhật ký, `updatedAt` đổi."""
    actor, target = await make_user(db_session, role="engineer"), await make_user(db_session, role="viewer")
    project = await seed_project(db_session, owner=actor, members=[target])
    before = await updated_at(db_session, project.id)
    response = await remove(api_client, actor, project.id, target.id)
    assert response.status_code == 200
    assert response.json() == {"id": target.id, "email": target.email, "name": target.name, "role": "viewer"}
    assert await member_ids(db_session, project.id) == [actor.id]
    await assert_one_activity(
        db_sessionmaker, actor_id=actor.id, kind=ActivityKind.MEMBER_REMOVE, object_code=target.id
    )
    assert await updated_at(db_session, project.id) != before


async def test_members_remove_member__C06(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Admin hệ thống không là thành viên → 404 `project`."""
    owner, outsider = await make_user(db_session, role="engineer"), await make_user(db_session, role="admin")
    project = await seed_project(db_session, owner=owner)
    response = await remove(api_client, outsider, project.id, owner.id)
    assert (response.status_code, response.json()["resource"]) == (404, "project")


async def test_members_remove_member__C07(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Viewer là thành viên → 403."""
    owner, viewer = await make_user(db_session, role="engineer"), await make_user(db_session, role="viewer")
    project = await seed_project(db_session, owner=owner, members=[viewer])
    response = await remove(api_client, viewer, project.id, owner.id)
    assert (response.status_code, response.json()["code"]) == (403, "FORBIDDEN")


async def test_members_remove_member__C08(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: Any
) -> None:
    """Dự án xoá mềm → 404 `project`; người không là thành viên của dự án còn sống → 404 `member`."""
    owner, stranger = await make_user(db_session, role="admin"), await make_user(db_session)
    dead = await seed_project(db_session, owner=owner, deleted_at=fake_clock.now())
    live = await seed_project(db_session, owner=owner)
    gone = await remove(api_client, owner, dead.id, owner.id)
    assert (gone.status_code, gone.json()["resource"]) == (404, "project")
    missing = await remove(api_client, owner, live.id, stranger.id)
    assert (missing.status_code, missing.json()["resource"]) == (404, "member")


async def test_members_remove_member__C17(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Người chưa có ảnh → không có khoá `avatarUrl`."""
    actor, target = await make_user(db_session, role="admin"), await make_user(db_session, role="viewer")
    project = await seed_project(db_session, owner=actor, members=[target])
    assert "avatarUrl" not in (await remove(api_client, actor, project.id, target.id)).json()


async def test_members_remove_member__C18(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Nhật ký ghi `actor_id` người gọi, `object_code` người bị gỡ, `project_id` đúng."""
    actor, target = await make_user(db_session, role="admin"), await make_user(db_session, role="viewer")
    project = await seed_project(db_session, owner=actor, members=[target])
    await remove(api_client, actor, project.id, target.id)
    rows = await activity_rows(db_sessionmaker, kind=ActivityKind.MEMBER_REMOVE)
    assert [(r.actor_id, r.object_code, r.project_id, r.object_label) for r in rows] == [
        (actor.id, target.id, project.id, target.email)
    ]


async def test_members_remove_member__bad_user_id(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """`{user_id}` sai mẫu → 404 `member`."""
    actor = await make_user(db_session, role="admin")
    project = await seed_project(db_session, owner=actor)
    response = await remove(api_client, actor, project.id, "khong-phai-id")
    assert (response.status_code, response.json()["resource"]) == (404, "member")


async def test_members_remove_member__takes_effect_immediately(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Sau khi bị gỡ, người đó gọi #24 → 404 ngay (`require_project` không cache)."""
    actor, target = await make_user(db_session, role="engineer"), await make_user(db_session, role="viewer")
    project = await seed_project(db_session, owner=actor, members=[target])
    path = f"/api/projects/{project.id}"
    assert (await api_client.get(path, headers=headers_of(target))).status_code == 200
    await remove(api_client, actor, project.id, target.id)
    assert (await api_client.get(path, headers=headers_of(target))).status_code == 404


async def test_members_remove_member__self_removal_with_other_editor(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Tự gỡ mình khi còn người sửa khác → 200."""
    actor, other = await make_user(db_session, role="engineer"), await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=actor, members=[other])
    assert (await remove(api_client, actor, project.id, actor.id)).status_code == 200
    assert await member_ids(db_session, project.id) == [other.id]


async def test_members_remove_member__engineer_removes_admin(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Kỹ sư gỡ được admin (M2) khi còn người sửa khác."""
    engineer, admin = await make_user(db_session, role="engineer"), await make_user(db_session, role="admin")
    project = await seed_project(db_session, owner=engineer, members=[admin])
    assert (await remove(api_client, engineer, project.id, admin.id)).status_code == 200


async def test_members_remove_member__last_editor_with_viewer_left(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Người sửa cuối, dù còn viewer khác → 422 `MEMBER_LAST_EDITOR`, không đổi gì."""
    actor, viewer = await make_user(db_session, role="engineer"), await make_user(db_session, role="viewer")
    project = await seed_project(db_session, owner=actor, members=[viewer])
    response = await remove(api_client, actor, project.id, actor.id)
    assert (response.status_code, response.json()["code"]) == (422, "MEMBER_LAST_EDITOR")
    assert await member_ids(db_session, project.id) == sorted([actor.id, viewer.id])


async def test_members_remove_member__unknown_user(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Id đúng mẫu mà không có người → 404 `member`."""
    actor = await make_user(db_session, role="admin")
    project = await seed_project(db_session, owner=actor)
    response = await remove(api_client, actor, project.id, new_id("usr", SystemClock()))
    assert (response.status_code, response.json()["resource"]) == (404, "member")
