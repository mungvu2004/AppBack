"""#41 `users_change_role`, #42 `users_disable_user`, #43 `users_enable_user` (B1-05 [6], [8]).

Loại A: C01 C02 C03 C07 C08 C17 C18 (+ C21 cho #41). Verifier giả cho hầu hết test (vai lấy từ
`Principal`, khoá tập admin đọc DB thật); hai test dùng verifier **thật** để kiểm token cũ bị
thu hồi (C25): access token của người bị đổi vai / vô hiệu nhận 401 `SESSION_REVOKED`.
"""

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.access.kinds import ActivityKind
from apps.api.auth_recovery.tests.support import seed_token
from apps.api.users.tests.support import USERS, count_tokens, make_admin, reload, second_client, send
from packages.db.models.access import ActivityLog
from packages.db.models.auth import RefreshSession, User
from packages.testing.factories.auth import TEST_PASSWORD, make_user
from packages.testing.fixtures.access import activity_rows, assert_one_activity
from packages.testing.fixtures.auth import ORIGIN, REFRESH_PATH, SignIn, login
from packages.testing.fixtures.clock import FakeClock

pytestmark = pytest.mark.usefixtures("api_env")

GHOST = "usr_01JABCDEFGHJKMNPQRSTVWXYZ0"
KEYS = {"email", "id", "lastActiveAt", "name", "projectCount", "role", "status"}


def _role_path(user_id: str) -> str:
    return f"{USERS}/{user_id}/role"


def _role_body(user: User | str, role: str = "viewer") -> dict[str, str]:
    """Thân #41: `userId` khớp đường (guard W21) trừ khi test cố tình lệch."""
    return {"role": role, "userId": user if isinstance(user, str) else user.id}


async def _wrote_nothing(
    sessionmaker: async_sessionmaker[AsyncSession], db: AsyncSession, user: User, before: int
) -> None:
    """Không đổi gì: không dòng nhật ký nào và `token_version` giữ nguyên."""
    assert await activity_rows(sessionmaker) == []
    assert (await reload(db, user.id)).token_version == before


# --------------------------------------------------------------------------- #41


