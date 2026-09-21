"""`TokenVerifier` thật trên app thật (không tiêm Fake): token, phiên, cache (BE-00 §5, C05, C25)."""

import base64
import json
from contextlib import suppress
from datetime import timedelta
from typing import Final
from uuid import uuid4

import httpx
import jwt
import pytest
from fastapi import FastAPI
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth.services import AuthServices
from apps.api.auth.sessions import bump_token_version, principal_key, revoke_sessions
from apps.api.auth.settings import reset_auth_settings_cache
from apps.api.auth.stream_tokens import verify_stream_token
from apps.api.auth.tests.support import cookie_value, set_cookies, wait_until
from apps.api.auth.tokens import issue_token
from apps.api.auth.verifier import JwtTokenVerifier
from apps.api.core.app import create_app
from packages.core.clock import SystemClock
from packages.core.errors import AppError
from packages.core.keys import current_key
from packages.core.settings import get_core_settings
from packages.db.hooks import after_commit_idle
from packages.db.models.auth import User
from packages.db.settings import reset_database_settings_cache
from packages.messaging.redis import AsyncRedis
from packages.messaging.settings import reset_messaging_settings_cache
from packages.testing.factories.auth import TEST_PASSWORD, make_user
from packages.testing.fixtures.api import make_api_client
from packages.testing.fixtures.auth import PROBE_PATH, SignedIn, build_probe_app, login, sign_in
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.db import drop_after_commit
from packages.testing.fixtures.services import ephemeral_redis, refused_url

UNAUTHENTICATED: Final = "UNAUTHENTICATED"
SESSION_REVOKED: Final = "SESSION_REVOKED"


def _claims(me: SignedIn) -> dict[str, object]:
    """Claim thật của access token (đã kiểm chữ ký bằng khoá hiện hành)."""
    return dict(
        jwt.decode(
            me.access_token,
            current_key("access"),
            algorithms=["HS256"],
            audience="access",
            options={"verify_exp": False},
        )
    )


def _signed(claims: dict[str, object], key: bytes | None = None) -> str:
    """JWT HS256 dựng tay từ claim cho trước."""
    return jwt.encode(claims, key if key is not None else current_key("access"), algorithm="HS256")


def _unsigned(claims: dict[str, object]) -> str:
    """JWT `alg: none` — thứ mà một `jwt.decode` thiếu `algorithms` sẽ nhận."""

    def part(value: dict[str, object]) -> str:
        """Một đoạn base64url không đệm."""
        return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=").decode()

    return f"{part({'alg': 'none', 'typ': 'JWT'})}.{part(claims)}."


async def _probe(client: httpx.AsyncClient, token: str) -> httpx.Response:
    """Gọi route được bảo vệ mẫu bằng một access token."""
    return await client.get(PROBE_PATH, headers={"Authorization": f"Bearer {token}"})


async def _code(client: httpx.AsyncClient, token: str) -> tuple[int, str | None]:
    """(status, mã lỗi) của một lượt gọi route mẫu."""
    response = await _probe(client, token)
    return response.status_code, response.json().get("code")


