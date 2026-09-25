"""project_settings

Revision ID: r20260925_b2_02
Revises: r20260923_b2_03
Create Date: 2026-09-25 04:25:03.543832+00:00

Một bảng mới `project_settings` (B2-02 [5], BE-00 §6.1): expand thuần, không đụng bảng nào đang
có. Hằng số chép tay từ `packages/db/models/project_settings.py`, không nhập module model
(BE-00 §6.1: migration phải tự đứng vững kể cả khi model sau này đổi).

FK `project_id → projects.id` là `ON DELETE CASCADE` (như `r20260923_b2_03_floors.py`): lịch dọn
xoá cứng dự án bằng một lệnh `DELETE FROM projects`. Khoá chính `project_id` đã là index tra cứu
duy nhất của N5/N6, nên không cần index thêm.

Luật expand/contract: BE-00 §6.1 (`tools/lint_migrations.py` chặn drop/rename/NOT NULL).
"""

from collections.abc import Sequence
from typing import Final

import sqlalchemy as sa
from alembic import op

revision: str = "r20260925_b2_02"
down_revision: str | None = "r20260923_b2_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PROJECT_SETTINGS: Final = "project_settings"
PROJECTS: Final = "projects"


def upgrade() -> None:
    """Expand: một bảng mới `project_settings` cùng các CHECK phòng thủ (BE-00 §6.1)."""
    op.create_table(
        PROJECT_SETTINGS,
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("revision", sa.BigInteger(), nullable=False),
        sa.Column("building_type", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("length_unit", sa.Text(), nullable=False),
        sa.Column("snap_tolerance_mm", sa.Integer(), nullable=False),
        sa.Column("confidence_threshold", sa.Numeric(4, 3), nullable=False),
        sa.Column("default_scale_mm_per_px", sa.Numeric(12, 6), nullable=False),
        sa.Column("last_writer_id", sa.Text(), nullable=False),
        sa.Column("last_body_sha256", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("revision >= 1", name=op.f(f"ck_{PROJECT_SETTINGS}_revision_min")),
        sa.CheckConstraint(
            "building_type IN ('residential', 'commercial', 'industrial', 'mixed', 'other')",
            name=op.f(f"ck_{PROJECT_SETTINGS}_building_type_values"),
        ),
        sa.CheckConstraint(
            "notes IS NULL OR char_length(notes) BETWEEN 1 AND 500", name=op.f(f"ck_{PROJECT_SETTINGS}_notes_length")
        ),
        sa.CheckConstraint("length_unit IN ('mm', 'm')", name=op.f(f"ck_{PROJECT_SETTINGS}_length_unit_values")),
        sa.CheckConstraint(
            "snap_tolerance_mm BETWEEN 1 AND 120", name=op.f(f"ck_{PROJECT_SETTINGS}_snap_tolerance_mm_range")
        ),
        sa.CheckConstraint(
            "confidence_threshold BETWEEN 0 AND 1", name=op.f(f"ck_{PROJECT_SETTINGS}_confidence_threshold_range")
        ),
        sa.CheckConstraint(
            "default_scale_mm_per_px BETWEEN 0.01 AND 1000",
            name=op.f(f"ck_{PROJECT_SETTINGS}_default_scale_mm_per_px_range"),
        ),
        sa.CheckConstraint(
            "char_length(last_body_sha256) = 64", name=op.f(f"ck_{PROJECT_SETTINGS}_last_body_sha256_length")
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            [f"{PROJECTS}.id"],
            name=op.f(f"fk_{PROJECT_SETTINGS}_project_id_{PROJECTS}"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("project_id", name=f"pk_{PROJECT_SETTINGS}"),
    )


def downgrade() -> None:
    """Bỏ bảng `project_settings`."""
    op.drop_table(PROJECT_SETTINGS)
