"""#46 `users_delete_user` (B1-05 [6], [8]): xoá **mềm**, có thân `{confirmEmail, userId}` (W13).

Loại A: C01 C02 C03 C07 C08 C17 C18 C21 (+ C14 ở `test_concurrency.py`). Dự án mồ côi kiểm bằng
`caplog` (log `project_orphaned` chỉ ra **sau** commit) và bằng hàm công khai của B2-01.
"""

import logging

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.access.kinds import ActivityKind
from apps.api.auth_recovery.tests.support import seed_token
from apps.api.me.tests.support import seed_session
from apps.api.projects.memberships import count_projects_of_users
from apps.api.users.tests.support import USERS, count_tokens, make_admin, reload, send
from packages.db.models.auth import RefreshSession
from packages.testing.factories.auth import make_user
from packages.testing.factories.projects import make_project
from packages.testing.fixtures.access import assert_one_activity
from packages.testing.fixtures.clock import FakeClock

pytestmark = pytest.mark.usefixtures("api_env")

GHOST = "usr_01JABCDEFGHJKMNPQRSTVWXYZ0"
KEYS = {"email", "id", "lastActiveAt", "name", "projectCount", "role", "status"}


def _delete(user_id: str, confirm: str, *, body_id: str | None = None) -> dict[str, object]:
    """Tham số `json=` của #46; `body_id` để dựng thân `userId` lệch đường (C21)."""
    return {"confirmEmail": confirm, "userId": user_id if body_id is None else body_id}


