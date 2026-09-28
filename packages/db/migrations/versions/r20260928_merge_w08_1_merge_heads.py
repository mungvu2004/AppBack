"""merge heads

Revision ID: r20260928_merge_w08_1
Revises: r20260928_b2_07, r20260928_b3_04
Create Date: 2026-09-28

Revision merge không thao tác: B2-07 và B3-04 cùng tách từ `r20260928_b2_06` nên `main`
có hai head sau khi gộp B2-07. Viết tay vì `run.sh merge-heads` hỏng ở template
(`script.py.mako` in `down_revision` nhiều head thành một chuỗi — NO-249).

Luật expand/contract: BE-00 §6.1 (`tools/lint_migrations.py` chặn drop/rename/NOT NULL).
"""

from collections.abc import Sequence

revision: str = "r20260928_merge_w08_1"
down_revision: str | Sequence[str] | None = ("r20260928_b2_07", "r20260928_b3_04")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Không thao tác: chỉ nối hai head về một."""


def downgrade() -> None:
    """Không thao tác: tách lại hai head."""
