"""versions

Revision ID: r20260928_b3_04
Revises: r20260928_b2_06
Create Date: 2026-09-28

Bảng `versions` (B3-04 [5], BE-00 §6.1): expand thuần, một bảng mới với hai FK
`ON DELETE CASCADE`. Hằng số chép tay từ `packages/db/models/versions.py`, không nhập
module model. Tên constraint bọc `op.f(...)` để quy ước của `Base.metadata` không ghép
tiền tố lần hai.

Luật expand/contract: BE-00 §6.1 (`tools/lint_migrations.py` chặn drop/rename/NOT NULL).
"""

from collections.abc import Sequence
from typing import Final

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "r20260928_b3_04"
down_revision: str | None = "r20260928_b2_06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

VERSIONS: Final = "versions"
FLOORS: Final = "floors"
PROJECTS: Final = "projects"
CREATOR_RE: Final = "^(usr_[0-9A-HJKMNP-TV-Z]{26}|system:pipeline)$"


def upgrade() -> None:
    """Expand: bảng mới; mọi cột ngoài danh tính và siêu dữ liệu chụp đều NULL được."""
    op.create_table(
        VERSIONS,
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("floor_pk", sa.BigInteger(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("floor_revision", sa.BigInteger(), nullable=False),
        sa.Column("creator_id", sa.Text(), nullable=False),
        sa.Column("creator_name", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("snapshot", postgresql.JSONB(none_as_null=True), nullable=True),
        sa.Column("restored_from_id", sa.Text(), nullable=True),
        sa.Column("restore_base_revision", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("sequence > 0", name=op.f(f"ck_{VERSIONS}_sequence_positive")),
        sa.CheckConstraint("floor_revision >= 0", name=op.f(f"ck_{VERSIONS}_floor_revision_non_negative")),
        sa.CheckConstraint(f"creator_id ~ '{CREATOR_RE}'", name=op.f(f"ck_{VERSIONS}_creator_id_format")),
        sa.CheckConstraint("char_length(creator_name) > 0", name=op.f(f"ck_{VERSIONS}_creator_name_not_empty")),
        sa.CheckConstraint("note IS NULL OR char_length(note) >= 1", name=op.f(f"ck_{VERSIONS}_note_not_empty")),
        sa.CheckConstraint(
            "label IS NULL OR char_length(label) BETWEEN 1 AND 60", name=op.f(f"ck_{VERSIONS}_label_length")
        ),
        sa.ForeignKeyConstraint(
            ["floor_pk"], [f"{FLOORS}.pk"], name=op.f(f"fk_{VERSIONS}_floor_pk_{FLOORS}"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], [f"{PROJECTS}.id"], name=op.f(f"fk_{VERSIONS}_project_id_{PROJECTS}"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=f"pk_{VERSIONS}"),
        sa.UniqueConstraint("floor_pk", "sequence", name=op.f(f"uq_{VERSIONS}_floor_pk_sequence")),
    )


def downgrade() -> None:
    """Bỏ bảng (kéo theo unique); không bảng nào khác trỏ tới nó."""
    op.drop_table(VERSIONS)
