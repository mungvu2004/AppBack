"""`GET /api/me` — N11 `me_read_profile` (B1-04 [6], [8]; CASE loại Đ*: C01, C17)."""

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.me.tests.support import headers_of, principal_of
from packages.testing.factories.auth import make_user

pytestmark = pytest.mark.usefixtures("api_env")

PATH = "/api/me"


async def test_me_read_profile__C01(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Đúng: 200, `MeSchema` đủ trường khi hồ sơ đủ khoá (K01/K02)."""
    user = await make_user(db_session, name="Nguyễn Văn A")
    response = await api_client.get(PATH, headers=headers_of(principal_of(user)))
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == user.email
    assert body["fullName"] == "Nguyễn Văn A"
    assert body["language"] == "vi"
    assert set(body) == {"email", "fullName", "language"}  # jobTitle/phone/avatarUrl vắng


async def test_me_read_profile__C17(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Trường tuỳ chọn `NULL` → vắng khoá, không `null` (K02)."""
    user = await make_user(db_session)
    response = await api_client.get(PATH, headers=headers_of(principal_of(user)))
    body = response.json()
    for key in ("jobTitle", "phone", "avatarUrl"):
        assert key not in body


async def test_me_read_profile_session_revoked_when_user_deleted(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Người dùng của `Principal` không còn (xoá mềm) → 401 `SESSION_REVOKED`, không 500 (K30)."""
    user = await make_user(db_session)
    user.deleted_at = user.created_at
    await db_session.commit()
    response = await api_client.get(PATH, headers=headers_of(principal_of(user)))
    assert response.status_code == 401
    assert response.json()["code"] == "SESSION_REVOKED"