async def test_users_change_role__C01(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Đổi vai → 200 `AdminUser` với vai mới, `token_version` tăng, một dòng nhật ký `user.role_change`."""
    admin, target = await make_admin(db_session), await make_user(db_session, role="engineer")
    response = await send(api_client, admin, "PATCH", _role_path(target.id), json=_role_body(target, "viewer"))
    assert response.status_code == 200
    assert response.json()["role"] == "viewer"
    stored = await reload(db_session, target.id)
    assert (stored.role, stored.token_version) == ("viewer", 1)
    row = await assert_one_activity(
        db_sessionmaker, actor_id=admin.id, kind=ActivityKind.USER_ROLE_CHANGE, object_code=target.id
    )
    assert row.object_label == target.email


async def test_users_change_role__C18(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Nhật ký: actor là người thực hiện (từ token), đúng `kind` và `objectCode`; nâng lên admin cũng ghi."""
    admin, target = await make_admin(db_session), await make_user(db_session, role="viewer")
    response = await send(api_client, admin, "PATCH", _role_path(target.id), json=_role_body(target, "admin"))
    assert response.status_code == 200
    await assert_one_activity(
        db_sessionmaker, actor_id=admin.id, kind=ActivityKind.USER_ROLE_CHANGE, object_code=target.id
    )


async def test_users_change_role__C17(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Người không có avatar/lời mời/hoạt động: khoá tuỳ chọn vắng, `lastActiveAt` có mặt là `null`."""
    admin, target = await make_admin(db_session), await make_user(db_session, role="engineer")
    body = (await send(api_client, admin, "PATCH", _role_path(target.id), json=_role_body(target))).json()
    assert set(body) == KEYS
    assert body["lastActiveAt"] is None


@pytest.mark.parametrize("bad", [{"role": "root", "userId": "x"}, {"role": 7, "userId": "x"}, {"userId": "x"}])
async def test_users_change_role__C02(
    api_client: httpx.AsyncClient, db_session: AsyncSession, bad: dict[str, object]
) -> None:
    """Vai sai giá trị/kiểu hoặc thiếu → 422 `VALIDATION`, không đổi gì."""
    admin, target = await make_admin(db_session), await make_user(db_session, role="engineer")
    bad = {**bad, "userId": target.id}
    response = await send(api_client, admin, "PATCH", _role_path(target.id), json=bad)
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"
    assert (await reload(db_session, target.id)).role == "engineer"


async def test_users_change_role__C03(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Khoá lạ trong thân → 422 `VALIDATION`."""
    admin, target = await make_admin(db_session), await make_user(db_session)
    response = await send(api_client, admin, "PATCH", _role_path(target.id), json={**_role_body(target), "x": 1})
    assert (response.status_code, response.json()["code"]) == (422, "VALIDATION")


@pytest.mark.parametrize("role", ["engineer", "viewer"])
async def test_users_change_role__C07(api_client: httpx.AsyncClient, db_session: AsyncSession, role: str) -> None:
    """Không phải admin → 403."""
    caller, target = await make_user(db_session, role=role), await make_user(db_session)
    response = await send(api_client, caller, "PATCH", _role_path(target.id), json=_role_body(target))
    assert (response.status_code, response.json()["code"]) == (403, "FORBIDDEN")


async def test_users_change_role__C08(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Không có người hoặc đã xoá mềm → 404 `resource:"user"`."""
    admin, gone = await make_admin(db_session), await make_user(db_session)
    await db_session.execute(update(User).where(User.id == gone.id).values(deleted_at=User.created_at))
    await db_session.commit()
    for user_id in (GHOST, gone.id):
        response = await send(api_client, admin, "PATCH", _role_path(user_id), json=_role_body(user_id))
        assert (response.status_code, response.json()["resource"]) == (404, "user")


async def test_users_change_role__C21(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """`userId` thân khác đường → 422 `PATH_BODY_MISMATCH`, không ghi gì (K09)."""
    admin, target, other = await make_admin(db_session), await make_user(db_session), await make_user(db_session)
    response = await send(api_client, admin, "PATCH", _role_path(target.id), json=_role_body(other, "viewer"))
    assert (response.status_code, response.json()["code"]) == (422, "PATH_BODY_MISMATCH")
    assert (await reload(db_session, other.id)).role == other.role


async def test_users_change_role_same_role_writes_nothing(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Đổi sang vai đang có → 200, không nhật ký, không tăng `token_version`."""
    admin, target = await make_admin(db_session), await make_user(db_session, role="engineer")
    response = await send(api_client, admin, "PATCH", _role_path(target.id), json=_role_body(target, "engineer"))
    assert (response.status_code, response.json()["role"]) == (200, "engineer")
    await _wrote_nothing(db_sessionmaker, db_session, target, 0)


async def test_users_change_role_self_is_rejected(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Tự đổi vai chính mình → 422 `USER_SELF_MODIFICATION`."""
    admin = await make_admin(db_session)
    response = await send(api_client, admin, "PATCH", _role_path(admin.id), json=_role_body(admin, "viewer"))
    assert (response.status_code, response.json()["code"]) == (422, "USER_SELF_MODIFICATION")
    assert (await reload(db_session, admin.id)).role == "admin"


async def test_users_change_role_actor_demoted_in_db_is_forbidden(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Vai vừa bị hạ trong DB (`Principal` còn `admin`, như cache ≤ 5 s) → 403 ở khoá tập admin, không ghi gì."""
    actor, other_admin, target = await make_admin(db_session), await make_admin(db_session), await make_user(db_session)
    await db_session.execute(update(User).where(User.id == actor.id).values(role="engineer"))
    await db_session.commit()
    actor.role = "admin"  # `Principal` dựng từ `user.role` — giữ vai cũ như cache chưa hết hạn
    response = await send(api_client, actor, "PATCH", _role_path(target.id), json=_role_body(target, "viewer"))
    assert (response.status_code, response.json()["code"]) == (403, "FORBIDDEN")
    assert (await reload(db_session, target.id)).role == target.role
    assert other_admin.role == "admin"


async def test_users_change_role_revokes_old_access_token(
    auth_app: FastAPI, auth_client: httpx.AsyncClient, db_session: AsyncSession, signed_in: SignIn
) -> None:
    """Hạ vai người đang đăng nhập: access token cũ 401 `SESSION_REVOKED`, refresh trả `roles` mới (C25)."""
    admin, victim = await make_admin(db_session), await make_user(db_session, role="engineer")
    admin_session = await signed_in(admin)
    async with second_client(auth_app) as victim_client:
        session = await signed_in(victim, client=victim_client)
        assert (await victim_client.get("/api/me", headers=session.headers)).status_code == 200
        changed = await auth_client.patch(
            _role_path(victim.id), json=_role_body(victim, "viewer"), headers=admin_session.headers
        )
        assert changed.status_code == 200
        stale = await victim_client.get("/api/me", headers=session.headers)
        assert (stale.status_code, stale.json()["code"]) == (401, "SESSION_REVOKED")
        refreshed = await victim_client.post(REFRESH_PATH, headers=ORIGIN)
        assert (refreshed.status_code, refreshed.json()["roles"]) == (200, ["viewer"])


# --------------------------------------------------------------------------- #42


def _path(user_id: str, action: str) -> str:
    return f"{USERS}/{user_id}/{action}"


async def test_users_disable_user__C01(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
) -> None:
    """Vô hiệu → `disabled`, phiên bị thu hồi, lời mời chờ mất hiệu lực, `token_version` tăng."""
    admin, target = await make_admin(db_session), await make_user(db_session, status="pending", password=None)
    await seed_token(db_session, user_id=target.id, purpose="invite", clock=fake_clock)
    response = await send(api_client, admin, "POST", _path(target.id, "disable"), json={})
    assert (response.status_code, response.json()["status"]) == (200, "disabled")
    assert "invitedAt" not in response.json()
    assert await count_tokens(db_session, target.id, live_only=True) == 0
    assert (await reload(db_session, target.id)).token_version == 1
    await assert_one_activity(db_sessionmaker, actor_id=admin.id, kind=ActivityKind.USER_DISABLE, object_code=target.id)


async def test_users_disable_user__C18(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Nhật ký `user.disable`: actor là admin, `objectLabel` là email mục tiêu."""
    admin, target = await make_admin(db_session), await make_user(db_session)
    await send(api_client, admin, "POST", _path(target.id, "disable"), json={})
    row = await assert_one_activity(
        db_sessionmaker, actor_id=admin.id, kind=ActivityKind.USER_DISABLE, object_code=target.id
    )
    assert row.object_label == target.email


async def test_users_disable_user__C17(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Khoá tuỳ chọn vắng, `lastActiveAt` là `null` có mặt."""
    admin, target = await make_admin(db_session), await make_user(db_session)
    body = (await send(api_client, admin, "POST", _path(target.id, "disable"), json={})).json()
    assert set(body) == KEYS
    assert body["lastActiveAt"] is None


async def test_users_disable_user__C02(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Thân không phải object (`[]`) → 422 `VALIDATION`."""
    admin, target = await make_admin(db_session), await make_user(db_session)
    response = await send(api_client, admin, "POST", _path(target.id, "disable"), json=[])
    assert (response.status_code, response.json()["code"]) == (422, "VALIDATION")
    assert (await reload(db_session, target.id)).status == "active"


async def test_users_disable_user__C03(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Khoá lạ trong thân → 422 `VALIDATION`."""
    admin, target = await make_admin(db_session), await make_user(db_session)
    response = await send(api_client, admin, "POST", _path(target.id, "disable"), json={"x": 1})
    assert (response.status_code, response.json()["code"]) == (422, "VALIDATION")


@pytest.mark.parametrize("role", ["engineer", "viewer"])
async def test_users_disable_user__C07(api_client: httpx.AsyncClient, db_session: AsyncSession, role: str) -> None:
    """Không phải admin → 403."""
    caller, target = await make_user(db_session, role=role), await make_user(db_session)
    response = await send(api_client, caller, "POST", _path(target.id, "disable"), json={})
    assert response.status_code == 403


async def test_users_disable_user__C08(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Không có người → 404 `resource:"user"`."""
    admin = await make_admin(db_session)
    response = await send(api_client, admin, "POST", _path(GHOST, "disable"), json={})
    assert (response.status_code, response.json()["resource"]) == (404, "user")


async def test_users_disable_user_twice_and_self(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Đã `disabled` → 200, không ghi thêm gì; tự vô hiệu mình → 422 `USER_SELF_MODIFICATION`."""
    admin, target = await make_admin(db_session), await make_user(db_session, status="disabled")
    response = await send(api_client, admin, "POST", _path(target.id, "disable"), json={})
    assert (response.status_code, response.json()["status"]) == (200, "disabled")
    await _wrote_nothing(db_sessionmaker, db_session, target, 0)
    own = await send(api_client, admin, "POST", _path(admin.id, "disable"), json={})
    assert (own.status_code, own.json()["code"]) == (422, "USER_SELF_MODIFICATION")


async def test_users_disable_user_kills_every_session(
    auth_app: FastAPI, auth_client: httpx.AsyncClient, db_session: AsyncSession, signed_in: SignIn
) -> None:
    """Mọi phiên của người bị vô hiệu chết: access token 401, refresh 401, đăng nhập lại 401 (C25)."""
    admin, victim = await make_admin(db_session), await make_user(db_session, role="engineer")
    admin_session = await signed_in(admin)
    async with second_client(auth_app) as victim_client:
        session = await signed_in(victim, client=victim_client)
        disabled = await auth_client.post(_path(victim.id, "disable"), json={}, headers=admin_session.headers)
        assert disabled.status_code == 200
        stale = await victim_client.get("/api/me", headers=session.headers)
        assert (stale.status_code, stale.json()["code"]) == (401, "SESSION_REVOKED")
        assert (await victim_client.post(REFRESH_PATH, headers=ORIGIN)).status_code == 401
        assert (await login(victim_client, victim.email, TEST_PASSWORD)).status_code == 403
    live = await db_session.execute(
        select(RefreshSession.id).where(RefreshSession.user_id == victim.id, RefreshSession.revoked_at.is_(None))
    )
    assert live.first() is None
    reasons = (
        await db_session.execute(select(RefreshSession.revoked_reason).where(RefreshSession.user_id == victim.id))
    ).scalars()
    assert "disabled" in set(reasons)


# --------------------------------------------------------------------------- #43


async def test_users_enable_user__C01(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Bật lại người có mật khẩu → `active`; người chưa có mật khẩu → `pending` (cần gửi lại lời mời)."""
    admin = await make_admin(db_session)
    with_password = await make_user(db_session, status="disabled")
    without_password = await make_user(db_session, status="disabled", password=None)
    first = await send(api_client, admin, "POST", _path(with_password.id, "enable"), json={})
    second = await send(api_client, admin, "POST", _path(without_password.id, "enable"), json={})
    assert (first.status_code, first.json()["status"]) == (200, "active")
    assert (second.status_code, second.json()["status"]) == (200, "pending")
    await assert_one_activity(
        db_sessionmaker, actor_id=admin.id, kind=ActivityKind.USER_ENABLE, object_code=with_password.id
    )


async def test_users_enable_user__C18(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Nhật ký `user.enable`: `objectLabel` là email mục tiêu."""
    admin, target = await make_admin(db_session), await make_user(db_session, status="disabled")
    await send(api_client, admin, "POST", _path(target.id, "enable"), json={})
    row = await assert_one_activity(
        db_sessionmaker, actor_id=admin.id, kind=ActivityKind.USER_ENABLE, object_code=target.id
    )
    assert row.object_label == target.email


async def test_users_enable_user__C17(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Khoá tuỳ chọn vắng, `lastActiveAt` là `null` có mặt."""
    admin, target = await make_admin(db_session), await make_user(db_session, status="disabled")
    body = (await send(api_client, admin, "POST", _path(target.id, "enable"), json={})).json()
    assert set(body) == KEYS
    assert body["lastActiveAt"] is None


async def test_users_enable_user__C02(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Thân không phải object → 422 `VALIDATION`."""
    admin, target = await make_admin(db_session), await make_user(db_session, status="disabled")
    response = await send(api_client, admin, "POST", _path(target.id, "enable"), json=[])
    assert (response.status_code, response.json()["code"]) == (422, "VALIDATION")


async def test_users_enable_user__C03(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Khoá lạ trong thân → 422 `VALIDATION`."""
    admin, target = await make_admin(db_session), await make_user(db_session, status="disabled")
    response = await send(api_client, admin, "POST", _path(target.id, "enable"), json={"x": 1})
    assert (response.status_code, response.json()["code"]) == (422, "VALIDATION")


@pytest.mark.parametrize("role", ["engineer", "viewer"])
async def test_users_enable_user__C07(api_client: httpx.AsyncClient, db_session: AsyncSession, role: str) -> None:
    """Không phải admin → 403."""
    caller, target = await make_user(db_session, role=role), await make_user(db_session, status="disabled")
    assert (await send(api_client, caller, "POST", _path(target.id, "enable"), json={})).status_code == 403


async def test_users_enable_user__C08(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Không có người → 404 `resource:"user"`."""
    admin = await make_admin(db_session)
    response = await send(api_client, admin, "POST", _path(GHOST, "enable"), json={})
    assert (response.status_code, response.json()["resource"]) == (404, "user")


async def test_users_enable_user_not_disabled_writes_nothing(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Bật người không `disabled` → 200 trả nguyên trạng, không nhật ký, không tăng `token_version`."""
    admin, target = await make_admin(db_session), await make_user(db_session)
    response = await send(api_client, admin, "POST", _path(target.id, "enable"), json={})
    assert (response.status_code, response.json()["status"]) == (200, "active")
    await _wrote_nothing(db_sessionmaker, db_session, target, 0)
    assert (await db_session.execute(select(ActivityLog.id))).first() is None
