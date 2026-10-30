"""upload_content_sha256

Revision ID: r20261030_ux41_upload_sha256
Revises: r20261030_ux41_paper_mm
Create Date: 2026-10-30

UX41 P01, expand thuần (BE-00 §6.1): `uploads.content_sha256` — SHA-256 hex của cả tệp gốc, ghi lúc
#7 `complete`. FE so nó với tệp vừa chọn để báo "giống hệt bản vẽ đang dùng". Cột nullable, không
default, không backfill: lượt tải cũ NULL = không biết, FE không báo trùng.
"""

from collections.abc import Sequence
from typing import Final

import sqlalchemy as sa
from alembic import op

revision: str = "r20261030_ux41_upload_sha256"
down_revision: str | None = "r20261030_ux41_paper_mm"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE: Final = "uploads"
COLUMN: Final = "content_sha256"


def upgrade() -> None:
    """Thêm cột `TEXT NULL` (chỉ sửa catalog, không viết lại bảng)."""
    op.add_column(TABLE, sa.Column(COLUMN, sa.Text(), nullable=True))


def downgrade() -> None:
    """Bỏ cột (mất dấu băm; FE thôi báo tệp trùng, dữ liệu khác giữ nguyên)."""
    op.drop_column(TABLE, COLUMN)
