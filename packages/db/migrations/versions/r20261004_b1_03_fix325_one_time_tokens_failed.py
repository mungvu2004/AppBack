"""one_time_tokens_failed

Revision ID: r20261004_b1_03_fix325
Revises: r20261004_b6_02_fix273
Create Date: 2026-10-04

NO-150 (FIX-325), expand thuần (BE-00 §6.1): `sent_at` từng mang hai nghĩa — đã gửi, hoặc bị
SMTP từ chối vĩnh viễn (`MAIL_REJECTED`). Thêm `failed_at` + `failure_code` (cùng NULL hoặc
cùng có giá trị) để tách hai nghĩa; quét bù lọc thêm `failed_at IS NULL`. Không backfill: cột
mới mặc định NULL, và dòng cũ đã `MAIL_REJECTED` không phân biệt được với dòng gửi thật nên để
nguyên (vẫn ngoài tập quét vì `sent_at` có giá trị). Index partial `sent_at IS NULL` giữ nguyên.
"""

from collections.abc import Sequence
from typing import Final

import sqlalchemy as sa
from alembic import op

revision: str = "r20261004_b1_03_fix325"
down_revision: str | None = "r20261004_b6_02_fix273"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE: Final = "one_time_tokens"
CHECK_NAME: Final = "ck_one_time_tokens_failed_pair"


def upgrade() -> None:
    """Thêm hai cột nullable rồi CHECK cặp (bảng đang có dòng cũ đều NULL nên CHECK đúng ngay)."""
    op.add_column(TABLE, sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(TABLE, sa.Column("failure_code", sa.Text(), nullable=True))
    op.create_check_constraint(op.f(CHECK_NAME), TABLE, "(failed_at IS NULL) = (failure_code IS NULL)")


def downgrade() -> None:
    """Bỏ CHECK rồi hai cột (mất dấu vết lỗi vĩnh viễn, dòng vẫn nguyên)."""
    op.drop_constraint(op.f(CHECK_NAME), TABLE, type_="check")
    op.drop_column(TABLE, "failure_code")
    op.drop_column(TABLE, "failed_at")
