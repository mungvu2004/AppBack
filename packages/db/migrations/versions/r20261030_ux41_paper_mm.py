"""drawing_px_per_paper_mm

Revision ID: r20261030_ux41_paper_mm
Revises: r20261027_perf03_lookup_ix
Create Date: 2026-10-30

UX41 U01, expand thuần (BE-00 §6.1): `drawings.px_per_paper_mm` — px trên mỗi mm giấy của trang
PDF vừa dựng (preprocess đã đo, trước đây chỉ gửi bước tường). Bước dựng đọc nó để đổi ghi chú
`TL 1:N` thành mm/px, N16 trả `sourceDpi`. Nullable, không backfill: dòng cũ và ảnh raster là `NULL`.
"""

from collections.abc import Sequence
from typing import Final

import sqlalchemy as sa
from alembic import op

revision: str = "r20261030_ux41_paper_mm"
down_revision: str | None = "r20261027_perf03_lookup_ix"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE: Final = "drawings"
COLUMN: Final = "px_per_paper_mm"


def upgrade() -> None:
    """Thêm cột nullable (dòng cũ nhận `NULL` ngay, không khoá bảng lâu)."""
    op.add_column(TABLE, sa.Column(COLUMN, sa.Float(), nullable=True))


def downgrade() -> None:
    """Bỏ cột (mất tỉ số px/mm giấy; lượt chạy sau lại đo, dữ liệu khác giữ nguyên)."""
    op.drop_column(TABLE, COLUMN)
