"""Đầu-cuối N8-N10 với Mailpit thật và worker Celery thật (B1-03 [2], [6], [8]).

`e2e_client` dựng app bằng `SystemClock()` (**không** `fake_clock`): task `send_token_mail`
chạy trong worker thật luôn dùng `SystemClock()` (`apps/api/auth_recovery/jobs.py:131`),
nên token phát bởi một app dùng đồng hồ giả cố định (2026-01-01) sẽ bị `active_clause` của
worker coi là đã hết hạn so với giờ hệ thống thật — thư sẽ không bao giờ gửi được.
"""

from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.auth.cookies import REFRESH_COOKIE, STREAM_COOKIE
from apps.api.auth.tests.support import cookie_value, refresh_with, set_cookies
from apps.api.auth_recovery.tokens import issue_token
from apps.api.core.app import create_app
from packages.core.clock import SystemClock
from packages.core.settings import get_core_settings
from packages.testing.factories.auth import TEST_PASSWORD, make_user
from packages.testing.fixtures.api import make_api_client
from packages.testing.fixtures.auth import ORIGIN, login
from packages.testing.fixtures.mail import MailpitInbox, extract_token
from packages.testing.fixtures.messaging import WorkerFactory

pytestmark = pytest.mark.usefixtures("auth_env")

MAIL_WAIT_S = 15.0
NEW_INVITE_PASSWORD = "mat-khau-e2e-loi-moi-01"  # noqa: S105 — mật khẩu giả của test
NEW_RESET_PASSWORD = "mat-khau-e2e-dat-lai-01"  # noqa: S105 — mật khẩu giả của test


@pytest_asyncio.fixture(loop_scope="function")
async def e2e_client() -> AsyncIterator[httpx.AsyncClient]:
    """App thật, đồng hồ **hệ thống** thật — khớp `SystemClock()` mà worker dùng (xem docstring module)."""
    app = create_app(get_core_settings())
    async with make_api_client(app) as client:
        yield client


async def test_invitation_accept_e2e(
    e2e_client: httpx.AsyncClient,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    mailpit_inbox: MailpitInbox,
    celery_worker_factory: WorkerFactory,
) -> None:
    """Người `pending` được mời: thư tới Mailpit thật qua worker thật, N10 nhận lời mời, refresh 200."""
    async with db_sessionmaker() as setup:
        user = await make_user(setup, status="pending", password=None)

    with celery_worker_factory(["default"]):
        async with db_sessionmaker() as issuing:
            await issue_token(issuing, user_id=user.id, purpose="invite", clock=SystemClock())
            await issuing.commit()
        message = mailpit_inbox.wait_for(user.email, MAIL_WAIT_S)

    token = extract_token(message)
    response = await e2e_client.post(
        "/api/auth/invitations/accept",
        json={"token": token, "fullName": "Người E2E", "password": NEW_INVITE_PASSWORD},
        headers=ORIGIN,
    )
    assert response.status_code == 204
    cookies = set_cookies(response)
    assert REFRESH_COOKIE in cookies
    assert STREAM_COOKIE in cookies
    assert (await e2e_client.post("/api/auth/refresh", headers=ORIGIN)).status_code == 200


async def test_password_reset_e2e(
    e2e_client: httpx.AsyncClient,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    mailpit_inbox: MailpitInbox,
    celery_worker_factory: WorkerFactory,
) -> None:
    """Người `active` đã đăng nhập: N8 → thư thật → N9; mật khẩu mới dùng được, phiên cũ bị thu hồi."""
    async with db_sessionmaker() as setup:
        user = await make_user(setup)

    logged_in = await login(e2e_client, user.email, TEST_PASSWORD)
    assert logged_in.status_code == 204, logged_in.text
    old_refresh = cookie_value(set_cookies(logged_in)[REFRESH_COOKIE])

    with celery_worker_factory(["default"]):
        requested = await e2e_client.post("/api/auth/password-reset", json={"email": user.email}, headers=ORIGIN)
        assert requested.status_code == 204
        message = mailpit_inbox.wait_for(user.email, MAIL_WAIT_S)

    token = extract_token(message)
    confirmed = await e2e_client.post(
        "/api/auth/password-reset/confirm",
        json={"token": token, "newPassword": NEW_RESET_PASSWORD},
        headers=ORIGIN,
    )
    assert confirmed.status_code == 204

    assert (await login(e2e_client, user.email, TEST_PASSWORD)).status_code == 401
    assert (await login(e2e_client, user.email, NEW_RESET_PASSWORD)).status_code == 204

    denied = await refresh_with(e2e_client, old_refresh)
    assert denied.status_code == 401
    assert denied.json()["code"] == "SESSION_REVOKED"
