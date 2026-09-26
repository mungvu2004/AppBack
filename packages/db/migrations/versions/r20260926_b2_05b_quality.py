"""quality

Revision ID: r20260926_b2_05b
Revises: r20260926_b3_02
Create Date: 2026-09-26

Bảng `quality_assessments` (B2-05b [5], BE-00 §6.1): expand thuần, không đụng bảng nào đang
có. Hằng số chép tay từ `packages/db/models/quality.py`, không nhập module model.

`floor_pk` là PK và FK `ON DELETE CASCADE` (như `floor_documents`): xoá cứng tầng là một
lệnh `DELETE`. `drawing_id` không FK — bản vẽ bị thay thì dòng đo thành cũ.

Luật expand/contract: BE-00 §6.1 (`tools/lint_migrations.py` chặn drop/rename/NOT NULL).
"""

from collections.abc import Sequence
from typing import Final

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "r20260926_b2_05b"
down_revision: str | None = "r20260926_b3_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

QUALITY_ASSESSMENTS: Final = "quality_assessments"
FLOORS: Final = "floors"


def upgrade() -> None:
    """Expand: một bảng mới, `corners` NULL được (chưa ai áp góc)."""
    op.create_table(
        QUALITY_ASSESSMENTS,
        sa.Column("floor_pk", sa.BigInteger(), nullable=False),
        sa.Column("drawing_id", sa.Text(), nullable=False),
        sa.Column("report", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("corners", postgresql.JSONB(astext_type=sa.Text(), none_as_null=True), nullable=True),
        sa.Column("homography", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["floor_pk"],
            [f"{FLOORS}.pk"],
            name=op.f(f"fk_{QUALITY_ASSESSMENTS}_floor_pk_{FLOORS}"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("floor_pk", name=f"pk_{QUALITY_ASSESSMENTS}"),
    )


def downgrade() -> None:
    """Bỏ bảng; không bảng nào khác trỏ tới nó."""
    op.drop_table(QUALITY_ASSESSMENTS)
