"""Seed người dùng admin cố định cho môi trường không phải production (NO-107).

H2 (`tools/ci/h2.py`) gửi token `fake:<id>:…:admin`; `FakeTokenVerifier` không tra DB nên id phải
có thật trong `users` khi route ghi chạm FK (`project_memberships.user_id`) hay đọc principal từ DB.
Một nguồn duy nhất: H2 và test nhập `SEED_ADMIN_ID` từ đây, không dựng tay.

`password_hash=NULL` nên không đăng nhập bằng mật khẩu được; không có ở `production`/`staging`.
Admin bị xoá mềm không được hồi sinh (dòng vẫn giữ id). Idempotent: `ON CONFLICT (id) DO NOTHING`
(xung đột email vẫn nổi lỗi) — chạy lại không nhân bản, không ghi đè dòng đã sửa.
"""

from typing import Final

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.text import nfc, normalize_email
from packages.db.models.auth import User

ORDER: Final = 10
ENVS: Final = frozenset({"dev", "test", "ci"})
SEED_ADMIN_ID: Final = "usr_01JB302" + "0" * 19
SEED_ADMIN_EMAIL: Final = "seed-admin@example.com"


async def seed(session: AsyncSession) -> None:
    """Chèn admin seed `SEED_ADMIN_ID` (vai `admin`, `active`) nếu chưa có; chạy lại không đổi gì."""
    await session.execute(
        insert(User)
        .values(
            id=SEED_ADMIN_ID,
            email=nfc(SEED_ADMIN_EMAIL),
            email_normalized=normalize_email(SEED_ADMIN_EMAIL),
            name="Seed admin",
            password_hash=None,
            role="admin",
            status="active",
        )
        .on_conflict_do_nothing(index_elements=[User.id])
    )
