"""`POST /api/me/password` — N13 `me_change_password` (B1-04 [6], [8]; CASE loại G*: C01 C02 C03,
C11 cố định qua `row_id="N13"` của `tools/case_gate.py`)."""

import asyncio
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.auth.passwords import hash_password, verify_password
from apps.api.auth.tests.support import user_row
from apps.api.auth_recovery.tests.support import seed_token
from apps.api.core.ratelimit import install
from apps.api.me import router
from apps.api.me.router import PASSWORD_RATE_LIMIT
from apps.api.me.tests.support import headers_of, principal_of, seed_session
from packages.db.models.auth import RefreshSession, User
from packages.messaging.redis import cache_redis
from packages.testing.factories.auth import TEST_PASSWORD, make_user
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.services import refused_url
from packages.testing.fixtures.storage import PUBLIC_BASE_URL

pytestmark = pytest.mark.usefixtures("api_env")

PATH = "/api/me/password"
NEW_PASSWORD = "mat-khau-moi-cho-chinh-minh"  # noqa: S105 — mật khẩu giả của test
OTHER_PASSWORD = "mat-khau-khac-han-01"  # noqa: S105 — mật khẩu giả của test


async def _change(
    client: httpx.AsyncClient, headers: dict[str, str], *, current: str = TEST_PASSWORD
) -> httpx.Response:
    return await client.post(PATH, json={"currentPassword": current, "newPassword": NEW_PASSWORD}, headers=headers)


async def _session_row(db: AsyncSession, session_id: str) -> RefreshSession:
    """Dòng `refresh_sessions` đọc mới từ DB (`db_session` không tự hết hạn cache — `expire_on_commit=False`)."""
    row = await db.get_one(RefreshSession, UUID(session_id))
    await db.refresh(row)
    return row


