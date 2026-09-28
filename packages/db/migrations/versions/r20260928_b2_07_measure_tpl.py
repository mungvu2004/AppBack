"""measure_tpl

Revision ID: r20260928_b2_07
Revises: r20260928_b2_06
Create Date: 2026-09-28

Bảng `measurements` và `property_templates` (B2-07 [5], BE-00 §6.1): expand thuần, hai bảng
mới, mỗi bảng một FK CASCADE sang `projects`. Hằng số chép tay từ `packages/db/models/`,
không nhập module model. Tên constraint bọc `op.f(...)` để quy ước của `Base.metadata`
không ghép tiền tố lần hai.

Luật expand/contract: BE-00 §6.1 (`tools/lint_migrations.py` chặn drop/rename/NOT NULL).
"""

from collections.abc import Sequence
from typing import Any, Final

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "r20260928_b2_07"
down_revision: str | None = "r20260928_b2_06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MEASUREMENTS: Final = "measurements"
PROPERTY_TEMPLATES: Final = "property_templates"
PROJECTS: Final = "projects"


def _timestamps() -> list[sa.Column[Any]]:
    """Hai cột `created_at`/`updated_at` của `TimestampMixin`."""
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    """Expand: hai bảng mới, không đụng bảng cũ."""
    op.create_table(
        MEASUREMENTS,
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("measurement_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("points", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("raw_value", sa.Float(), nullable=False),
        sa.Column("body_sha256", sa.CHAR(64), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "measurement_id ~ '^MS-[0-9]{4,15}$'", name=op.f(f"ck_{MEASUREMENTS}_measurement_id_format")
        ),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 120", name=op.f(f"ck_{MEASUREMENTS}_name_length")),
        sa.CheckConstraint(
            "mode IN ('pointToPoint', 'perpendicular', 'height', 'floorArea')", name=op.f(f"ck_{MEASUREMENTS}_mode")
        ),
        sa.CheckConstraint("raw_value >= 0", name=op.f(f"ck_{MEASUREMENTS}_raw_value_nonneg")),
        sa.ForeignKeyConstraint(
            ["project_id"],
            [f"{PROJECTS}.id"],
            name=op.f(f"fk_{MEASUREMENTS}_project_id_{PROJECTS}"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("project_id", "measurement_id", name=f"pk_{MEASUREMENTS}"),
    )
    op.create_table(
        PROPERTY_TEMPLATES,
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("object_kind", sa.Text(), nullable=False),
        sa.Column("fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 120", name=op.f(f"ck_{PROPERTY_TEMPLATES}_name_length")),
        sa.CheckConstraint(
            "object_kind IN ('wall', 'opening', 'room', 'furniture')",
            name=op.f(f"ck_{PROPERTY_TEMPLATES}_object_kind"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            [f"{PROJECTS}.id"],
            name=op.f(f"fk_{PROPERTY_TEMPLATES}_project_id_{PROJECTS}"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=f"pk_{PROPERTY_TEMPLATES}"),
    )
    op.create_index(
        f"ix_{PROPERTY_TEMPLATES}_project_id_created_at_id", PROPERTY_TEMPLATES, ["project_id", "created_at", "id"]
    )


def downgrade() -> None:
    """Bỏ hai bảng (kéo theo index); không bảng nào khác trỏ tới chúng."""
    op.drop_table(PROPERTY_TEMPLATES)
    op.drop_table(MEASUREMENTS)
