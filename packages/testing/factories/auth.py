"""Factory người dùng cho test (B1-01).

`make_user` ghi thẳng một dòng `users` (không qua API) và **commit**, để app thử — chạy
trên pool riêng — đọc thấy ngay. Mật khẩu băm bằng đúng `hash_password` của sản phẩm,
nên cùng `ARGON2_PROFILE` với lượt đăng nhập đi so (C27).
"""

import secrets
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth.passwords import hash_password
from packages.core.clock import SystemClock
from packages.core.ids import new_id
from packages.core.text import nfc, normalize_email
from packages.db.models.auth import User

TEST_PASSWORD: Final = "mat-khau-thu-nghiem-01"  # noqa: S105 — mật khẩu giả của bộ test, không bảo vệ gì
DEFAULT_NAME: Final = "Người dùng thử"


async def make_user(
    db: AsyncSession,
    *,
    role: str = "engineer",
    status: str = "active",
    password: str | None = TEST_PASSWORD,
    email: str | None = None,
    name: str | None = None,
) -> User:
    """Một người dùng đã commit; `password=None` → chưa có mật khẩu (như người `pending`)."""
    address = email if email is not None else f"nguoi-{secrets.token_hex(6)}@example.com"
    user = User(
        id=new_id("usr", SystemClock()),
        email=nfc(address.strip()),
        email_normalized=normalize_email(address),
        name=nfc(name if name is not None else DEFAULT_NAME),
        password_hash=None if password is None else await hash_password(password),
        role=role,
        status=status,
    )
    db.add(user)
    await db.commit()
    return user
