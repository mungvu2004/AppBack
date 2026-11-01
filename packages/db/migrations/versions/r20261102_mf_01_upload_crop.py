"""upload_crop_corners

Revision ID: r20261102_mf_01
Revises: r20261102_lb_01
Create Date: 2026-11-02

MULTI-FLOOR-01, expand thuần (BE-00 §6.1): `uploads.crop_corners` — vùng cắt của tầng trên một tờ
có nhiều mặt bằng, lưu 4 góc TL,TR,BR,BL theo tỉ lệ trang gốc (cùng dạng `quality_assessments.corners`).
Cột nullable, không default, không backfill: NULL = xử lý cả trang như trước.
"""

from collections.abc import Sequence
from typing import Final

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "r20261102_mf_01"
down_revision: str | None = "r20261102_lb_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE: Final = "uploads"
COLUMN: Final = "crop_corners"


def upgrade() -> None:
    """Thêm cột `JSONB NULL` (chỉ sửa catalog, không viết lại bảng)."""
    op.add_column(TABLE, sa.Column(COLUMN, JSONB(), nullable=True))


def downgrade() -> None:
    """Bỏ cột (mất vùng cắt; lượt chạy sau xử lý cả trang)."""
    op.drop_column(TABLE, COLUMN)
