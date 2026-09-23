"""floors

Revision ID: r20260923_b2_03
Revises: r20260923_b1_03
Create Date: 2026-09-23

Một bảng mới `floors` (B2-03 [5], BE-00 §6.1): expand thuần, không đụng bảng nào đang
có. Hằng số chép tay từ `packages/db/models/floors.py`, không nhập module model
(BE-00 §6.1: migration phải tự đứng vững kể cả khi model sau này đổi).

FK `project_id → projects.id` là `ON DELETE CASCADE` (như `r20260923_b2_01_projects.py`):
lịch dọn xoá cứng dự án bằng một lệnh `DELETE FROM projects`, không phải nhiều lệnh
theo thứ tự bảng con.

Luật expand/contract: BE-00 §6.1 (`tools/lint_migrations.py` chặn drop/rename/NOT NULL).
"""

from collections.abc import Sequence
from typing import Final

import sqlalchemy as sa
from alembic import op

revision: str = "r20260923_b2_03"
down_revision: str | None = "r20260923_b1_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FLOORS: Final = "floors"
PROJECTS: Final = "projects"


def upgrade() -> None:
    """Expand: một bảng mới `floors` cùng ba index một phần (BE-00 §6.1)."""
    op.create_table(
        FLOORS,
        sa.Column("pk", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("level_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("floor_order", sa.Integer(), nullable=False),
        sa.Column("elevation_mm", sa.BigInteger(), nullable=False),
        sa.Column("height_mm", sa.BigInteger(), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("level_id ~ '^L-[0-9A-Z]{10,64}$'", name=op.f(f"ck_{FLOORS}_level_id_format")),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 120", name=op.f(f"ck_{FLOORS}_name_length")),
        sa.CheckConstraint("floor_order BETWEEN 0 AND 999", name=op.f(f"ck_{FLOORS}_floor_order_range")),
        sa.CheckConstraint("elevation_mm BETWEEN -30000 AND 300000", name=op.f(f"ck_{FLOORS}_elevation_mm_range")),
        sa.CheckConstraint("height_mm BETWEEN 2000 AND 10000", name=op.f(f"ck_{FLOORS}_height_mm_range")),
        sa.ForeignKeyConstraint(
            ["project_id"], [f"{PROJECTS}.id"], name=op.f(f"fk_{FLOORS}_project_id_{PROJECTS}"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("pk", name=f"pk_{FLOORS}"),
    )
    op.create_index(
        f"uq_{FLOORS}_level",
        FLOORS,
        ["project_id", "level_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        f"ix_{FLOORS}_project_id_floor_order_pk",
        FLOORS,
        ["project_id", "floor_order", "pk"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(f"ix_{FLOORS}_level_id", FLOORS, ["level_id"], postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index(
        f"ix_{FLOORS}_deleted_at", FLOORS, ["deleted_at"], postgresql_where=sa.text("deleted_at IS NOT NULL")
    )


def downgrade() -> None:
    """Bỏ bảng `floors`; index đi theo `DROP TABLE`."""
    op.drop_table(FLOORS)
