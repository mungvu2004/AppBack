"""`POST /api/auth/password-reset/confirm` (N9, B1-03 [2], [8]; CASE loại C)."""

import asyncio
import unicodedata
from datetime import timedelta
from typing import Final

import httpx
import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.auth.cookies import REFRESH_COOKIE, STREAM_COOKIE
from apps.api.auth.passwords import hash_password
from apps.api.auth.tests.support import cookie_value, refresh_with, set_cookies, user_row
from apps.api.auth_recovery import router
from apps.api.auth_recovery.settings import get_recovery_settings
from apps.api.auth_recovery.tests.support import seed_token
from packages.db.models.auth import User
from packages.testing.factories.auth import TEST_PASSWORD, make_user
from packages.testing.fixtures.auth import ORIGIN, login
from packages.testing.fixtures.clock import FakeClock

pytestmark = pytest.mark.usefixtures("api_env")

PATH: Final = "/api/auth/password-reset/confirm"
NEW_PASSWORD: Final = "mat-khau-moi-cho-ai-do"  # noqa: S105 — mật khẩu giả của test


async def _confirm(client: httpx.AsyncClient, token: str, new_password: str) -> httpx.Response:
    """Một lượt `POST /api/auth/password-reset/confirm` đúng `Origin`."""
    return await client.post(PATH, json={"token": token, "newPassword": new_password}, headers=ORIGIN)


