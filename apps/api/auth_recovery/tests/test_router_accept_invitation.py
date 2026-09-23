"""`POST /api/auth/invitations/accept` (N10, B1-03 [2], [8]; CASE loại C)."""

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
from apps.api.auth.tests.support import set_cookies, user_row
from apps.api.auth_recovery import router
from apps.api.auth_recovery.settings import get_recovery_settings
from apps.api.auth_recovery.tests.support import seed_token
from packages.db.models.auth import User
from packages.testing.factories.auth import make_user
from packages.testing.fixtures.auth import ORIGIN, login
from packages.testing.fixtures.clock import FakeClock

pytestmark = pytest.mark.usefixtures("api_env")

PATH: Final = "/api/auth/invitations/accept"
PASSWORD: Final = "mat-khau-nhan-loi-moi-01"  # noqa: S105 — mật khẩu giả của test


async def _accept(client: httpx.AsyncClient, token: str, full_name: str, password: str) -> httpx.Response:
    """Một lượt `POST /api/auth/invitations/accept` đúng `Origin`."""
    return await client.post(PATH, json={"token": token, "fullName": full_name, "password": password}, headers=ORIGIN)


async def test_auth_accept_invitation__C01(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Đúng: 204, hai cookie, người `pending` → `active` với tên và mật khẩu mới."""
    user = await make_user(db_session, status="pending", password=None)
    _, plain = await seed_token(db_session, user_id=user.id, purpose="invite", clock=fake_clock)
    response = await _accept(auth_client, plain, "Người Mới", PASSWORD)
    assert response.status_code == 204
    assert response.content == b""
    cookies = set_cookies(response)
    assert REFRESH_COOKIE in cookies
    assert STREAM_COOKIE in cookies
    row = await user_row(db_session, user.id)
    assert (row.status, row.name) == ("active", "Người Mới")
    assert (await login(auth_client, user.email, PASSWORD)).status_code == 204


async def test_auth_accept_invitation__C02(auth_client: httpx.AsyncClient) -> None:
    """Mật khẩu ngắn hơn 8 → 422 `field:"password"`; token rỗng → 422 `field:"token"`."""
    short = await auth_client.post(PATH, json={"token": "x" * 10, "fullName": "A", "password": "ngan"}, headers=ORIGIN)
    assert short.status_code == 422
    assert short.json()["field"] == "password"
    empty_token = await auth_client.post(
        PATH, json={"token": "", "fullName": "A", "password": PASSWORD}, headers=ORIGIN
    )
    assert empty_token.status_code == 422
    assert empty_token.json()["field"] == "token"


@pytest.mark.parametrize(
    "full_name",
    ["", " ", "a" * 121, "co-\u0007-dieu-khien", "co-‮-dao-chieu"],
    ids=["rong", "trang", "qua-dai", "control", "bidi"],
)
async def test_auth_accept_invitation__C02_full_name(auth_client: httpx.AsyncClient, full_name: str) -> None:
    """`fullName` rỗng/quá 120/ký tự điều khiển/đảo chiều → 422 `field:"fullName"`."""
    response = await _accept(auth_client, "x" * 10, full_name, PASSWORD)
    assert response.status_code == 422
    assert response.json()["field"] == "fullName"


async def test_auth_accept_invitation__C03(auth_client: httpx.AsyncClient) -> None:
    """Khoá lạ → 422 `VALIDATION`."""
    body = {"token": "x" * 10, "fullName": "A", "password": PASSWORD, "extra": 1}
    response = await auth_client.post(PATH, json=body, headers=ORIGIN)
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"


async def test_auth_accept_invitation__C11(auth_client: httpx.AsyncClient) -> None:
    """Vượt `recovery_ip` → 429; hạn mức dùng chung với N8/N9."""
    limit = get_recovery_settings().recovery_ip_limit
    for _ in range(limit):
        response = await _accept(auth_client, "x" * 20, "A", PASSWORD)
        assert response.status_code == 422
    blocked = await _accept(auth_client, "x" * 20, "A", PASSWORD)
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "RATE_LIMITED"


async def test_auth_accept_invitation__C16(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """`fullName` NFD được lưu NFC; mật khẩu NFD đặt lúc nhận lời mời vẫn đăng nhập bằng NFC."""
    user = await make_user(db_session, status="pending", password=None)
    _, plain = await seed_token(db_session, user_id=user.id, purpose="invite", clock=fake_clock)
    nfc_name = "Tên Có Dấu"
    nfd_name = unicodedata.normalize("NFD", nfc_name)
    nfd_password = unicodedata.normalize("NFD", "Mật-khẩu-tiếng-Việt-moi")
    assert (await _accept(auth_client, plain, nfd_name, nfd_password)).status_code == 204
    row = await user_row(db_session, user.id)
    assert row.name == nfc_name
    assert (await login(auth_client, user.email, unicodedata.normalize("NFC", nfd_password))).status_code == 204


async def test_auth_accept_invitation__C24(auth_client: httpx.AsyncClient) -> None:
    """Thiếu/lệch `Origin` → 403 `ORIGIN_MISMATCH`, trước cả kiểm thân."""
    body = {"token": "x" * 10, "fullName": "A", "password": PASSWORD}
    missing = await auth_client.post(PATH, json=body)
    foreign = await auth_client.post(PATH, json=body, headers={"Origin": "https://ke-gian.example"})
    for response in (missing, foreign):
        assert response.status_code == 403
        assert response.json()["code"] == "ORIGIN_MISMATCH"


async def test_auth_accept_invitation__C26_unknown_token(auth_client: httpx.AsyncClient) -> None:
    """Token không tồn tại → 422 `INVITATION_TOKEN_INVALID`."""
    response = await _accept(auth_client, "z" * 43, "A", PASSWORD)
    assert response.status_code == 422
    assert response.json()["code"] == "INVITATION_TOKEN_INVALID"


async def test_auth_accept_invitation__C26_used(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Token đã dùng → 422."""
    user = await make_user(db_session, status="pending", password=None)
    _, plain = await seed_token(
        db_session, user_id=user.id, purpose="invite", clock=fake_clock, used_at=fake_clock.now()
    )
    assert (await _accept(auth_client, plain, "A", PASSWORD)).status_code == 422


async def test_auth_accept_invitation__C26_expired(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Token hết hạn → 422."""
    user = await make_user(db_session, status="pending", password=None)
    _, plain = await seed_token(
        db_session, user_id=user.id, purpose="invite", clock=fake_clock, ttl=timedelta(seconds=-1)
    )
    assert (await _accept(auth_client, plain, "A", PASSWORD)).status_code == 422


async def test_auth_accept_invitation__C26_superseded(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Token bị thay (mời lại) → 422."""
    user = await make_user(db_session, status="pending", password=None)
    _, plain = await seed_token(
        db_session, user_id=user.id, purpose="invite", clock=fake_clock, superseded_at=fake_clock.now()
    )
    assert (await _accept(auth_client, plain, "A", PASSWORD)).status_code == 422


async def test_auth_accept_invitation__C26_wrong_purpose(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Token của mục đích khác (`password_reset`) → 422."""
    user = await make_user(db_session, status="pending", password=None)
    _, plain = await seed_token(db_session, user_id=user.id, purpose="password_reset", clock=fake_clock)
    assert (await _accept(auth_client, plain, "A", PASSWORD)).status_code == 422


async def test_auth_accept_invitation__C26_already_active(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Người sở hữu token đã `active` (mời chấp nhận rồi) → 422."""
    user = await make_user(db_session)  # active mặc định
    _, plain = await seed_token(db_session, user_id=user.id, purpose="invite", clock=fake_clock)
    assert (await _accept(auth_client, plain, "A", PASSWORD)).status_code == 422


async def test_auth_accept_invitation__refresh_works_after(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Xong N10: cookie refresh vừa đặt dùng để `refresh` được (200)."""
    user = await make_user(db_session, status="pending", password=None)
    _, plain = await seed_token(db_session, user_id=user.id, purpose="invite", clock=fake_clock)
    response = await _accept(auth_client, plain, "A", PASSWORD)
    assert response.status_code == 204
    refreshed = await auth_client.post("/api/auth/refresh", headers=ORIGIN)
    assert refreshed.status_code == 200


async def test_auth_accept_invitation__concurrent_same_token_one_wins(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Hai lượt N10 song song cùng token → một 204, một 422."""
    user = await make_user(db_session, status="pending", password=None)
    _, plain = await seed_token(db_session, user_id=user.id, purpose="invite", clock=fake_clock)
    first, second = await asyncio.gather(
        _accept(auth_client, plain, "A", "mat-khau-thu-nhat-01"),
        _accept(auth_client, plain, "B", "mat-khau-thu-hai-02"),
    )
    assert sorted([first.status_code, second.status_code]) == [204, 422]


async def test_auth_accept_invitation__disabled_mid_hash_stays_pending(
    auth_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Người bị `disabled` đúng lúc N10 đang băm → N10 422, người không thành `active`."""
    user = await make_user(db_session, status="pending", password=None)
    _, plain = await seed_token(db_session, user_id=user.id, purpose="invite", clock=fake_clock)
    started, proceed = asyncio.Event(), asyncio.Event()

    async def _blocking_hash(password: str) -> str:
        started.set()
        await proceed.wait()
        return await hash_password(password)

    monkeypatch.setattr(router, "hash_password", _blocking_hash)
    task = asyncio.create_task(_accept(auth_client, plain, "A", PASSWORD))
    await started.wait()
    async with db_sessionmaker() as setup:
        await setup.execute(update(User).where(User.id == user.id).values(status="disabled"))
        await setup.commit()
    proceed.set()
    response = await task
    assert response.status_code == 422
    assert response.json()["code"] == "INVITATION_TOKEN_INVALID"
    row = await user_row(db_session, user.id)
    assert row.status == "disabled"
