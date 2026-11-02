"""design_concepts

Revision ID: r20261102_aid_01
Revises: r20261028_ux_r2
Create Date: 2026-11-02

Expand thuần (BE-00 §6.1): bảng mới `design_concepts` cho AID-01 (N47-N48, AI chọn phong cách nội thất).
Không đụng bảng cũ nên không mang `# contract:`.
"""

from collections.abc import Sequence
from typing import Final

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "r20261102_aid_01"
down_revision: str | None = "r20261028_ux_r2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE: Final = "design_concepts"
STYLES: Final = (
    "japandi",
    "scandinavian",
    "modern-min",
    "modern-lux",
    "indochine",
    "wabi-sabi",
    "industrial",
    "tropical",
    "korean-min",
    "neoclassic",
    "midcentury",
    "rustic",
)


def upgrade() -> None:
    """Tạo bảng `design_concepts` + chỉ mục theo dự án + chặn hai lượt đang chạy cùng đầu vào."""
    op.create_table(
        TABLE,
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("project_id", sa.Text(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("style_id", sa.Text(), nullable=True),
        sa.Column("suggested", sa.Boolean(), nullable=False),
        sa.Column("input_key", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("failure_code", sa.Text(), nullable=True),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("usage", postgresql.JSONB(), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("selected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'done', 'failed')", name=op.f("ck_design_concepts_status_values")
        ),
        sa.CheckConstraint(
            "style_id IS NULL OR style_id IN (" + ", ".join(f"'{s}'" for s in STYLES) + ")",
            name=op.f("ck_design_concepts_style_values"),
        ),
    )
    op.create_index(op.f("ix_design_concepts_project_id_id"), TABLE, ["project_id", "id"])
    op.create_index(
        op.f("uq_design_concepts_active"),
        TABLE,
        ["project_id", "input_key"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )


def downgrade() -> None:
    """Bỏ bảng (mất mọi concept; FE quay về phong cách cũ)."""
    op.drop_table(TABLE)
