"""`POST /api/auth/invitations/preview` (UIFIX-B2: G2-9, G2-10, G1-10; CASE loại C)."""

from datetime import timedelta
from typing import Any, Final

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.access.activity import record_activity
from apps.api.access.kinds import ActivityKind
from apps.api.auth_recovery.settings import get_recovery_settings
from apps.api.auth_recovery.tests.support import seed_token
from packages.testing.factories.auth import make_user
from packages.testing.fixtures.auth import ORIGIN
from packages.testing.fixtures.clock import FakeClock

pytestmark = pytest.mark.usefixtures("api_env")

PATH: Final = "/api/auth/invitations/preview"


async def _preview(client: httpx.AsyncClient, token: str) -> httpx.Response:
    """Một lượt `POST /api/auth/invitations/preview` đúng `Origin`."""
    return await client.post(PATH, json={"token": token}, headers=ORIGIN)


async def _pending_with_token(db: AsyncSession, clock: FakeClock, **token_kwargs: Any) -> tuple[str, str]:
    """Người `pending` (vai viewer) và token `invite` của họ; trả `(email, token bản rõ)`."""
    user = await make_user(db, status="pending", password=None, role="viewer")
    _, plain = await seed_token(db, user_id=user.id, purpose="invite", clock=clock, **token_kwargs)
    return user.email, plain


async def test_auth_preview_invitation__C01(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Đúng: 200, email/vai/tên người mời/hạn; không id, không trạng thái nội bộ; token chưa bị tiêu."""
    admin = await make_user(db_session, role="admin", name="Quản Trị Viên")
    invitee = await make_user(db_session, status="pending", password=None, role="engineer")
    await record_activity(
        db_session,
        actor_id=admin.id,
        kind=ActivityKind.USER_INVITE,
        object_code=invitee.id,
        object_label=invitee.email,
        clock=fake_clock,
    )
    await db_session.commit()
    _, plain = await seed_token(db_session, user_id=invitee.id, purpose="invite", clock=fake_clock)
    response = await _preview(auth_client, plain)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"status", "email", "role", "inviterName", "expiresAt"}
    assert body["status"] == "valid"
    assert (body["email"], body["role"], body["inviterName"]) == (invitee.email, "engineer", "Quản Trị Viên")
    assert body["expiresAt"].endswith("Z")
    again = await _preview(auth_client, plain)
    assert again.status_code == 200


async def test_auth_preview_invitation__C01_no_inviter(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Không có dòng nhật ký mời → bỏ `inviterName` (W2), vẫn 200."""
    email, plain = await _pending_with_token(db_session, fake_clock)
    response = await _preview(auth_client, plain)
    assert response.status_code == 200
    body = response.json()
    assert "inviterName" not in body
    assert (body["email"], body["role"]) == (email, "viewer")


async def test_auth_preview_invitation__C02(auth_client: httpx.AsyncClient) -> None:
    """Token rỗng/quá dài → 422 `field:"token"`."""
    for token in ("", "x" * 513):
        response = await _preview(auth_client, token)
        assert response.status_code == 422
        assert response.json()["field"] == "token"


async def test_auth_preview_invitation__C03(auth_client: httpx.AsyncClient) -> None:
    """Khoá lạ → 422 `VALIDATION`."""
    response = await auth_client.post(PATH, json={"token": "x" * 10, "extra": 1}, headers=ORIGIN)
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"


async def test_auth_preview_invitation__C11(auth_client: httpx.AsyncClient) -> None:
    """Vượt `recovery_ip` → 429; hạn mức dùng chung với N8/N9/N10."""
    for _ in range(get_recovery_settings().recovery_ip_limit):
        assert (await _preview(auth_client, "x" * 20)).status_code == 422
    blocked = await _preview(auth_client, "x" * 20)
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "RATE_LIMITED"


async def test_auth_preview_invitation__C24(auth_client: httpx.AsyncClient) -> None:
    """Thiếu/lệch `Origin` → 403 `ORIGIN_MISMATCH`."""
    missing = await auth_client.post(PATH, json={"token": "x" * 10})
    foreign = await auth_client.post(PATH, json={"token": "x" * 10}, headers={"Origin": "https://ke-gian.example"})
    for response in (missing, foreign):
        assert response.status_code == 403
        assert response.json()["code"] == "ORIGIN_MISMATCH"


async def test_auth_preview_invitation__C26_unknown(auth_client: httpx.AsyncClient) -> None:
    """Token không tồn tại (link sai) → 422 `INVITATION_TOKEN_INVALID`, không lộ email."""
    response = await _preview(auth_client, "z" * 43)
    assert response.status_code == 422
    assert response.json()["code"] == "INVITATION_TOKEN_INVALID"
    assert "email" not in response.json()


async def test_auth_preview_invitation__C26_wrong_purpose(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Token `password_reset` dùng làm lời mời → 422 `INVITATION_TOKEN_INVALID`."""
    user = await make_user(db_session, status="pending", password=None)
    _, plain = await seed_token(db_session, user_id=user.id, purpose="password_reset", clock=fake_clock)
    response = await _preview(auth_client, plain)
    assert response.json()["code"] == "INVITATION_TOKEN_INVALID"


async def test_auth_preview_invitation__C26_expired(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Quá hạn → 422 `INVITATION_TOKEN_EXPIRED` (khác mã link sai, G1-10)."""
    _, plain = await _pending_with_token(db_session, fake_clock, ttl=timedelta(seconds=-1))
    response = await _preview(auth_client, plain)
    assert response.status_code == 422
    assert response.json()["code"] == "INVITATION_TOKEN_EXPIRED"


async def test_auth_preview_invitation__C26_superseded(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Link cũ sau khi "Gửi lại" → 422 `INVITATION_TOKEN_EXPIRED` (G2-9)."""
    _, plain = await _pending_with_token(db_session, fake_clock, superseded_at=fake_clock.now())
    assert (await _preview(auth_client, plain)).json()["code"] == "INVITATION_TOKEN_EXPIRED"


async def test_auth_preview_invitation__C26_used(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Token đã dùng → 422 `INVITATION_TOKEN_USED`."""
    _, plain = await _pending_with_token(db_session, fake_clock, used_at=fake_clock.now())
    response = await _preview(auth_client, plain)
    assert response.status_code == 422
    assert response.json()["code"] == "INVITATION_TOKEN_USED"


async def test_auth_preview_invitation__C26_already_active(
    auth_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Người đã `active` (nhận rồi) dù token chưa đánh dấu → 422 `INVITATION_TOKEN_USED`."""
    user = await make_user(db_session)
    _, plain = await seed_token(db_session, user_id=user.id, purpose="invite", clock=fake_clock)
    assert (await _preview(auth_client, plain)).json()["code"] == "INVITATION_TOKEN_USED"
