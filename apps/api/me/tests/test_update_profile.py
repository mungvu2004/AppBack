"""`PATCH /api/me` — N12 `me_update_profile` (B1-04 [6], [8]; CASE loại G*: C01 C02 C03 C17, `cases.toml` C16)."""

import unicodedata

import httpx
import pytest
from pydantic.alias_generators import to_camel
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.me.router import _COLUMN_OF, _NULLABLE_ON_EMPTY
from apps.api.me.tests.support import headers_of, principal_of
from packages.db.models.auth import User
from packages.testing.factories.auth import make_user

pytestmark = pytest.mark.usefixtures("api_env")

PATH = "/api/me"

NOT_NULLABLE_FIELDS = sorted(_COLUMN_OF.keys() - _NULLABLE_ON_EMPTY)
"""Khoá của `_COLUMN_OF` ánh xạ cột `NOT NULL` — thêm cột `NOT NULL` mới mà quên đưa vào
`_NULLABLE_ON_EMPTY` (hay quên chặn `null`) thì sweep test dưới đây đỏ ngay (NO-165, R-19)."""


async def _patch(client: httpx.AsyncClient, user: User, body: dict[str, object]) -> httpx.Response:
    return await client.patch(PATH, json=body, headers=headers_of(principal_of(user)))


async def test_me_update_profile__C01(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Đúng: ghi các cột có mặt, đọc lại sau ghi (K22); khoá vắng giữ nguyên."""
    user = await make_user(db_session, name="Cũ", role="engineer")
    response = await _patch(api_client, user, {"jobTitle": "Kỹ sư", "phone": "0900000000"})
    assert response.status_code == 200
    body = response.json()
    assert body["fullName"] == "Cũ"  # không gửi → giữ nguyên
    assert body["jobTitle"] == "Kỹ sư"
    assert body["phone"] == "0900000000"


async def test_me_update_profile_language_valid_value_is_saved(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """`language: "en"` hợp lệ → 200, lưu đúng giá trị (nhánh thành công của validator, đối lập NO-165)."""
    user = await make_user(db_session)
    response = await _patch(api_client, user, {"language": "en"})
    assert response.status_code == 200
    assert response.json()["language"] == "en"


@pytest.mark.parametrize("bad_body", [{"language": "fr"}, {"fullName": 7}])
async def test_me_update_profile__C02(
    api_client: httpx.AsyncClient, db_session: AsyncSession, bad_body: dict[str, object]
) -> None:
    """Sai kiểu/giá trị → 422 `VALIDATION` có `field`."""
    user = await make_user(db_session)
    response = await _patch(api_client, user, bad_body)
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"
    assert "field" in response.json()


async def test_me_update_profile__C03(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Khoá lạ trong thân → 422 `VALIDATION` (thân `.strict()`, W1)."""
    user = await make_user(db_session)
    response = await _patch(api_client, user, {"jobTitle": "A", "extra": 1})
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"


async def test_me_update_profile__C17(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Sau khi xoá `jobTitle` (gửi `''`), trường vắng khoá ở response (K02)."""
    user = await make_user(db_session, name="X")
    seeded = await _patch(api_client, user, {"jobTitle": "Có giá trị"})
    assert seeded.json()["jobTitle"] == "Có giá trị"
    cleared = await _patch(api_client, user, {"jobTitle": ""})
    assert cleared.status_code == 200
    assert "jobTitle" not in cleared.json()


async def test_me_update_profile__C16(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """`fullName` NFD → lưu và trả NFC (cases.toml extra)."""
    user = await make_user(db_session)
    nfd_name = unicodedata.normalize("NFD", "Nguyễn Thị Hà")
    response = await _patch(api_client, user, {"fullName": nfd_name})
    assert response.status_code == 200
    assert response.json()["fullName"] == unicodedata.normalize("NFC", nfd_name)
    assert response.json()["fullName"] == "Nguyễn Thị Hà"


async def test_me_update_profile_no_keys_is_422_without_field(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Thân không khoá nào → 422 `VALIDATION` **không** kèm `field`."""
    user = await make_user(db_session)
    response = await _patch(api_client, user, {})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION"
    assert "field" not in body


async def test_me_update_profile_full_name_whitespace_only_is_422(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """`fullName` toàn khoảng trắng → 422 `field:"fullName"`."""
    user = await make_user(db_session)
    response = await _patch(api_client, user, {"fullName": "   "})
    assert response.status_code == 422
    assert response.json()["field"] == "fullName"


async def test_me_update_profile_job_title_whitespace_only_clears(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """`jobTitle`/`phone` toàn khoảng trắng coi như `''` (xoá), không 422."""
    user = await make_user(db_session)
    await _patch(api_client, user, {"jobTitle": "Có giá trị", "phone": "0900000000"})
    response = await _patch(api_client, user, {"jobTitle": "   ", "phone": "  "})
    assert response.status_code == 200
    body = response.json()
    assert "jobTitle" not in body
    assert "phone" not in body


async def test_me_update_profile_forbidden_control_char_is_422(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Ký tự điều khiển (Cc) trong `fullName` → 422 `field:"fullName"`."""
    user = await make_user(db_session)
    response = await _patch(api_client, user, {"fullName": "Tên\x00lạ"})
    assert response.status_code == 422
    assert response.json()["field"] == "fullName"


async def test_me_update_profile_bidi_override_is_422(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Ký tự đảo chiều song hướng U+202E trong `jobTitle` → 422 `field:"jobTitle"`."""
    user = await make_user(db_session)
    response = await _patch(api_client, user, {"jobTitle": "A‮B"})
    assert response.status_code == 422
    assert response.json()["field"] == "jobTitle"


async def test_me_update_profile_server_owned_field_is_rejected(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Thân có `email` (server sở hữu) → 422, email không đổi."""
    user = await make_user(db_session)
    response = await _patch(api_client, user, {"email": "khac@example.com"})
    assert response.status_code == 422
    reread = await api_client.get(PATH, headers=headers_of(principal_of(user)))
    assert reread.json()["email"] == user.email


async def test_me_update_profile_session_revoked_when_user_deleted(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Người của `Principal` đã xoá mềm → 401 `SESSION_REVOKED`."""
    user = await make_user(db_session)
    user.deleted_at = user.created_at
    await db_session.commit()
    response = await _patch(api_client, user, {"jobTitle": "X"})
    assert response.status_code == 401
    assert response.json()["code"] == "SESSION_REVOKED"


@pytest.mark.parametrize("field", NOT_NULLABLE_FIELDS)
async def test_me_update_profile_not_nullable_field_explicit_null_is_422(
    api_client: httpx.AsyncClient, db_session: AsyncSession, field: str
) -> None:
    """`null` tường minh trên khoá ánh xạ cột `NOT NULL` → 422, cột không đổi (NO-165; quét cả `_COLUMN_OF`)."""
    user = await make_user(db_session)
    alias = to_camel(field)
    response = await _patch(api_client, user, {alias: None})
    assert response.status_code == 422
    assert response.json()["field"] == alias

    reread = await api_client.get(PATH, headers=headers_of(principal_of(user)))
    assert reread.status_code == 200  # không 500 — cột không bị NULL hoá


async def test_me_update_profile_job_title_and_phone_explicit_null_clears(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """`jobTitle`/`phone: null` tường minh → xoá cột, như gửi `''`."""
    user = await make_user(db_session)
    await _patch(api_client, user, {"jobTitle": "Có giá trị", "phone": "0900000000"})
    response = await _patch(api_client, user, {"jobTitle": None, "phone": None})
    assert response.status_code == 200
    body = response.json()
    assert "jobTitle" not in body
    assert "phone" not in body


async def test_me_update_profile_phone_too_long_is_422(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """`phone` > 32 ký tự → 422 `field:"phone"`."""
    user = await make_user(db_session)
    response = await _patch(api_client, user, {"phone": "0" * 33})
    assert response.status_code == 422
    assert response.json()["field"] == "phone"
