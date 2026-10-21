"""user_preferences

Revision ID: r20261021_fe3db4
Revises: r20261021_fe3db3
Create Date: 2026-10-21

FE3D-B4, expand thuần (BE-00 §6.1): `users.preferences` — tuỳ chọn tài khoản (giao diện, kênh thông báo,
cờ đã xem) mà trước đây FE chỉ giữ trong bộ nhớ. JSONB NOT NULL + `server_default '{}'`: dòng cũ và mã cũ
không ghi cột này đều nhận `{}`, không backfill. CHECK chỉ giữ "là object"; hình dạng bên trong do
`apps/api/me/schemas.py` kiểm ở biên HTTP.
"""

from collections.abc import Sequence
from typing import Final

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "r20261021_fe3db4"
down_revision: str | None = "r20261021_fe3db3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE: Final = "users"
COLUMN: Final = "preferences"
CHECK_NAME: Final = "ck_users_preferences_object"


def upgrade() -> None:
    """Thêm cột NOT NULL có `server_default '{}'` (dòng cũ nhận `{}` ngay) và CHECK là object."""
    op.add_column(
        TABLE,
        sa.Column(COLUMN, postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
    )
    op.create_check_constraint(op.f(CHECK_NAME), TABLE, f"jsonb_typeof({COLUMN}) = 'object'")


def downgrade() -> None:
    """Bỏ CHECK rồi bỏ cột (mất tuỳ chọn tài khoản; FE quay về mặc định; dữ liệu khác giữ nguyên)."""
    op.drop_constraint(op.f(CHECK_NAME), TABLE, type_="check")
    op.drop_column(TABLE, COLUMN)