async def test_users_delete_user__C01(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Xoá mềm: trả `AdminUser` trước khi xoá (còn `active`); DB `deleted_at` + `disabled`; phiên/lời mời thu hồi."""
    admin, target = await make_admin(db_session), await make_user(db_session, role="engineer")
    await seed_session(db_session, target, fake_clock)
    await seed_token(db_session, user_id=target.id, purpose="invite", clock=fake_clock)
    response = await send(api_client, admin, "DELETE", f"{USERS}/{target.id}", json=_delete(target.id, target.email))
    assert response.status_code == 200
    assert (response.json()["id"], response.json()["status"]) == (target.id, "active")
    stored = await reload(db_session, target.id)
    assert (stored.status, stored.token_version) == ("disabled", 1)
    assert stored.deleted_at is not None
    assert await count_tokens(db_session, target.id, live_only=True) == 0
    reasons = (
        await db_session.execute(select(RefreshSession.revoked_reason).where(RefreshSession.user_id == target.id))
    ).scalars()
    assert set(reasons) == {"deleted"}


async def test_users_delete_user__C18(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Nhật ký `user.delete` do admin thực hiện; `activity_log` của người bị xoá giữ nguyên."""
    admin, target = await make_admin(db_session), await make_user(db_session)
    await send(api_client, admin, "DELETE", f"{USERS}/{target.id}", json=_delete(target.id, target.email))
    row = await assert_one_activity(
        db_sessionmaker, actor_id=admin.id, kind=ActivityKind.USER_DELETE, object_code=target.id
    )
    assert row.object_label == target.email


async def test_users_delete_user__C17(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Khoá tuỳ chọn vắng, `lastActiveAt: null` có khoá."""
    admin, target = await make_admin(db_session), await make_user(db_session)
    body = (
        await send(api_client, admin, "DELETE", f"{USERS}/{target.id}", json=_delete(target.id, target.email))
    ).json()
    assert set(body) == KEYS
    assert body["lastActiveAt"] is None


@pytest.mark.parametrize("bad", [{"confirmEmail": 7}, {}])
async def test_users_delete_user__C02(
    api_client: httpx.AsyncClient, db_session: AsyncSession, bad: dict[str, object]
) -> None:
    """`confirmEmail` sai kiểu hoặc thiếu → 422 `VALIDATION`; không xoá."""
    admin, target = await make_admin(db_session), await make_user(db_session)
    response = await send(api_client, admin, "DELETE", f"{USERS}/{target.id}", json={**bad, "userId": target.id})
    assert (response.status_code, response.json()["code"]) == (422, "VALIDATION")
    assert (await reload(db_session, target.id)).deleted_at is None


async def test_users_delete_user__C03(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Khoá lạ trong thân → 422 `VALIDATION`."""
    admin, target = await make_admin(db_session), await make_user(db_session)
    body = {**_delete(target.id, target.email), "x": 1}
    response = await send(api_client, admin, "DELETE", f"{USERS}/{target.id}", json=body)
    assert (response.status_code, response.json()["code"]) == (422, "VALIDATION")


@pytest.mark.parametrize("role", ["engineer", "viewer"])
async def test_users_delete_user__C07(api_client: httpx.AsyncClient, db_session: AsyncSession, role: str) -> None:
    """Không phải admin → 403; không xoá."""
    caller, target = await make_user(db_session, role=role), await make_user(db_session)
    response = await send(api_client, caller, "DELETE", f"{USERS}/{target.id}", json=_delete(target.id, target.email))
    assert response.status_code == 403
    assert (await reload(db_session, target.id)).deleted_at is None


async def test_users_delete_user__C08(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Không có người, hoặc đã xoá rồi → 404 `resource:"user"`."""
    admin, target = await make_admin(db_session), await make_user(db_session)
    await send(api_client, admin, "DELETE", f"{USERS}/{target.id}", json=_delete(target.id, target.email))
    for user_id in (GHOST, target.id):
        response = await send(api_client, admin, "DELETE", f"{USERS}/{user_id}", json=_delete(user_id, target.email))
        assert (response.status_code, response.json()["resource"]) == (404, "user")


async def test_users_delete_user__C21(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """`userId` thân khác đường → 422 `PATH_BODY_MISMATCH`, không xoá ai (K09)."""
    admin, target, other = await make_admin(db_session), await make_user(db_session), await make_user(db_session)
    body = _delete(target.id, target.email, body_id=other.id)
    response = await send(api_client, admin, "DELETE", f"{USERS}/{target.id}", json=body)
    assert (response.status_code, response.json()["code"]) == (422, "PATH_BODY_MISMATCH")
    assert (await reload(db_session, target.id)).deleted_at is None
    assert (await reload(db_session, other.id)).deleted_at is None


async def test_users_delete_user_confirm_email_is_compared_normalized(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """`confirmEmail` khác hoa thường vẫn khớp (200); khác hẳn → 422 `USER_CONFIRM_EMAIL_MISMATCH`."""
    admin = await make_admin(db_session)
    lower = await make_user(db_session, email="Nguoi.Xoa@Example.com")
    other = await make_user(db_session)
    wrong = await send(api_client, admin, "DELETE", f"{USERS}/{other.id}", json=_delete(other.id, "sai@example.com"))
    assert (wrong.status_code, wrong.json()["code"], wrong.json()["field"]) == (
        422,
        "USER_CONFIRM_EMAIL_MISMATCH",
        "confirmEmail",
    )
    assert (await reload(db_session, other.id)).deleted_at is None
    ok = await send(api_client, admin, "DELETE", f"{USERS}/{lower.id}", json=_delete(lower.id, "NGUOI.XOA@example.COM"))
    assert ok.status_code == 200


async def test_users_delete_user_self_is_rejected(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Tự xoá chính mình → 422 `USER_SELF_MODIFICATION`."""
    admin = await make_admin(db_session)
    response = await send(api_client, admin, "DELETE", f"{USERS}/{admin.id}", json=_delete(admin.id, admin.email))
    assert (response.status_code, response.json()["code"]) == (422, "USER_SELF_MODIFICATION")
    assert (await reload(db_session, admin.id)).deleted_at is None


async def test_users_delete_user_disappears_from_list_and_frees_email(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Sau xoá: #38 không còn người đó (và `total` giảm); mời lại cùng email ra người mới có `id` khác."""
    admin, target = await make_admin(db_session), await make_user(db_session, email="tai-su-dung@example.com")
    await send(api_client, admin, "DELETE", f"{USERS}/{target.id}", json=_delete(target.id, target.email))
    listing = (await send(api_client, admin, "GET", USERS)).json()
    assert (listing["total"], [row["id"] for row in listing["users"]]) == (1, [admin.id])
    invited = await send(
        api_client,
        admin,
        "POST",
        f"{USERS}/invitations",
        json={"emails": ["tai-su-dung@example.com"], "role": "viewer"},
    )
    assert invited.status_code == 201
    assert invited.json()[0]["id"] != target.id


async def test_users_delete_user_removes_memberships_and_logs_orphans(
    api_client: httpx.AsyncClient, db_session: AsyncSession, caplog: pytest.LogCaptureFixture
) -> None:
    """Gỡ khỏi mọi dự án; dự án chỉ còn người này là người sửa → log `project_orphaned` (không chặn xoá)."""
    admin, target, peer = await make_admin(db_session), await make_user(db_session), await make_user(db_session)
    orphan = await make_project(db_session, owner=target)
    shared = await make_project(db_session, owner=target, members=[peer])
    await db_session.commit()
    with caplog.at_level(logging.WARNING, logger="apps.api.users.service"):
        response = await send(
            api_client, admin, "DELETE", f"{USERS}/{target.id}", json=_delete(target.id, target.email)
        )
    assert (response.status_code, response.json()["projectCount"]) == (200, 2)
    assert (await count_projects_of_users(db_session, [target.id]))[target.id] == 0
    logged = [record for record in caplog.records if record.getMessage() == "project_orphaned"]
    assert [(r.projectId, r.userId) for r in logged] == [(orphan.id, target.id)]  # type: ignore[attr-defined]  # `extra` của log
    assert shared.id not in {r.projectId for r in logged}  # type: ignore[attr-defined]  # `extra` của log


@pytest.mark.parametrize(("local", "fold_char"), [("ksu", chr(0x212A)), ("sa", chr(0x17F))])
async def test_users_delete_user_confirm_email_rejects_non_ascii_folding(
    api_client: httpx.AsyncClient, db_session: AsyncSession, local: str, fold_char: str
) -> None:
    """`confirmEmail` có Kelvin U+212A hay U+017F gấp về email mục tiêu → 422 `VALIDATION`, không xoá (K37)."""
    admin = await make_admin(db_session)
    target = await make_user(db_session, email=f"{local}@example.com")
    confirm = target.email.replace(local[0], fold_char)
    assert confirm != target.email
    body = _delete(target.id, confirm)
    response = await send(api_client, admin, "DELETE", f"{USERS}/{target.id}", json=body)
    assert (response.status_code, response.json()["code"], response.json()["field"]) == (
        422,
        "VALIDATION",
        "confirmEmail",
    )
    assert (await reload(db_session, target.id)).deleted_at is None