async def test_real_token_gives_the_principal_from_the_database(
    probe_app: FastAPI, probe_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """`create_app` tự nhận `build_verifier`; `Principal` mang vai đọc từ DB, `sid` của phiên."""
    assert isinstance(probe_app.state.token_verifier, JwtTokenVerifier)
    user = await make_user(db_session, role="admin")
    me = await sign_in(probe_client, user)
    response = await _probe(probe_client, me.access_token)
    assert response.status_code == 200
    assert response.json() == {"userId": user.id, "sessionId": me.sid, "role": "admin"}


@pytest.mark.parametrize("variant", ["foreign_key", "stream_audience", "alg_none", "no_sid", "expired", "future_iat"])
async def test_bad_tokens_are_401_unauthenticated(
    probe_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock, variant: str
) -> None:
    """Khoá lạ, `aud="stream"`, `alg: none`, thiếu `sid`, `exp` quá theo `fake_clock`, `iat` ở tương lai → 401."""
    me = await sign_in(probe_client, await make_user(db_session))
    claims = _claims(me)
    now = int(fake_clock.now().timestamp())
    tokens = {
        "foreign_key": _signed(claims, b"k" * 32),
        "stream_audience": _signed(claims | {"aud": "stream"}),
        "alg_none": _unsigned(claims),
        "no_sid": _signed({key: value for key, value in claims.items() if key != "sid"}),
        "expired": _signed(claims | {"exp": now}),
        "future_iat": _signed(claims | {"iat": now + 31}),
    }
    assert await _code(probe_client, tokens[variant]) == (401, UNAUTHENTICATED)


@pytest.mark.parametrize(
    "change",
    [{"sub": "usr_khong-hop-le"}, {"sid": "khong-phai-uuid"}, {"ver": True}, {"ver": -1}, {"exp": "mai"}],
    ids=["sub", "sid", "ver-bool", "ver-am", "exp-chuoi"],
)
async def test_malformed_claims_are_401(
    probe_client: httpx.AsyncClient, db_session: AsyncSession, change: dict[str, object]
) -> None:
    """Claim đúng chữ ký mà sai kiểu hay sai mẫu → 401 `UNAUTHENTICATED`."""
    me = await sign_in(probe_client, await make_user(db_session))
    assert await _code(probe_client, _signed(_claims(me) | change)) == (401, UNAUTHENTICATED)


async def test_expiry_follows_the_injected_clock(
    probe_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Hết hạn theo `fake_clock` (không theo giờ thật): +600 s → 401."""
    me = await sign_in(probe_client, await make_user(db_session))
    assert (await _probe(probe_client, me.access_token)).status_code == 200
    fake_clock.advance(timedelta(seconds=600))
    assert await _code(probe_client, me.access_token) == (401, UNAUTHENTICATED)


async def test_clock_a_year_ahead_of_real_time_still_verifies(
    probe_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """`fake_clock` đặt sau giờ thật 1 năm: token còn hạn theo đồng hồ app vẫn qua (PyJWT không so giờ thật)."""
    fake_clock.set(SystemClock().now() + timedelta(days=365))
    me = await sign_in(probe_client, await make_user(db_session))
    assert (await _probe(probe_client, me.access_token)).status_code == 200


async def test_token_of_another_users_session_is_401(probe_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """`sub` hợp lệ mà `sid` là phiên của người khác → 401 `SESSION_REVOKED`."""
    me = await sign_in(probe_client, await make_user(db_session))
    other = await make_user(db_session)
    forged = _signed(_claims(me) | {"sub": other.id})
    assert await _code(probe_client, forged) == (401, SESSION_REVOKED)


async def test_unknown_session_id_is_401(probe_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Token hợp lệ mà `sid` không có phiên nào (đã bị dọn) → 401 `SESSION_REVOKED`."""
    me = await sign_in(probe_client, await make_user(db_session))
    assert await _code(probe_client, _signed(_claims(me) | {"sid": str(uuid4())})) == (401, SESSION_REVOKED)


async def test_revoked_session_is_401_right_after_commit(
    probe_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """C25: thu hồi phiên → cache bị xoá sau commit → 401 `SESSION_REVOKED` ngay lượt kế tiếp."""
    user = await make_user(db_session)
    me = await sign_in(probe_client, user)
    assert (await _probe(probe_client, me.access_token)).status_code == 200
    await revoke_sessions(db_session, user_id=user.id, reason="logout", clock=fake_clock)
    await db_session.commit()
    await after_commit_idle(db_session)
    assert await _code(probe_client, me.access_token) == (401, SESSION_REVOKED)


async def test_disabled_user_is_401_right_after_commit(
    probe_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """C25: vô hiệu người dùng (trạng thái + thu hồi phiên, như B1-05) → 401 ngay sau commit."""
    user = await make_user(db_session)
    me = await sign_in(probe_client, user)
    assert (await _probe(probe_client, me.access_token)).status_code == 200
    await db_session.execute(update(User).where(User.id == user.id).values(status="disabled"))
    assert await revoke_sessions(db_session, user_id=user.id, reason="disabled", clock=fake_clock) == [me.sid]
    await db_session.commit()
    await after_commit_idle(db_session)
    assert await _code(probe_client, me.access_token) == (401, SESSION_REVOKED)


async def test_bumped_token_version_is_401_right_after_commit(
    probe_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """C25: `bump_token_version` → mọi access token cũ 401 ngay sau commit."""
    user = await make_user(db_session)
    me = await sign_in(probe_client, user)
    assert (await _probe(probe_client, me.access_token)).status_code == 200
    await bump_token_version(db_session, user.id)
    await db_session.commit()
    await after_commit_idle(db_session)
    assert await _code(probe_client, me.access_token) == (401, SESSION_REVOKED)


async def test_failed_cache_drop_is_bounded_by_the_ttl(
    probe_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Xoá cache hỏng (callback sau commit bị bỏ): ảnh chụp cũ sống tối đa `AUTH_PRINCIPAL_CACHE_TTL_S` (1 s)."""
    monkeypatch.setenv("AUTH_PRINCIPAL_CACHE_TTL_S", "1")
    reset_auth_settings_cache()
    user = await make_user(db_session)
    me = await sign_in(probe_client, user)
    assert (await _probe(probe_client, me.access_token)).status_code == 200
    with drop_after_commit():
        await revoke_sessions(db_session, user_id=user.id, reason="logout", clock=fake_clock)
        await db_session.commit()
    assert (await _probe(probe_client, me.access_token)).status_code == 200

    async def revoked() -> bool:
        """Lượt gọi đã thấy phiên bị thu hồi."""
        return (await _probe(probe_client, me.access_token)).status_code == 401

    await wait_until(revoked, timeout_s=3.0)


async def test_demoted_role_applies_once_the_cache_expires(
    probe_client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hạ vai trong DB → `Principal.role` mới ngay khi ảnh chụp hết hạn (vai không nằm trong token)."""
    monkeypatch.setenv("AUTH_PRINCIPAL_CACHE_TTL_S", "1")
    reset_auth_settings_cache()
    user = await make_user(db_session, role="admin")
    me = await sign_in(probe_client, user)
    assert (await _probe(probe_client, me.access_token)).json()["role"] == "admin"
    await db_session.execute(update(User).where(User.id == user.id).values(role="viewer"))
    await db_session.commit()

    async def demoted() -> bool:
        """Lượt gọi đã mang vai mới."""
        return bool((await _probe(probe_client, me.access_token)).json().get("role") == "viewer")

    await wait_until(demoted, timeout_s=3.0)


@pytest.mark.parametrize(
    "garbage",
    [
        "{khong phai json",
        json.dumps({"userId": "u", "role": "admin"}),
        json.dumps({"userId": "u", "role": "owner", "ver": 0, "status": "active", "revoked": False}),
        json.dumps({"ver": "0", "revoked": False}),
    ],
    ids=["json-hong", "thieu-khoa", "vai-la", "sai-kieu"],
)
async def test_corrupt_cache_falls_back_to_the_database(
    probe_client: httpx.AsyncClient, db_session: AsyncSession, cache_client: AsyncRedis, garbage: str
) -> None:
    """Ảnh chụp hỏng → đọc Postgres, trả đúng `Principal`, không 503, không 401."""
    user = await make_user(db_session, role="engineer")
    me = await sign_in(probe_client, user)
    await cache_client.set(principal_key(me.sid), garbage)
    response = await _probe(probe_client, me.access_token)
    assert response.status_code == 200
    assert response.json()["role"] == "engineer"


async def test_cache_redis_down_reads_the_database(
    auth_env: None, fake_clock: FakeClock, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`redis-cache` dừng → verifier đọc Postgres, route bảo vệ vẫn 200."""
    user = await make_user(db_session)
    container = ephemeral_redis("allkeys-lru")
    host, port = container.get_container_host_ip(), container.get_exposed_port(6379)
    monkeypatch.setenv("REDIS_CACHE_URL", f"redis://{host}:{port}/0")
    reset_messaging_settings_cache()
    try:
        async with make_api_client(build_probe_app(fake_clock)) as client:
            me = await sign_in(client, user)
            container.stop()
            response = await _probe(client, me.access_token)
    finally:
        reset_messaging_settings_cache()
        with suppress(Exception):  # đã dừng ở giữa test: lượt dừng thứ hai ném `NotFound`
            container.stop()
    assert response.status_code == 200


async def test_postgres_down_is_503_not_401(
    auth_env: None, fake_clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C13: Postgres không nghe và cache trống → 503 `DEPENDENCY_UNAVAILABLE`, không đăng xuất người dùng."""
    monkeypatch.setenv("DATABASE_URL", f"{refused_url('postgresql+asyncpg')}/appback")
    reset_database_settings_cache()
    token, _ = issue_token(
        "access", user_id=f"usr_{'0' * 26}", sid=str(uuid4()), ver=0, now=fake_clock.now(), ttl_s=600
    )
    async with make_api_client(build_probe_app(fake_clock)) as client:
        response = await _probe(client, token)
    reset_database_settings_cache()
    assert response.status_code == 503
    assert response.json()["code"] == "DEPENDENCY_UNAVAILABLE"


async def test_stream_token_is_verified_on_its_own_key(
    auth_app: FastAPI, auth_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Cookie luồng: JWT `aud="stream"` khoá `stream`; access token không thay được; hết hạn theo `fake_clock`."""
    user = await make_user(db_session)
    logged = await login(auth_client, user.email, TEST_PASSWORD)
    stream = cookie_value(set_cookies(logged)["appback_stream"])
    services = AuthServices(auth_app)
    claims = verify_stream_token(services, stream)
    assert (claims.user_id, claims.ver) == (user.id, 0)
    access, _ = issue_token("access", user_id=user.id, sid=claims.sid, ver=0, now=fake_clock.now(), ttl_s=600)
    with pytest.raises(AppError, match=UNAUTHENTICATED):
        verify_stream_token(services, access)
    fake_clock.advance(timedelta(seconds=600))
    with pytest.raises(AppError, match=UNAUTHENTICATED):
        verify_stream_token(services, stream)


async def test_verifier_is_built_without_touching_resources(auth_env: None, fake_clock: FakeClock) -> None:
    """`build_verifier` chạy trong `create_app`, trước `lifespan`: dựng được khi chưa có sessionmaker hay Redis."""
    app = create_app(get_core_settings(), clock=fake_clock)
    assert isinstance(app.state.token_verifier, JwtTokenVerifier)
    assert not hasattr(app.state, "sessionmaker")
