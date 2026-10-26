"""quality_summary

Revision ID: r20261026_b5_06a_p0_08
Revises: r20261025_share_links
Create Date: 2026-10-26

FIX-P0-08 (B5-06a), expand thuần (BE-00 §6.1): `pipeline_run_models.quality_summary` — tóm tắt
bước quality (`hasCritical`, `criticalCount`, `lowConfidence`) để N16 tính `readiness` khi
`quality.json` ở MinIO đã bị dọn. Cột nullable, không default, không backfill: lượt cũ NULL =
không có lý do `criticalIssues`.
"""

from collections.abc import Sequence
from typing import Final

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "r20261026_b5_06a_p0_08"
down_revision: str | None = "r20261025_share_links"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE: Final = "pipeline_run_models"
COLUMN: Final = "quality_summary"


def upgrade() -> None:
    """Thêm cột JSONB nullable (dòng cũ đều NULL)."""
    op.add_column(TABLE, sa.Column(COLUMN, postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    """Bỏ cột (mất tóm tắt quality đã ghi; readiness coi mọi lượt như chưa có tóm tắt)."""
    op.drop_column(TABLE, COLUMN)
