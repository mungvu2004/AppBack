"""NO-168/NO-169: ULID trần và luật Cc/bidi của `/api/me` nằm ở `packages.core`, không chép lại."""

import inspect

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth.tests.support import user_row
from apps.api.me import router, schemas
from apps.api.me.tests.support import b64, headers_of, png_bytes, principal_of
from packages.core.ids import is_ulid
from packages.testing.factories.auth import make_user


def test_me_schemas__reuses_core_text() -> None:
    """`schemas.py` không tự khai tập ký tự đảo chiều (U+202A…) — gọi `packages.core.text`."""
    source = inspect.getsource(schemas)
    assert "0x202A" not in source
    assert "\u202a" not in source


def test_me_router__reuses_core_new_ulid() -> None:
    """Tên object ảnh đại diện lấy ULID từ `new_ulid`, không cắt tiền tố của `new_id`."""
    assert '.split("_", 1)' not in inspect.getsource(router)


@pytest.mark.usefixtures("api_env")
async def test_me_replace_avatar__stored_key_name_is_a_bare_ulid(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Hành vi, không chỉ chuỗi nguồn: khoá lưu sau `PUT /api/me/avatar` có tên là ULID trần hợp lệ."""
    user = await make_user(db_session)
    response = await api_client.put(
        "/api/me/avatar",
        json={"mimeType": "image/png", "contentBase64": b64(png_bytes())},
        headers=headers_of(principal_of(user)),
    )
    assert response.status_code == 200
    row = await user_row(db_session, user.id)
    assert row.avatar_key is not None
    name = row.avatar_key.rsplit("/", 1)[-1]
    assert is_ulid(name.partition(".")[0])