async def test_auth_confirm_password_reset__C01(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Đúng: 204 rỗng, xoá hai cookie, mật khẩu mới dùng được, mật khẩu cũ hết dùng được."""
    user = await make_user(db_session)
    _, plain = await seed_token(db_session, user_id=user.id, purpose="password_reset", clock=fake_clock)
    response = await _confirm(auth_client, plain, NEW_PASSWORD)
    assert response.status_code == 204
    assert response.content == b""
    cookies = set_cookies(response)
    for name in (REFRESH_COOKIE, STREAM_COOKIE):
        assert "max-age=0" in cookies[name].lower()
    assert (await login(auth_client, user.email, TEST_PASSWORD)).status_code == 401
    assert (await login(auth_client, user.email, NEW_PASSWORD)).status_code == 204


async def test_auth_confirm_password_reset__C02(auth_client: httpx.AsyncClient) -> None:
    """Mật khẩu mới ngắn hơn 8 → 422 `field:"newPassword"`; token rỗng → 422 `field:"token"`."""
    short = await auth_client.post(PATH, json={"token": "x" * 10, "newPassword": "ngan"}, headers=ORIGIN)
    assert short.status_code == 422
    assert short.json()["field"] == "newPassword"
    empty_token = await auth_client.post(PATH, json={"token": "", "newPassword": NEW_PASSWORD}, headers=ORIGIN)
    assert empty_token.status_code == 422
    assert empty_token.json()["field"] == "token"


async def test_auth_confirm_password_reset__C03(auth_client: httpx.AsyncClient) -> None:
    """Khoá lạ → 422 `VALIDATION`."""
    body = {"token": "x" * 10, "newPassword": NEW_PASSWORD, "extra": 1}
    response = await auth_client.post(PATH, json=body, headers=ORIGIN)
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"


async def test_auth_confirm_password_reset__C11(auth_client: httpx.AsyncClient) -> None:
    """Vượt `recovery_ip` → 429; hạn mức dùng chung với N8 (một bucket `recovery_ip` theo IP)."""
    limit = get_recovery_settings().recovery_ip_limit
    for _ in range(limit):
        response = await _confirm(auth_client, "x" * 20, NEW_PASSWORD)
        assert response.status_code == 422
    blocked = await _confirm(auth_client, "x" * 20, NEW_PASSWORD)
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "RATE_LIMITED"


async def test_auth_confirm_password_reset__C16(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Mật khẩu NFD đặt lại vẫn đăng nhập được bằng NFC (chuẩn hoá NFC ở server)."""
    user = await make_user(db_session)
    nfd_password = unicodedata.normalize("NFD", "Mật-khẩu-mới-tiếng-Việt")
    _, plain = await seed_token(db_session, user_id=user.id, purpose="password_reset", clock=fake_clock)
    assert (await _confirm(auth_client, plain, nfd_password)).status_code == 204
    assert (await login(auth_client, user.email, unicodedata.normalize("NFC", nfd_password))).status_code == 204


async def test_auth_confirm_password_reset__C24(auth_client: httpx.AsyncClient) -> None:
    """Thiếu/lệch `Origin` → 403 `ORIGIN_MISMATCH`, trước cả kiểm thân."""
    body = {"token": "x" * 10, "newPassword": NEW_PASSWORD}
    missing = await auth_client.post(PATH, json=body)
    foreign = await auth_client.post(PATH, json=body, headers={"Origin": "https://ke-gian.example"})
    for response in (missing, foreign):
        assert response.status_code == 403
        assert response.json()["code"] == "ORIGIN_MISMATCH"


async def test_auth_confirm_password_reset__C26_unknown_token(auth_client: httpx.AsyncClient) -> None:
    """Token không tồn tại → 422 `PASSWORD_RESET_TOKEN_INVALID`."""
    response = await _confirm(auth_client, "z" * 43, NEW_PASSWORD)
    assert response.status_code == 422
    assert response.json()["code"] == "PASSWORD_RESET_TOKEN_INVALID"


async def test_auth_confirm_password_reset__C26_used(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Token đã dùng → 422, dùng lại lần nữa vẫn 422."""
    user = await make_user(db_session)
    _, plain = await seed_token(
        db_session, user_id=user.id, purpose="password_reset", clock=fake_clock, used_at=fake_clock.now()
    )
    response = await _confirm(auth_client, plain, NEW_PASSWORD)
    assert response.status_code == 422
    assert response.json()["code"] == "PASSWORD_RESET_TOKEN_INVALID"


async def test_auth_confirm_password_reset__C26_expired(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Token hết hạn → 422."""
    user = await make_user(db_session)
    _, plain = await seed_token(
        db_session, user_id=user.id, purpose="password_reset", clock=fake_clock, ttl=timedelta(seconds=-1)
    )
    assert (await _confirm(auth_client, plain, NEW_PASSWORD)).status_code == 422


async def test_auth_confirm_password_reset__C26_superseded(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Token bị thay (yêu cầu N8 sau) → 422."""
    user = await make_user(db_session)
    _, plain = await seed_token(
        db_session, user_id=user.id, purpose="password_reset", clock=fake_clock, superseded_at=fake_clock.now()
    )
    assert (await _confirm(auth_client, plain, NEW_PASSWORD)).status_code == 422


async def test_auth_confirm_password_reset__C26_wrong_purpose(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Token của mục đích khác (`invite`) → 422 (tra đúng `purpose`)."""
    user = await make_user(db_session)
    _, plain = await seed_token(db_session, user_id=user.id, purpose="invite", clock=fake_clock)
    assert (await _confirm(auth_client, plain, NEW_PASSWORD)).status_code == 422


async def test_auth_confirm_password_reset__C26_account_not_active(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Người sở hữu token không còn `active` (vô hiệu giữa chừng) → 422."""
    user = await make_user(db_session, status="disabled")
    _, plain = await seed_token(db_session, user_id=user.id, purpose="password_reset", clock=fake_clock)
    assert (await _confirm(auth_client, plain, NEW_PASSWORD)).status_code == 422


async def test_auth_confirm_password_reset__revokes_sessions_and_cookies(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Xong N9: phiên cũ refresh → 401 `SESSION_REVOKED`; mật khẩu cũ 401, mật khẩu mới 204."""
    user = await make_user(db_session)
    logged_in = await login(auth_client, user.email, TEST_PASSWORD)
    old_refresh = cookie_value(set_cookies(logged_in)[REFRESH_COOKIE])
    _, plain = await seed_token(db_session, user_id=user.id, purpose="password_reset", clock=fake_clock)
    assert (await _confirm(auth_client, plain, NEW_PASSWORD)).status_code == 204
    denied = await refresh_with(auth_client, old_refresh)
    assert denied.status_code == 401
    assert denied.json()["code"] == "SESSION_REVOKED"
    assert (await login(auth_client, user.email, TEST_PASSWORD)).status_code == 401
    assert (await login(auth_client, user.email, NEW_PASSWORD)).status_code == 204


async def test_auth_confirm_password_reset__concurrent_same_token_one_wins(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Hai lượt N9 song song cùng token → một 204, một 422 (`consume_token` phân xử)."""
    user = await make_user(db_session)
    _, plain = await seed_token(db_session, user_id=user.id, purpose="password_reset", clock=fake_clock)
    first, second = await asyncio.gather(
        _confirm(auth_client, plain, "mat-khau-thu-nhat-01"), _confirm(auth_client, plain, "mat-khau-thu-hai-02")
    )
    assert sorted([first.status_code, second.status_code]) == [204, 422]


async def test_auth_confirm_password_reset__disabled_mid_hash_stays_disabled(
    auth_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Người bị `disabled` (commit trực tiếp) đúng lúc N9 đang băm → N9 422, người vẫn `disabled`."""
    user = await make_user(db_session)
    _, plain = await seed_token(db_session, user_id=user.id, purpose="password_reset", clock=fake_clock)
    started, proceed = asyncio.Event(), asyncio.Event()

    async def _blocking_hash(password: str) -> str:
        """Bọc `hash_password` thật: báo đã tới điểm băm rồi chờ test mở khoá."""
        started.set()
        await proceed.wait()
        return await hash_password(password)

    monkeypatch.setattr(router, "hash_password", _blocking_hash)
    task = asyncio.create_task(_confirm(auth_client, plain, NEW_PASSWORD))
    await started.wait()
    async with db_sessionmaker() as setup:
        await setup.execute(update(User).where(User.id == user.id).values(status="disabled"))
        await setup.commit()
    proceed.set()
    response = await task
    assert response.status_code == 422
    assert response.json()["code"] == "PASSWORD_RESET_TOKEN_INVALID"
    row = await user_row(db_session, user.id)
    assert row.status == "disabled"


async def test_auth_confirm_password_reset__body_is_empty(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """204 thân rỗng (H1)."""
    user = await make_user(db_session)
    _, plain = await seed_token(db_session, user_id=user.id, purpose="password_reset", clock=fake_clock)
    response = await _confirm(auth_client, plain, NEW_PASSWORD)
    assert response.status_code == 204
    assert response.content == b""
