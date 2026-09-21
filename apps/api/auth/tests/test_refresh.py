"""`POST /api/auth/refresh` (BE-BIND #3, BE-00 §5 thuật toán refresh; CASE loại R)."""

import asyncio
import logging
from contextlib import suppress
from datetime import timedelta
from typing import Final
from uuid import UUID, uuid4

import httpx
import jwt
import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.responses import Response

from apps.api.auth import sessions
from apps.api.auth.cookies import REFRESH_COOKIE, STREAM_COOKIE
from apps.api.auth.sessions import RefreshDenied, Refreshed, refresh_session, start_session
from apps.api.auth.settings import get_auth_settings, reset_auth_settings_cache
from apps.api.auth.tests.support import (
    cookie_value,
    refresh_cookie,
    refresh_with,
    session_row,
    set_cookies,
    user_row,
    wait_until,
)
from apps.api.auth.tokens import new_refresh_token
from apps.api.core.app import create_app
from packages.core.keys import current_key
from packages.core.logging import JsonFormatter
from packages.core.settings import get_core_settings, reset_settings_cache
from packages.db.hooks import after_commit_idle
from packages.db.models.auth import User
from packages.db.settings import reset_database_settings_cache
from packages.messaging.settings import reset_messaging_settings_cache
from packages.testing.factories.auth import TEST_PASSWORD, make_user
from packages.testing.fixtures.api import make_api_client
from packages.testing.fixtures.auth import PROBE_PATH, login
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.services import ephemeral_redis, refused_url
from packages.testing.fixtures.storage import STORAGE_SECRET

_log: Final = logging.getLogger(__name__)

GRACE: Final = timedelta(seconds=31)
PARALLEL: Final = 5
JUNK_ATTEMPTS: Final = 30
ROTATED_SECRET: Final = "khoa-bi-mat-moi-sau-khi-xoay-vong-0002"  # noqa: S105 — khoá giả của test
W16_KEYS: Final = {"accessToken", "expiresAt", "roles", "user"}
CLAIMS: Final = {"sub", "sid", "ver", "iat", "exp", "aud"}


async def _logged_in(client: httpx.AsyncClient, user: User, *, remember: bool = True) -> str:
    """Đăng nhập thật; trả cookie refresh T0 (chưa xoay lần nào)."""
    response = await login(client, user.email, TEST_PASSWORD, remember=remember)
    assert response.status_code == 204, response.text
    return refresh_cookie(response)


def _sid(cookie: str) -> str:
    """`sid` của một giá trị cookie refresh."""
    return cookie.split(".", 1)[0]


