"""project_separate_units

Revision ID: r20261028_ux_r2
Revises: r20261027_perf03_lookup_ix
Create Date: 2026-10-28

UX-R2 K34, expand thuần (BE-00 §6.1): `project_settings.separate_units` — các tầng của dự án là
những căn hộ riêng, không phải các tầng chồng lên nhau của một toà nhà. Cột NOT NULL kèm
`server_default false`: dòng cũ đọc ra `false` ngay, Postgres không viết lại bảng.
"""

from collections.abc import Sequence
from typing import Final

import sqlalchemy as sa
from alembic import op

revision: str = "r20261028_ux_r2"
down_revision: str | None = "r20261027_perf03_lookup_ix"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE: Final = "project_settings"


def upgrade() -> None:
    """Thêm cột boolean mặc định `false`."""
    op.add_column(TABLE, sa.Column("separate_units", sa.Boolean(), server_default=sa.text("false"), nullable=False))


def downgrade() -> None:
    """Bỏ cột (mất lựa chọn "căn riêng", cài đặt khác giữ nguyên)."""
    op.drop_column(TABLE, "separate_units")
