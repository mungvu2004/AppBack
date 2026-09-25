"""Đầu-cuối #44 với Mailpit và worker Celery thật (B1-05 [8]): mời → thư → N10 → đăng nhập.

Dùng `SystemClock()` như `apps/api/auth_recovery/tests/test_e2e.py`: task `send_token_mail` của worker
thật dùng đồng hồ hệ thống, nên token phát bởi app đồng hồ giả sẽ bị coi là hết hạn.
"""

from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import apps.api.auth_recovery.jobs  # noqa: F401 — nhập để đăng ký task `send_token_mail` với worker thật
from apps.api.core.app import create_app
from apps.api.users.tests.support import USERS, make_admin
from packages.core.settings import get_core_settings
from packages.testing.fixtures.api import make_api_client
from packages.testing.fixtures.auth import ORIGIN, login, sign_in
from packages.testing.fixtures.mail import MailpitInbox, extract_token
from packages.testing.fixtures.messaging import WorkerFactory

pytestmark = pytest.mark.usefixtures("auth_env")

MAIL_WAIT_S = 15.0
NEW_PASSWORD = "mat-khau-e2e-quan-tri-01"  # noqa: S105 — mật khẩu giả của test


@pytest_asyncio.fixture(loop_scope="function")
async def e2e_client() -> AsyncIterator[httpx.AsyncClient]:
    """App thật, đồng hồ **hệ thống** thật, verifier thật."""
    async with make_api_client(create_app(get_core_settings())) as client:
        yield client


async def test_invited_user_can_accept_and_sign_in(
    e2e_client: httpx.AsyncClient,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    mailpit_inbox: MailpitInbox,
    celery_worker_factory: WorkerFactory,
) -> None:
    """Admin mời một email: thư tới Mailpit thật qua worker thật, N10 nhận lời mời, người đó đăng nhập được."""
    async with db_sessionmaker() as setup:
        admin = await make_admin(setup)
    session = await sign_in(e2e_client, admin)
    email = "nguoi-moi-e2e@example.com"

    with celery_worker_factory(["default"]):
        invited = await e2e_client.post(
            f"{USERS}/invitations", json={"emails": [email], "role": "engineer"}, headers=session.headers
        )
        assert invited.status_code == 201
        message = mailpit_inbox.wait_for(email, MAIL_WAIT_S)

    accepted = await e2e_client.post(
        "/api/auth/invitations/accept",
        json={"token": extract_token(message), "fullName": "Người Mới", "password": NEW_PASSWORD},
        headers=ORIGIN,
    )
    assert accepted.status_code == 204
    async with make_api_client(create_app(get_core_settings())) as fresh:
        assert (await login(fresh, email, NEW_PASSWORD)).status_code == 204
