"""activity

Revision ID: r20260922_b1_02
Revises: r20260921_b0_06_fix037
Create Date: 2026-09-22

Bảng `activity_log` (B1-02, BE-00 §6.1): expand thuần, không đụng bảng nào đang
có. Tên CHECK bọc `op.f(...)` như `r20260921_b1_01_auth.py` để quy ước
`ck_%(table_name)s_%(constraint_name)s` không ghép tiền tố lần hai. Hằng số
chép tay từ `packages/db/models/access.py`, không nhập module model: migration
phải tự đứng vững kể cả khi model sau này đổi (BE-00 §6.1).
"""

from collections.abc import Sequence
from typing import Any, Final

import sqlalchemy as sa
from alembic import op

revision: str = "r20260922_b1_02"
down_revision: str | None = "r20260921_b0_06_fix037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE: Final = "activity_log"
KIND_PATTERN: Final = r"^[a-z]+\.[a-z_]+$"
OBJECT_CODE_MAX: Final = 120
OBJECT_LABEL_MAX: Final = 200


def _timestamps() -> list[sa.Column[Any]]:
    """`created_at`, `updated_at` đúng như `TimestampMixin`."""
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    """Expand: một bảng mới, hai index, không đụng bảng nào đang có (BE-00 §6.1)."""
    op.create_table(
        TABLE,
        *_timestamps(),
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("object_code", sa.Text(), nullable=False),
        sa.Column("object_label", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(f"kind ~ '{KIND_PATTERN}'", name=op.f(f"ck_{TABLE}_kind_format")),
        sa.CheckConstraint(
            f"char_length(object_code) BETWEEN 1 AND {OBJECT_CODE_MAX}",
            name=op.f(f"ck_{TABLE}_object_code_length"),
        ),
        sa.CheckConstraint(
            f"char_length(object_label) BETWEEN 1 AND {OBJECT_LABEL_MAX}",
            name=op.f(f"ck_{TABLE}_object_label_length"),
        ),
        sa.PrimaryKeyConstraint("id", name=f"pk_{TABLE}"),
    )
    op.create_index(f"ix_{TABLE}_actor_id_at_id", TABLE, ["actor_id", sa.text("at DESC"), sa.text("id DESC")])
    op.create_index(f"ix_{TABLE}_at", TABLE, ["at"])


def downgrade() -> None:
    """Bỏ bảng; mọi nhật ký hoạt động mất theo — chỉ dùng trước khi có dữ liệu thật."""
    op.drop_index(f"ix_{TABLE}_at", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_actor_id_at_id", table_name=TABLE)
    op.drop_table(TABLE)
