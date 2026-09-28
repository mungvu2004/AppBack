"""library

Revision ID: r20260928_b2_06
Revises: r20260926_b2_05b
Create Date: 2026-09-28

Bảng `library_items` (B2-06 [5], BE-00 §6.1): expand thuần, một bảng mới và một FK sang
`users`. Hằng số chép tay từ `packages/db/models/library.py`, không nhập module model.
Tên constraint bọc `op.f(...)` để quy ước của `Base.metadata` không ghép tiền tố lần hai.

Luật expand/contract: BE-00 §6.1 (`tools/lint_migrations.py` chặn drop/rename/NOT NULL).
"""

from collections.abc import Sequence
from typing import Final

import sqlalchemy as sa
from alembic import op

revision: str = "r20260928_b2_06"
down_revision: str | None = "r20260926_b2_05b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LIBRARY_ITEMS: Final = "library_items"
USERS: Final = "users"


def upgrade() -> None:
    """Expand: bảng mới, mọi cột ngoài danh tính NULL được (seed chỉ ghi danh tính)."""
    op.create_table(
        LIBRARY_ITEMS,
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("item_group", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=True),
        sa.Column("width_mm", sa.Integer(), nullable=True),
        sa.Column("depth_mm", sa.Integer(), nullable=True),
        sa.Column("height_mm", sa.Integer(), nullable=True),
        sa.Column("triangle_count", sa.Integer(), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("model_key", sa.Text(), nullable=True),
        sa.Column("model_sha256", sa.CHAR(64), nullable=True),
        sa.Column("preview_key", sa.Text(), nullable=True),
        sa.Column("preview_sha256", sa.CHAR(64), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("id ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name=op.f(f"ck_{LIBRARY_ITEMS}_id_format")),
        sa.CheckConstraint("char_length(id) <= 64", name=op.f(f"ck_{LIBRARY_ITEMS}_id_length")),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 120", name=op.f(f"ck_{LIBRARY_ITEMS}_name_length")),
        sa.CheckConstraint(
            "item_group IN ('table', 'chair', 'bed', 'sofa', 'storage', 'sanitary', 'kitchen', 'technical')",
            name=op.f(f"ck_{LIBRARY_ITEMS}_item_group"),
        ),
        sa.CheckConstraint(
            "published_at IS NULL OR (COALESCE(width_mm, 0) > 0 AND COALESCE(depth_mm, 0) > 0"
            " AND COALESCE(height_mm, 0) > 0"
            " AND COALESCE(triangle_count, 0) > 0 AND COALESCE(file_size_bytes, 0) > 0"
            " AND model_key IS NOT NULL AND model_sha256 IS NOT NULL)",
            name=op.f(f"ck_{LIBRARY_ITEMS}_published"),
        ),
        sa.CheckConstraint(
            "(preview_key IS NULL) = (preview_sha256 IS NULL)", name=op.f(f"ck_{LIBRARY_ITEMS}_preview_pair")
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            [f"{USERS}.id"],
            name=op.f(f"fk_{LIBRARY_ITEMS}_owner_id_{USERS}"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=f"pk_{LIBRARY_ITEMS}"),
    )
    op.create_index(
        f"ix_{LIBRARY_ITEMS}_sort_order_id_live",
        LIBRARY_ITEMS,
        ["sort_order", "id"],
        postgresql_where=sa.text("published_at IS NOT NULL AND retired_at IS NULL"),
    )


def downgrade() -> None:
    """Bỏ bảng (kéo theo index); không bảng nào khác trỏ tới nó."""
    op.drop_table(LIBRARY_ITEMS)
