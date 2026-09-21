"""auth

Revision ID: r20260921_b1_01
Revises: r20260920_b0_06
Create Date: 2026-09-21

Bảng `users` và `refresh_sessions` của đăng nhập và phiên (B1-01, BE-00 §5). Chỉ tạo
bảng và index mới, không đụng bảng nào đang có: thuộc nhánh "expand", lùi được bằng
`downgrade()`. Index tạo cùng revision với bảng nên không cần `CONCURRENTLY` (§6.1). Tên `CHECK` đã đầy đủ
nên bọc `op.f(...)`: quy ước `ck_%(table_name)s_%(constraint_name)s` của `Base.metadata` không
ghép tiền tố lần hai (`ck_users_ck_users_role`), tên trong DB đúng bằng tên của model.
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "r20260921_b1_01"
down_revision: str | None = "r20260920_b0_06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

USERS = "users"
SESSIONS = "refresh_sessions"


def _timestamps() -> list[sa.Column[Any]]:
    """`created_at`, `updated_at` đúng như `TimestampMixin`."""
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def _create_users() -> None:
    """Bảng `users` + unique email trên dòng chưa xoá mềm."""
    op.create_table(
        USERS,
        *_timestamps(),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("email_normalized", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("token_version", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("job_title", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("language", sa.Text(), server_default=sa.text("'vi'"), nullable=False),
        sa.Column("avatar_key", sa.Text(), nullable=True),
        sa.CheckConstraint("role IN ('admin', 'engineer', 'viewer')", name=op.f(f"ck_{USERS}_role")),
        sa.CheckConstraint("status IN ('active', 'pending', 'disabled')", name=op.f(f"ck_{USERS}_status")),
        sa.CheckConstraint("language IN ('vi', 'en')", name=op.f(f"ck_{USERS}_language")),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 120", name=op.f(f"ck_{USERS}_name_length")),
        sa.CheckConstraint("token_version >= 0", name=op.f(f"ck_{USERS}_token_version")),
        sa.PrimaryKeyConstraint("id", name=f"pk_{USERS}"),
    )
    op.create_index(
        "uq_users_email", USERS, ["email_normalized"], unique=True, postgresql_where=sa.text("deleted_at IS NULL")
    )


def _create_sessions() -> None:
    """Bảng `refresh_sessions` + ba index (phiên sống theo người, hai điều kiện của lịch dọn)."""
    op.create_table(
        SESSIONS,
        *_timestamps(),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("current_token_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("previous_token_hash", sa.CHAR(length=64), nullable=True),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("remember", sa.Boolean(), nullable=False),
        sa.Column("idle_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.Text(), nullable=True),
        sa.Column("created_ip", postgresql.INET(), nullable=True),
        sa.CheckConstraint(
            "revoked_reason IN ('logout', 'reuse', 'replaced', 'password_change', 'password_reset', "
            "'disabled', 'deleted', 'expired')",
            name=op.f(f"ck_{SESSIONS}_revoked_reason"),
        ),
        sa.CheckConstraint("(revoked_at IS NULL) = (revoked_reason IS NULL)", name=op.f(f"ck_{SESSIONS}_revoked_pair")),
        sa.ForeignKeyConstraint(["user_id"], [f"{USERS}.id"], name=f"fk_{SESSIONS}_user_id_{USERS}"),
        sa.PrimaryKeyConstraint("id", name=f"pk_{SESSIONS}"),
    )
    op.create_index(
        f"ix_{SESSIONS}_user_id_live", SESSIONS, ["user_id"], postgresql_where=sa.text("revoked_at IS NULL")
    )
    op.create_index(f"ix_{SESSIONS}_absolute_expires_at", SESSIONS, ["absolute_expires_at"])
    op.create_index(
        f"ix_{SESSIONS}_revoked_at", SESSIONS, ["revoked_at"], postgresql_where=sa.text("revoked_at IS NOT NULL")
    )


def upgrade() -> None:
    """Expand: hai bảng mới, không đụng bảng nào đang có (BE-00 §6.1)."""
    _create_users()
    _create_sessions()


def downgrade() -> None:
    """Bỏ hai bảng; mọi người dùng và phiên mất theo — chỉ dùng trước khi có dữ liệu thật."""
    op.drop_index(f"ix_{SESSIONS}_revoked_at", table_name=SESSIONS)
    op.drop_index(f"ix_{SESSIONS}_absolute_expires_at", table_name=SESSIONS)
    op.drop_index(f"ix_{SESSIONS}_user_id_live", table_name=SESSIONS)
    op.drop_table(SESSIONS)
    op.drop_index("uq_users_email", table_name=USERS)
    op.drop_table(USERS)