async def test_me_change_password__C01(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Đúng: 204 rỗng, thu hồi phiên **khác**, phiên hiện tại vẫn sống."""
    user = await make_user(db_session)
    current = await seed_session(db_session, user, fake_clock)
    other = await seed_session(db_session, user, fake_clock)
    response = await _change(api_client, headers_of(current))
    assert response.status_code == 204
    assert response.content == b""

    current_row = await _session_row(db_session, current.session_id)
    other_row = await _session_row(db_session, other.session_id)
    assert current_row.revoked_at is None
    assert other_row.revoked_at is not None


@pytest.mark.parametrize("bad_body", [{"newPassword": "ngan"}, {"currentPassword": ""}])
async def test_me_change_password__C02(
    api_client: httpx.AsyncClient, db_session: AsyncSession, bad_body: dict[str, str]
) -> None:
    """Mật khẩu mới < 8 ký tự hay mật khẩu hiện tại rỗng → 422 `VALIDATION`."""
    user = await make_user(db_session)
    payload = {"currentPassword": TEST_PASSWORD, "newPassword": NEW_PASSWORD, **bad_body}
    response = await api_client.post(PATH, json=payload, headers=headers_of(principal_of(user)))
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"


async def test_me_change_password__C03(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Khoá lạ → 422 `VALIDATION`."""
    user = await make_user(db_session)
    payload = {"currentPassword": TEST_PASSWORD, "newPassword": NEW_PASSWORD, "extra": 1}
    response = await api_client.post(PATH, json=payload, headers=headers_of(principal_of(user)))
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"


async def test_me_change_password__C11(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Vượt `me_password` (5/15 phút) → 429."""
    user = await make_user(db_session)
    headers = headers_of(principal_of(user))
    for _ in range(PASSWORD_RATE_LIMIT):
        response = await _change(api_client, headers, current="sai")
        assert response.status_code == 422
    blocked = await _change(api_client, headers, current="sai")
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "RATE_LIMITED"


async def test_me_change_password_wrong_current_is_422_not_401(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Sai mật khẩu hiện tại → 422 `CURRENT_PASSWORD_INCORRECT`, không bao giờ 401 (K30)."""
    user = await make_user(db_session)
    principal = await seed_session(db_session, user, fake_clock)
    response = await _change(api_client, headers_of(principal), current="sai-hoan-toan")
    assert response.status_code == 422
    assert response.json()["code"] == "CURRENT_PASSWORD_INCORRECT"
    assert response.json()["field"] == "currentPassword"


async def test_me_change_password_success_then_old_password_rejected(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Đổi xong: mật khẩu mới băm đúng, mật khẩu cũ không còn khớp."""
    user = await make_user(db_session)
    principal = await seed_session(db_session, user, fake_clock)
    ok = await _change(api_client, headers_of(principal))
    assert ok.status_code == 204
    row = await user_row(db_session, user.id)
    assert await verify_password(row.password_hash, NEW_PASSWORD) is True
    assert await verify_password(row.password_hash, TEST_PASSWORD) is False


async def test_me_change_password_current_session_revoked_in_db_is_401(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
) -> None:
    """Phiên hiện tại đã bị thu hồi trong DB → 401, mật khẩu không đổi."""
    user = await make_user(db_session)
    principal = await seed_session(db_session, user, fake_clock)
    async with db_sessionmaker() as setup:
        await setup.execute(
            update(RefreshSession)
            .where(RefreshSession.id == UUID(principal.session_id))
            .values(revoked_at=fake_clock.now(), revoked_reason="logout")
        )
        await setup.commit()
    response = await _change(api_client, headers_of(principal))
    assert response.status_code == 401
    assert response.json()["code"] == "SESSION_REVOKED"
    row = await user_row(db_session, user.id)
    assert await verify_password(row.password_hash, TEST_PASSWORD) is True


async def test_me_change_password_concurrent_reset_wins_is_422_password_unchanged(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mật khẩu bị đổi trực tiếp (giả N9) giữa lúc N13 đang băm → N13 422, mật khẩu không bị đè."""
    user = await make_user(db_session)
    principal = await seed_session(db_session, user, fake_clock)
    started, proceed = asyncio.Event(), asyncio.Event()

    async def _blocking_hash(password: str) -> str:
        """Bọc `hash_password` thật: báo đã tới điểm băm rồi chờ test mở khoá."""
        started.set()
        await proceed.wait()
        return await hash_password(password)

    monkeypatch.setattr(router, "hash_password", _blocking_hash)
    task = asyncio.create_task(_change(api_client, headers_of(principal)))
    await started.wait()
    async with db_sessionmaker() as setup:
        other_hash = await hash_password(OTHER_PASSWORD)
        await setup.execute(update(User).where(User.id == user.id).values(password_hash=other_hash))
        await setup.commit()
    proceed.set()
    response = await task
    assert response.status_code == 422
    assert response.json()["code"] == "CURRENT_PASSWORD_INCORRECT"
    row = await user_row(db_session, user.id)
    assert await verify_password(row.password_hash, OTHER_PASSWORD) is True


async def test_me_change_password_session_revoked_when_user_deleted(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Người của `Principal` đã xoá mềm → 401, không băm mật khẩu."""
    user = await make_user(db_session)
    user.deleted_at = user.created_at
    await db_session.commit()
    response = await _change(api_client, headers_of(principal_of(user)))
    assert response.status_code == 401
    assert response.json()["code"] == "SESSION_REVOKED"


async def test_me_change_password_invalidates_pending_password_reset_token(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Sau N13, token `password_reset` còn hạn trước đó bị N9 dùng → 422 (`revoke_tokens`)."""
    user = await make_user(db_session)
    principal = await seed_session(db_session, user, fake_clock)
    _, plain = await seed_token(db_session, user_id=user.id, purpose="password_reset", clock=fake_clock)

    assert (await _change(api_client, headers_of(principal))).status_code == 204

    confirm = await api_client.post(
        "/api/auth/password-reset/confirm",
        json={"token": plain, "newPassword": "mat-khau-khong-quan-trong"},
        headers={"Origin": PUBLIC_BASE_URL},
    )
    assert confirm.status_code == 422


async def test_me_change_password_safe_redis_down_is_503(
    api_client: httpx.AsyncClient, api_app: FastAPI, db_session: AsyncSession
) -> None:
    """DB an toàn (`redis-broker`, kho `safe`) chết → rate limit `me_password` đóng, 503 (NO-167, C13).

    Hỏng hóc dựng bằng client thật trỏ vào một cổng không ai nghe (`refused_url`), như
    `apps/api/core/tests/test_ratelimit.py::test_redis_down_is_503_when_closed_and_passes_when_open`
    — không mock Redis (K23). `cache` vẫn là client thật để không ảnh hưởng hạn mức khác của app.
    """
    user = await make_user(db_session)
    dead = refused_url("redis")
    install(api_app, cache=cache_redis(), safe=Redis.from_url(dead, socket_connect_timeout=1))
    response = await _change(api_client, headers_of(principal_of(user)))
    assert response.status_code == 503
    assert response.json()["code"] == "DEPENDENCY_UNAVAILABLE"
