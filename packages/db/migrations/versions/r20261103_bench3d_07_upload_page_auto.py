"""upload_page_auto

Revision ID: r20261103_bench3d_07
Revises: r20261102_aid_01
Create Date: 2026-11-03

BENCH3D-07, expand thuần (BE-00 §6.1): `uploads.page_auto` — #5 ghi `true` khi client **vắng** `pageIndex`
(`model_fields_set`), để #7 biết được tự chọn trang bản vẽ của PDF (bỏ trang bìa) mà không ghi đè trang người
dùng đã chọn. Cột nullable, không default, không backfill: NULL (lượt cũ) = coi như đã chọn trang, không tự đổi.
"""

from collections.abc import Sequence
from typing import Final

import sqlalchemy as sa
from alembic import op

revision: str = "r20261103_bench3d_07"
down_revision: str | None = "r20261102_aid_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE: Final = "uploads"
COLUMN: Final = "page_auto"


def upgrade() -> None:
    """Thêm cột `BOOLEAN NULL` (chỉ sửa catalog, không viết lại bảng)."""
    op.add_column(TABLE, sa.Column(COLUMN, sa.Boolean(), nullable=True))


def downgrade() -> None:
    """Bỏ cột (lượt tải đang dở mất cờ; #7 giữ đúng trang trong `page_index`)."""
    op.drop_column(TABLE, COLUMN)
