"""lighting_bakes

Revision ID: r20261102_lb_01
Revises: r20261030_ux41_member_role
Create Date: 2026-11-02

Expand thuần (BE-00 §6.1): bảng mới `lighting_bakes` cho LB-01 (N42-N44, bake ánh sáng GLB).
Không đụng bảng cũ nên không mang `# contract:`.
"""

from collections.abc import Sequence
from typing import Final

import sqlalchemy as sa
from alembic import op

revision: str = "r20261102_lb_01"
down_revision: str | None = "r20261030_ux41_member_role"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE: Final = "lighting_bakes"


def upgrade() -> None:
    """Tạo bảng `lighting_bakes` + chỉ mục theo dự án + chặn hai lượt đang chạy cùng dự án."""
    op.create_table(
        TABLE,
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("project_id", sa.Text(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("failure_code", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'done', 'failed')", name=op.f("ck_lighting_bakes_status_values")
        ),
    )
    op.create_index(op.f("ix_lighting_bakes_project_id_id"), TABLE, ["project_id", "id"])
    op.create_index(
        op.f("uq_lighting_bakes_active"),
        TABLE,
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )


def downgrade() -> None:
    """Bỏ bảng (mất mọi lượt bake; tệp trong kho object thành rác của dự án)."""
    op.drop_table(TABLE)
