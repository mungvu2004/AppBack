"""projects

Revision ID: r20260923_b2_01
Revises: r20260922_b1_02
Create Date: 2026-09-23

Ba bảng nền của dự án (B2-01 [5], BE-00 §6.1): expand thuần, không đụng bảng nào
đang có. Tên CHECK bọc `op.f(...)` như `r20260922_b1_02_activity.py` để quy ước
`ck_%(table_name)s_%(constraint_name)s` không ghép tiền tố lần hai. Hằng số chép
tay từ `packages/db/models/projects.py`, không nhập module model: migration phải
tự đứng vững kể cả khi model sau này đổi (BE-00 §6.1).

Mọi FK tới `projects.id` là `ON DELETE CASCADE`: lịch dọn xoá cứng dự án bằng một
lệnh `DELETE FROM projects`, không phải ba lệnh theo thứ tự.
"""

from collections.abc import Sequence
from typing import Any, Final

import sqlalchemy as sa
from alembic import op

revision: str = "r20260923_b2_01"
down_revision: str | None = "r20260922_b1_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROJECTS: Final = "projects"
MEMBERSHIPS: Final = "project_memberships"
FLOOR_SUMMARIES: Final = "project_floor_summaries"
PIPELINE_STATES: Final = ("none", "pending", "running", "failed", "completed")


def _timestamps() -> list[sa.Column[Any]]:
    """`created_at`, `updated_at` đúng như `TimestampMixin`."""
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def _project_fk(table: str) -> sa.ForeignKeyConstraint:
    """FK `project_id → projects.id` có CASCADE; tên theo quy ước `fk_%(table)s_%(cols)s_%(referred)s`."""
    return sa.ForeignKeyConstraint(
        ["project_id"],
        [f"{PROJECTS}.id"],
        name=op.f(f"fk_{table}_project_id_{PROJECTS}"),
        ondelete="CASCADE",
    )


def upgrade() -> None:
    """Expand: ba bảng mới và một index, không đụng bảng nào đang có (BE-00 §6.1)."""
    op.create_table(
        PROJECTS,
        *_timestamps(),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("code", sa.Text(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=f"pk_{PROJECTS}"),
    )
    op.create_table(
        MEMBERSHIPS,
        *_timestamps(),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("added_by", sa.Text(), nullable=False),
        _project_fk(MEMBERSHIPS),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f(f"fk_{MEMBERSHIPS}_user_id_users")),
        sa.PrimaryKeyConstraint("project_id", "user_id", name=f"pk_{MEMBERSHIPS}"),
    )
    op.create_index(f"ix_{MEMBERSHIPS}_user_id", MEMBERSHIPS, ["user_id"])
    quoted = ", ".join(f"'{state}'" for state in PIPELINE_STATES)
    op.create_table(
        FLOOR_SUMMARIES,
        *_timestamps(),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("floor_level_id", sa.Text(), nullable=False),
        sa.Column("floor_order", sa.Integer(), nullable=False),
        sa.Column("walls_total", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("walls_reviewed", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("area_m2", sa.Numeric(12, 2), nullable=True),
        sa.Column("has_upload", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("pipeline_state", sa.Text(), server_default=sa.text("'none'"), nullable=False),
        sa.Column("hidden", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.CheckConstraint(
            "walls_reviewed >= 0 AND walls_reviewed <= walls_total",
            name=op.f(f"ck_{FLOOR_SUMMARIES}_walls_reviewed_range"),
        ),
        sa.CheckConstraint(
            f"pipeline_state IN ({quoted})",
            name=op.f(f"ck_{FLOOR_SUMMARIES}_pipeline_state"),
        ),
        _project_fk(FLOOR_SUMMARIES),
        sa.PrimaryKeyConstraint("project_id", "floor_level_id", name=f"pk_{FLOOR_SUMMARIES}"),
    )


def downgrade() -> None:
    """Bỏ ba bảng theo thứ tự ngược; mọi dự án, thành viên và số đếm mất theo."""
    op.drop_table(FLOOR_SUMMARIES)
    op.drop_index(f"ix_{MEMBERSHIPS}_user_id", table_name=MEMBERSHIPS)
    op.drop_table(MEMBERSHIPS)
    op.drop_table(PROJECTS)
