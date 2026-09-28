"""#22 `notifications_accept_invite` (B4-02 [8]): G* — C01 C02 C03 C08 C17 C23, cộng test đặt tên theo việc."""

import asyncio
from datetime import timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.notifications.tests.support import accept_path, post_json, remove_member, rows_of, seed_project
from packages.db.models.projects import ProjectMembership
from packages.testing.factories.auth import make_user
from packages.testing.factories.notifications import make_notification
from packages.testing.fixtures.clock import FakeClock


async def _invite(db: AsyncSession, **kwargs: Any) -> tuple[Any, Any, Any]:
    """(người nhận, dự án, lời mời chưa đọc); người nhận là `viewer` để thấy rõ không ai đổi vai."""
    owner, user = await make_user(db, role="admin"), await make_user(db, role="viewer")
    project = await seed_project(db, owner=owner, members=[user], **kwargs)
    row = await make_notification(
        db,
        user=user,
        project=project,
        kind="projectInvite",
        place="projectSettings",
        floor_level_id=None,
        stream_id=None,
    )
    await db.commit()
    return user, project, row


def _not_found(response: httpx.Response) -> tuple[int, str, str]:
    """(status, code, resource) của thân 404."""
    body = response.json()
    return response.status_code, body["code"], body["resource"]


async def test_notifications_accept_invite__C01(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """200 `Notification` với `isRead: true`; dòng đã đọc trong DB; không có `userId`, `dedupeKey`, `streamId`."""
    user, project, row = await _invite(db_session)

    response = await post_json(api_client, user, accept_path(row.id), {})

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "id": row.id,
        "kind": "projectInvite",
        "place": "projectSettings",
        "projectId": project.id,
        "projectName": project.name,
        "objectLabel": project.name,
        "message": "bạn vừa được thêm vào dự án",
        "isRead": True,
        "createdAt": body["createdAt"],
    }
    assert (await rows_of(db_session, user.id))[0].is_read


@pytest.mark.parametrize("body", [[], "x", 7])
async def test_notifications_accept_invite__C02(
    api_client: httpx.AsyncClient, db_session: AsyncSession, body: Any
) -> None:
    """Thân `[]` (hay không phải object) → 422 `VALIDATION`."""
    user, _, row = await _invite(db_session)
    response = await post_json(api_client, user, accept_path(row.id), body)
    assert (response.status_code, response.json()["code"]) == (422, "VALIDATION")


async def test_notifications_accept_invite__C03(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Khoá lạ → 422 `VALIDATION`; dòng vẫn chưa đọc."""
    user, _, row = await _invite(db_session)
    response = await post_json(api_client, user, accept_path(row.id), {"x": 1})
    assert (response.status_code, response.json()["code"]) == (422, "VALIDATION")
    assert not (await rows_of(db_session, user.id))[0].is_read


@pytest.mark.parametrize("notification_id", ["ntf_01ARZ3NDEKTSV4RRFFQ69G5FAV", "khong-phai-mau-id", "ntf_"])
async def test_notifications_accept_invite__C08_unknown_id(
    api_client: httpx.AsyncClient, db_session: AsyncSession, notification_id: str
) -> None:
    """Id không có, hoặc sai mẫu → 404 `resource:"notification"`."""
    user = await make_user(db_session)
    response = await post_json(api_client, user, accept_path(notification_id), {})
    assert _not_found(response) == (404, "NOT_FOUND", "notification")


async def test_notifications_accept_invite__C08_project_deleted(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Thông báo của dự án đã xoá mềm → 404."""
    user, _, row = await _invite(db_session, deleted_at=fake_clock.now() - timedelta(days=1))
    response = await post_json(api_client, user, accept_path(row.id), {})
    assert _not_found(response) == (404, "NOT_FOUND", "notification")


async def test_notifications_accept_invite__C08_removed_member(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Người gọi đã bị gỡ khỏi dự án → 404 (không 403), dòng không đổi."""
    user, project, row = await _invite(db_session)
    await remove_member(db_session, project, user)
    response = await post_json(api_client, user, accept_path(row.id), {})
    assert _not_found(response) == (404, "NOT_FOUND", "notification")
    assert not (await rows_of(db_session, user.id))[0].is_read


async def test_notifications_accept_invite__C17(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Lời mời không có `floorId`, `excerpt` (vắng khoá, không `null`)."""
    user, _, row = await _invite(db_session)
    body = (await post_json(api_client, user, accept_path(row.id), {})).json()
    assert "floorId" not in body
    assert "excerpt" not in body


async def test_notifications_accept_invite__C23(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Thông báo của người khác (cùng dự án) → 404; dòng của họ không đổi."""
    owner, other = await make_user(db_session, role="admin"), await make_user(db_session)
    project = await seed_project(db_session, owner=owner, members=[other])
    row = await make_notification(
        db_session, user=other, project=project, kind="projectInvite", place="projectSettings", floor_level_id=None
    )
    await db_session.commit()

    response = await post_json(api_client, owner, accept_path(row.id), {})

    assert _not_found(response) == (404, "NOT_FOUND", "notification")
    assert not (await rows_of(db_session, other.id))[0].is_read


async def test_notifications_accept_invite__twice_same_body(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Gọi hai lần → hai 200 cùng thân; lần hai không ghi (`updated_at` giữ nguyên)."""
    user, _, row = await _invite(db_session)
    first = await post_json(api_client, user, accept_path(row.id), {})
    stamp = (await rows_of(db_session, user.id))[0].updated_at
    second = await post_json(api_client, user, accept_path(row.id), {})
    assert (first.status_code, second.status_code) == (200, 200)
    assert first.json() == second.json()
    assert (await rows_of(db_session, user.id))[0].updated_at == stamp


async def test_notifications_accept_invite__parallel(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Hai lượt song song → cả hai 200, cùng thân."""
    user, _, row = await _invite(db_session)
    first, second = await asyncio.gather(
        post_json(api_client, user, accept_path(row.id), {}), post_json(api_client, user, accept_path(row.id), {})
    )
    assert (first.status_code, second.status_code) == (200, 200)
    assert first.json() == second.json()
    assert first.json()["isRead"] is True


async def test_notifications_accept_invite__already_read_still_200(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """FE luôn hiện nút chấp nhận kể cả khi đã đọc: dòng `is_read` sẵn vẫn 200."""
    user, _, row = await _invite(db_session)
    await post_json(api_client, user, "/api/notifications/read", {"ids": [row.id]})
    response = await post_json(api_client, user, accept_path(row.id), {})
    assert (response.status_code, response.json()["isRead"]) == (200, True)


async def test_notifications_accept_invite__not_an_invite(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """`aiCompleted` → 422 `NOTIFICATION_NOT_INVITE`; dòng vẫn chưa đọc."""
    owner = await make_user(db_session, role="admin")
    project = await seed_project(db_session, owner=owner)
    row = await make_notification(db_session, user=owner, project=project)
    await db_session.commit()
    response = await post_json(api_client, owner, accept_path(row.id), {})
    assert (response.status_code, response.json()["code"]) == (422, "NOTIFICATION_NOT_INVITE")
    assert not (await rows_of(db_session, owner.id))[0].is_read


async def test_notifications_accept_invite__does_not_touch_membership(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """#22 không đổi thành viên hay vai (M1: N3 đã thêm)."""
    user, _, row = await _invite(db_session)
    stmt = select(ProjectMembership.user_id, ProjectMembership.added_by)
    before = (await db_session.execute(stmt)).all()
    await post_json(api_client, user, accept_path(row.id), {})
    after = (await db_session.execute(stmt)).all()
    assert sorted(before) == sorted(after)
