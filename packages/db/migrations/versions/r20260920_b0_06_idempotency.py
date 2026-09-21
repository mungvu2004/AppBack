"""idempotency

Revision ID: r20260920_b0_06
Revises: r20260920_b0_03
Create Date: 2026-09-20

Bảng `idempotency_records` của khung API (BE-00 §7). Chỉ tạo bảng và index — không
đụng bảng nào khác, nên thuộc nhánh "expand" và lùi được bằng `downgrade()`.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "r20260920_b0_06"
down_revision: str | None = "r20260920_b0_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "idempotency_records"


def upgrade() -> None:
    """Expand: bảng mới, không đụng bảng nào đang có (BE-00 §6.1)."""
    op.create_table(
        TABLE,
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("route_template", sa.String(length=255), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("claim_token", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("response_body", sa.LargeBinary(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("state IN ('in_progress', 'completed')", name=f"ck_{TABLE}_state"),
        sa.CheckConstraint("key ~ '^[A-Za-z0-9_-]{8,128}$'", name=f"ck_{TABLE}_key_format"),
        sa.PrimaryKeyConstraint("id", name=f"pk_{TABLE}"),
        sa.UniqueConstraint(
            "user_id",
            "method",
            "route_template",
            "key",
            name=f"uq_{TABLE}_user_id_method_route_template_key",
        ),
    )
    op.create_index(f"ix_{TABLE}_expires_at", TABLE, ["expires_at"], unique=False)


def downgrade() -> None:
    """Bỏ bảng; bản ghi idempotency sống 24 h nên mất chúng chỉ mất khả năng trả lại."""
    op.drop_index(f"ix_{TABLE}_expires_at", table_name=TABLE)
    op.drop_table(TABLE)