async def test_auth_refresh__C01(auth_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Đúng: 200 thân W16 đúng khoá, claim đúng sáu khoá không có vai, `expiresAt` `.000Z`, cookie xoay."""
    user = await make_user(db_session, role="viewer")
    t0 = await _logged_in(auth_client, user)
    response = await refresh_with(auth_client, t0)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == W16_KEYS
    assert body["roles"] == ["viewer"]
    assert body["user"] == {"id": user.id, "name": user.name, "email": user.email}
    assert body["expiresAt"] == "2026-01-01T00:10:00.000Z"
    claims = jwt.decode(
        body["accessToken"],
        current_key("access"),
        algorithms=["HS256"],
        audience="access",
        options={"verify_exp": False},
    )
    assert set(claims) == CLAIMS
    assert (claims["sub"], claims["sid"], claims["ver"], claims["aud"]) == (user.id, _sid(t0), 0, "access")
    assert claims["exp"] - claims["iat"] == get_auth_settings().access_token_ttl_s
    cookies = set_cookies(response)
    t1 = cookie_value(cookies[REFRESH_COOKIE])
    assert _sid(t1) == _sid(t0)
    assert t1 != t0
    assert STREAM_COOKIE in cookies


async def test_auth_refresh__C11(auth_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Tầng thất bại: cùng một token rác `REFRESH_FAIL_LIMIT` lần 401, lượt kế tiếp 429."""
    user = await make_user(db_session)
    junk = f"{_sid(await _logged_in(auth_client, user))}.{new_refresh_token()}"
    for _ in range(get_auth_settings().refresh_fail_limit):
        assert (await refresh_with(auth_client, junk)).status_code == 401
    blocked = await refresh_with(auth_client, junk)
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "RATE_LIMITED"
    assert 1 <= int(blocked.headers["Retry-After"]) <= 10


async def test_auth_refresh__C11_total(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tầng tổng theo `sid`: vượt `REFRESH_TOTAL_LIMIT` (đặt 3) thì kể cả cookie đúng cũng 429."""
    monkeypatch.setenv("REFRESH_TOTAL_LIMIT", "3")
    reset_auth_settings_cache()
    user = await make_user(db_session)
    t0 = await _logged_in(auth_client, user)
    statuses = [(await refresh_with(auth_client, t0)).status_code for _ in range(4)]
    assert statuses == [200, 200, 200, 429]


async def test_auth_refresh__C19(auth_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """5 lượt song song cùng cookie → cả 5 là 200, cùng `sid`, cùng một `Set-Cookie`; phiên còn sống."""
    user = await make_user(db_session)
    t0 = await _logged_in(auth_client, user)
    responses = await asyncio.gather(*(refresh_with(auth_client, t0) for _ in range(PARALLEL)))
    assert [response.status_code for response in responses] == [200] * PARALLEL
    headers = {set_cookies(response)[REFRESH_COOKIE] for response in responses}
    _log.info("c19 responses=%d distinct_set_cookie=%d value=%s", PARALLEL, len(headers), sorted(headers))
    assert len(headers) == 1
    current = cookie_value(headers.pop())
    assert _sid(current) == _sid(t0)
    assert current != t0
    assert (await session_row(db_session, _sid(t0))).revoked_at is None


async def test_auth_refresh__C19_chain(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Cookie cũ, cookie kế tiếp, lại cookie cũ trong 30 s → cả ba 200, cùng một cookie hiện hành."""
    user = await make_user(db_session)
    t0 = await _logged_in(auth_client, user)
    first = await refresh_with(auth_client, t0)
    t1 = refresh_cookie(first)
    fake_clock.advance(timedelta(seconds=10))
    second = await refresh_with(auth_client, t1)
    fake_clock.advance(timedelta(seconds=10))
    third = await refresh_with(auth_client, t0)
    assert [first.status_code, second.status_code, third.status_code] == [200, 200, 200]
    handed = [refresh_cookie(response) for response in (first, second, third)]
    _log.info("c19_chain distinct_set_cookie=%d", len(set(handed)))
    assert handed == [t1, t1, t1]
    assert {_sid(value) for value in handed} == {_sid(t0)}
    assert (await session_row(db_session, _sid(t0))).revoked_at is None


async def test_auth_refresh__C20(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Dùng lại cookie cũ sau 31 s → 401 `SESSION_REVOKED`, cả phiên bị thu hồi (`reuse`)."""
    user = await make_user(db_session)
    t0 = await _logged_in(auth_client, user)
    t1 = refresh_cookie(await refresh_with(auth_client, t0))
    fake_clock.advance(GRACE)
    replay = await refresh_with(auth_client, t0)
    assert replay.status_code == 401
    assert replay.json()["code"] == "SESSION_REVOKED"
    current = await refresh_with(auth_client, t1)
    assert current.status_code == 401
    assert current.json()["code"] == "SESSION_REVOKED"
    assert (await session_row(db_session, _sid(t0))).revoked_reason == "reuse"


async def test_auth_refresh__C24(auth_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Thiếu hoặc lệch `Origin` → 403 `ORIGIN_MISMATCH`; cookie không bị xoay."""
    user = await make_user(db_session)
    t0 = await _logged_in(auth_client, user)
    missing = await refresh_with(auth_client, t0, origin=False)
    foreign = await auth_client.post(
        "/api/auth/refresh", headers={"Origin": "https://ke-gian.example", "Cookie": f"{REFRESH_COOKIE}={t0}"}
    )
    for response in (missing, foreign):
        assert response.status_code == 403
        assert response.json()["code"] == "ORIGIN_MISMATCH"
    assert (await session_row(db_session, _sid(t0))).rotated_at is None


@pytest.mark.parametrize("value", [None, "", "khong-co-dau-cham", f"{uuid4()}.ngan", f"{uuid4()}".upper() + ".x"])
async def test_missing_or_malformed_cookie_is_401(auth_client: httpx.AsyncClient, value: str | None) -> None:
    """Cookie thiếu hoặc sai mẫu `<sid>.<token 43 ký tự>` → 401 `UNAUTHENTICATED`, không chạm DB."""
    response = await refresh_with(auth_client, value)
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"


async def test_unknown_session_is_401(auth_client: httpx.AsyncClient) -> None:
    """Cookie đúng mẫu nhưng `sid` không có phiên → 401 `UNAUTHENTICATED`."""
    response = await refresh_with(auth_client, f"{uuid4()}.{new_refresh_token()}")
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"


async def test_revocation_is_checked_before_grace(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Đăng xuất rồi gửi cookie `previous` trong ân hạn → 401: thu hồi được kiểm trước mọi nhánh."""
    user = await make_user(db_session)
    t0 = await _logged_in(auth_client, user)
    t1 = refresh_cookie(await refresh_with(auth_client, t0))
    logout = await auth_client.post(
        "/api/auth/logout", headers={"Origin": get_core_settings().public_base_url, "Cookie": f"{REFRESH_COOKIE}={t1}"}
    )
    assert logout.status_code == 204
    fake_clock.advance(timedelta(seconds=5))
    response = await refresh_with(auth_client, t0)
    assert response.status_code == 401
    assert response.json()["code"] == "SESSION_REVOKED"


async def test_junk_tokens_never_revoke_the_session(auth_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Kẻ chỉ biết `sid`: 30 token rác → 401 `UNAUTHENTICATED`, phiên vẫn sống, refresh thật vẫn 200."""
    user = await make_user(db_session)
    t0 = await _logged_in(auth_client, user)
    for _ in range(JUNK_ATTEMPTS):
        response = await refresh_with(auth_client, f"{_sid(t0)}.{new_refresh_token()}")
        assert response.status_code == 401
        assert response.json()["code"] == "UNAUTHENTICATED"
    assert (await session_row(db_session, _sid(t0))).revoked_at is None
    assert (await refresh_with(auth_client, t0)).status_code == 200


async def test_old_token_down_the_chain_revokes_the_session(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """T0 → T1 (+31 s) → T2 (+31 s), gửi lại T0: chuỗi HMAC chạm `current` → thu hồi (`reuse`)."""
    user = await make_user(db_session)
    t0 = await _logged_in(auth_client, user)
    t1 = refresh_cookie(await refresh_with(auth_client, t0))
    fake_clock.advance(GRACE)
    t2 = refresh_cookie(await refresh_with(auth_client, t1))
    fake_clock.advance(GRACE)
    assert t2 not in (t0, t1)
    replay = await refresh_with(auth_client, t0)
    assert replay.status_code == 401
    assert replay.json()["code"] == "SESSION_REVOKED"
    assert (await session_row(db_session, _sid(t0))).revoked_reason == "reuse"
    assert (await refresh_with(auth_client, t2)).status_code == 401


async def test_idle_expiry_is_401(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Phiên không ghi nhớ bỏ không quá 12 giờ → 401 `SESSION_REVOKED`."""
    user = await make_user(db_session)
    t0 = await _logged_in(auth_client, user, remember=False)
    fake_clock.advance(timedelta(hours=12))
    response = await refresh_with(auth_client, t0)
    assert response.status_code == 401
    assert response.json()["code"] == "SESSION_REVOKED"


async def test_absolute_expiry_is_401_even_when_active(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Ghi nhớ, refresh đều mỗi 6 ngày (idle không hết) → tới ngày 30 vẫn 401; idle không vượt hạn tuyệt đối."""
    user = await make_user(db_session)
    cookie = await _logged_in(auth_client, user)
    started = fake_clock.now()
    for _ in range(4):
        fake_clock.advance(timedelta(days=6))
        response = await refresh_with(auth_client, cookie)
        assert response.status_code == 200
        cookie = refresh_cookie(response)
    row = await session_row(db_session, _sid(cookie))
    assert row.idle_expires_at == started + timedelta(days=30) == row.absolute_expires_at
    fake_clock.advance(timedelta(days=6))
    expired = await refresh_with(auth_client, cookie)
    assert expired.status_code == 401
    assert expired.json()["code"] == "SESSION_REVOKED"


@pytest.mark.parametrize(
    ("change", "reason"), [({"status": "disabled"}, "disabled"), ({"deleted_at": func.now()}, "deleted")]
)
async def test_gone_owner_is_401_and_revokes(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, change: dict[str, object], reason: str
) -> None:
    """Người dùng bị vô hiệu hay xoá mềm → 401 `SESSION_REVOKED`, phiên bị thu hồi đúng lý do."""
    user = await make_user(db_session)
    t0 = await _logged_in(auth_client, user)
    await db_session.execute(update(User).where(User.id == user.id).values(**change))
    await db_session.commit()
    response = await refresh_with(auth_client, t0)
    assert response.status_code == 401
    assert response.json()["code"] == "SESSION_REVOKED"
    assert (await session_row(db_session, _sid(t0))).revoked_reason == reason


async def test_last_active_is_touched_at_most_every_five_minutes(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """`last_active_at` chỉ đổi khi cũ hơn 5 phút (giảm ghi DB mỗi lượt refresh)."""
    user = await make_user(db_session)
    cookie = await _logged_in(auth_client, user)
    logged_in_at = fake_clock.now()
    fake_clock.advance(timedelta(minutes=1))
    cookie = refresh_cookie(await refresh_with(auth_client, cookie))
    assert (await user_row(db_session, user.id)).last_active_at == logged_in_at
    fake_clock.advance(timedelta(minutes=5))
    await refresh_with(auth_client, cookie)
    assert (await user_row(db_session, user.id)).last_active_at == fake_clock.now()


async def test_last_active_never_waits_for_a_row_lock(
    auth_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
) -> None:
    """Dòng `users` đang bị khoá → refresh vẫn 200 ngay, bỏ qua lượt ghi `last_active_at` (SKIP LOCKED)."""
    user = await make_user(db_session)
    cookie = await _logged_in(auth_client, user)
    fake_clock.advance(timedelta(minutes=10))
    async with db_sessionmaker() as locker:
        await locker.execute(select(User.id).where(User.id == user.id).with_for_update())
        response = await asyncio.wait_for(refresh_with(auth_client, cookie), timeout=3)
        await locker.rollback()
    assert response.status_code == 200
    assert (await user_row(db_session, user.id)).last_active_at == fake_clock.now() - timedelta(minutes=10)


async def _blocked_on_lock(maker: async_sessionmaker[AsyncSession]) -> bool:
    """Có một giao dịch của database này đang chờ khoá dòng."""
    async with maker() as probe:
        waiting = await probe.scalar(
            text(
                "SELECT count(*) FROM pg_stat_activity WHERE wait_event_type = 'Lock' AND datname = current_database()"
            )
        )
    return bool(waiting)


async def test_losing_the_rotation_race_rereads_and_hands_the_winner(
    auth_env: None, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Hai lượt cùng token: lượt thua chờ khoá dòng, `UPDATE` được 0 dòng, đọc lại và trả cookie của lượt thắng."""
    user = await make_user(db_session)
    response = Response()
    sid = await start_session(db_session, response, user=user, remember=True, ip="2001:db8::1", clock=fake_clock)
    await db_session.commit()
    await after_commit_idle(db_session)
    token = next(h for h in response.headers.getlist("set-cookie") if h.startswith(REFRESH_COOKIE))
    t0 = cookie_value(token).split(".", 1)[1]
    settings = get_auth_settings()
    async with db_sessionmaker() as winner, db_sessionmaker() as loser:
        won = await refresh_session(winner, sid=UUID(sid), token=t0, clock=fake_clock, settings=settings)
        racing = asyncio.create_task(
            refresh_session(loser, sid=UUID(sid), token=t0, clock=fake_clock, settings=settings)
        )
        await wait_until(lambda: _blocked_on_lock(db_sessionmaker))
        await winner.commit()
        lost = await racing
        await loser.commit()
        await after_commit_idle(winner)
        await after_commit_idle(loser)
    assert isinstance(won, Refreshed)
    assert isinstance(lost, Refreshed)
    assert lost.token == won.token != t0
    assert str((await session_row(db_session, sid)).created_ip) == "2001:db8::1"


async def test_grace_needs_a_key_that_made_the_successor(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Token `previous` trong ân hạn mà không khoá kiểm nào dựng ra `current` → 401, không thu hồi."""
    user = await make_user(db_session)
    t0 = await _logged_in(auth_client, user)
    assert (await refresh_with(auth_client, t0)).status_code == 200
    monkeypatch.setenv("SECRET_KEY", ROTATED_SECRET)
    monkeypatch.delenv("SECRET_KEY_PREVIOUS", raising=False)
    reset_settings_cache()
    response = await refresh_with(auth_client, t0)
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"
    assert (await session_row(db_session, _sid(t0))).revoked_at is None


async def test_secret_rotation_keeps_grace_and_old_access_tokens(
    probe_client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Xoay `SECRET_KEY` (khoá cũ sang `SECRET_KEY_PREVIOUS`): ân hạn vẫn trả đúng cookie, access token cũ vẫn qua."""
    user = await make_user(db_session)
    t0 = await _logged_in(probe_client, user)
    first = await refresh_with(probe_client, t0)
    t1, old_access = refresh_cookie(first), first.json()["accessToken"]
    monkeypatch.setenv("SECRET_KEY", ROTATED_SECRET)
    monkeypatch.setenv("SECRET_KEY_PREVIOUS", STORAGE_SECRET)
    reset_settings_cache()
    again = await refresh_with(probe_client, t0)
    assert again.status_code == 200
    assert refresh_cookie(again) == t1
    probe = await probe_client.get(PROBE_PATH, headers={"Authorization": f"Bearer {old_access}"})
    assert probe.status_code == 200
    assert probe.json()["userId"] == user.id


async def test_cache_redis_down_still_refreshes(
    auth_env: None, fake_clock: FakeClock, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`redis-cache` dừng: hai tầng hạn mức `on_error="open"`, xoá ảnh chụp hỏng chỉ log → vẫn 200."""
    user = await make_user(db_session)
    container = ephemeral_redis("allkeys-lru")
    host, port = container.get_container_host_ip(), container.get_exposed_port(6379)
    try:
        monkeypatch.setenv("REDIS_CACHE_URL", f"redis://{host}:{port}/0")
        reset_messaging_settings_cache()
        async with make_api_client(create_app(get_core_settings(), clock=fake_clock)) as client:
            t0 = await _logged_in(client, user)
            container.stop()
            response = await refresh_with(client, t0)
    finally:
        reset_messaging_settings_cache()
        with suppress(Exception):  # đã dừng ở giữa test: lượt dừng thứ hai ném `NotFound`
            container.stop()
    assert response.status_code == 200
    assert set(response.json()) == W16_KEYS


async def test_postgres_down_is_503(auth_env: None, fake_clock: FakeClock, monkeypatch: pytest.MonkeyPatch) -> None:
    """Postgres không nghe → 503 `DEPENDENCY_UNAVAILABLE` kèm `Retry-After` (không phải 401)."""
    monkeypatch.setenv("DATABASE_URL", f"{refused_url('postgresql+asyncpg')}/appback")
    reset_database_settings_cache()
    async with make_api_client(create_app(get_core_settings(), clock=fake_clock)) as client:
        response = await refresh_with(client, f"{uuid4()}.{new_refresh_token()}")
    reset_database_settings_cache()
    assert response.status_code == 503
    assert response.json()["code"] == "DEPENDENCY_UNAVAILABLE"
    assert "Retry-After" in response.headers


async def test_refresh_resets_idle_but_grace_hands_do_not_write(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Xoay kéo dài idle tới `now + 7 ngày`; lượt trong ân hạn không ghi DB (`rotated_at` giữ nguyên)."""
    user = await make_user(db_session)
    t0 = await _logged_in(auth_client, user)
    fake_clock.advance(timedelta(days=1))
    await refresh_with(auth_client, t0)
    rotated = await session_row(db_session, _sid(t0))
    assert rotated.idle_expires_at == fake_clock.now() + timedelta(days=7)
    fake_clock.advance(timedelta(seconds=20))
    await refresh_with(auth_client, t0)
    again = await session_row(db_session, _sid(t0))
    assert (again.rotated_at, again.current_token_hash) == (rotated.rotated_at, rotated.current_token_hash)


async def test_denied_refresh_is_a_value_not_an_exception(
    auth_env: None, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """`refresh_session` trả `RefreshDenied` (không ném) để lệnh thu hồi của người gọi được commit."""
    outcome = await refresh_session(
        db_session, sid=uuid4(), token=new_refresh_token(), clock=fake_clock, settings=get_auth_settings()
    )
    assert isinstance(outcome, RefreshDenied)
    assert outcome.code.code == "UNAUTHENTICATED"


async def test_auth_refresh__C11_parallel(auth_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Tầng thất bại dưới tải song song: 40 lượt cùng token rác → đúng `REFRESH_FAIL_LIMIT` lượt 401, còn lại 429."""
    user = await make_user(db_session)
    junk = f"{_sid(await _logged_in(auth_client, user))}.{new_refresh_token()}"
    limit = get_auth_settings().refresh_fail_limit
    responses = await asyncio.gather(*(refresh_with(auth_client, junk) for _ in range(2 * limit)))
    statuses = sorted(response.status_code for response in responses)
    assert statuses == [401] * limit + [429] * limit


async def test_old_token_across_a_key_rotation_revokes_the_session(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Chuỗi đổi khoá một lần (T0 bằng khoá cũ, T1 bằng khoá mới) vẫn chạm `current` → gửi lại T0 là `reuse`."""
    user = await make_user(db_session)
    t0 = await _logged_in(auth_client, user)
    t1 = refresh_cookie(await refresh_with(auth_client, t0))
    monkeypatch.setenv("SECRET_KEY", ROTATED_SECRET)
    monkeypatch.setenv("SECRET_KEY_PREVIOUS", STORAGE_SECRET)
    reset_settings_cache()
    fake_clock.advance(GRACE)
    assert (await refresh_with(auth_client, t1)).status_code == 200
    fake_clock.advance(GRACE)
    replay = await refresh_with(auth_client, t0)
    assert replay.status_code == 401
    assert replay.json()["code"] == "SESSION_REVOKED"
    assert (await session_row(db_session, _sid(t0))).revoked_reason == "reuse"


async def test_second_read_refuses_to_rotate(auth_env: None, db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Lượt đọc lại sau xoay hỏng mà token vẫn là `current` → bất biến vỡ → `RuntimeError`, không trả thành công."""
    user = await make_user(db_session)
    response = Response()
    sid = await start_session(db_session, response, user=user, remember=True, ip=None, clock=fake_clock)
    await db_session.commit()
    token = cookie_value(response.headers.getlist("set-cookie")[0]).split(".", 1)[1]
    with pytest.raises(RuntimeError, match="bất biến"):
        await sessions._decide(db_session, UUID(sid), token, fake_clock, get_auth_settings(), may_rotate=False)


async def test_reuse_is_logged_without_the_token(
    auth_client: httpx.AsyncClient,
    db_session: AsyncSession,
    fake_clock: FakeClock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Thu hồi vì dùng lại để lại một dòng `refresh_reuse_revoked` mang `sid`, không mang token."""
    user = await make_user(db_session)
    t0 = await _logged_in(auth_client, user)
    await refresh_with(auth_client, t0)
    fake_clock.advance(GRACE)
    with caplog.at_level(logging.WARNING, logger="apps.api.auth.sessions"):
        assert (await refresh_with(auth_client, t0)).status_code == 401
    records = [record for record in caplog.records if record.getMessage() == "refresh_reuse_revoked"]
    assert len(records) == 1
    line = JsonFormatter().format(records[0])
    assert f'"sid": "{_sid(t0)}"' in line
    assert all(t0.split(".", 1)[1] not in JsonFormatter().format(record) for record in caplog.records)


async def test_junk_token_with_a_previous_key_never_revokes(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Có khoá cũ (`SECRET_KEY_PREVIOUS`): token rác đi hết mọi chuỗi một khoá và đổi khoá → 401, phiên vẫn sống."""
    user = await make_user(db_session)
    t0 = await _logged_in(auth_client, user)
    monkeypatch.setenv("SECRET_KEY_PREVIOUS", ROTATED_SECRET)
    reset_settings_cache()
    response = await refresh_with(auth_client, f"{_sid(t0)}.{new_refresh_token()}")
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"
    assert (await session_row(db_session, _sid(t0))).revoked_at is None
    assert (await refresh_with(auth_client, t0)).status_code == 200
