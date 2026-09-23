"""one_time_tokens

Revision ID: r20260923_b1_03
Revises: r20260923_b2_01
Create Date: 2026-09-23

Bảng `one_time_tokens` của token một lời (mời, quên mật khẩu) (B1-03, BE-00 §5). Chỉ
tạo bảng mới, không đụng bảng nào đang có: thuộc nhánh "expand", lùi được bằng
`downgrade()`. Index tạo cùng revision với bảng nên không cần `CONCURRENTLY` (§6.1).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "r20260923_b1_03"
down_revision: str | None = "r20260923_b2_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "one_time_tokens"
USERS = "users"


def upgrade() -> None:
    """Expand: một bảng mới, không đụng bảng nào đang có (BE-00 §6.1)."""
    op.create_table(
        TABLE,
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("nonce", sa.LargeBinary(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("purpose IN ('invite', 'password_reset')", name=op.f(f"ck_{TABLE}_purpose")),
        sa.CheckConstraint("octet_length(nonce) = 16", name=op.f(f"ck_{TABLE}_nonce_length")),
        sa.ForeignKeyConstraint(["user_id"], [f"{USERS}.id"], name=f"fk_{TABLE}_user_id_{USERS}"),
        sa.PrimaryKeyConstraint("id", name=f"pk_{TABLE}"),
        sa.UniqueConstraint("token_hash", name=op.f(f"uq_{TABLE}_token_hash")),
    )
    op.create_index(
        f"uq_{TABLE}_user_id_purpose",
        TABLE,
        ["user_id", "purpose"],
        unique=True,
        postgresql_where=sa.text("used_at IS NULL AND superseded_at IS NULL"),
    )
    op.create_index(
        f"ix_{TABLE}_sent_at_created_at", TABLE, ["sent_at", "created_at"], postgresql_where=sa.text("sent_at IS NULL")
    )


def downgrade() -> None:
    """Bỏ bảng; mọi token một lời mất theo — chỉ dùng trước khi có dữ liệu thật."""
    op.drop_index(f"ix_{TABLE}_sent_at_created_at", table_name=TABLE)
    op.drop_index(f"uq_{TABLE}_user_id_purpose", table_name=TABLE)
    op.drop_table(TABLE)
