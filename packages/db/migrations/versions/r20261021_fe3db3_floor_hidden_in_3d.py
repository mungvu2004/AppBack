"""floor_hidden_in_3d

Revision ID: r20261021_fe3db3
Revises: r20261020_fe3db2
Create Date: 2026-10-21

FE3D-B3, expand thuần (BE-00 §6.1): `floors.hidden_in_3d` — tầng bị ẩn khỏi cảnh 3D (trình quản lý
tầng của FE). NOT NULL + `server_default false`: dòng cũ và mã cũ không ghi cột này đều nhận `false`,
không backfill.
"""

from collections.abc import Sequence
from typing import Final

import sqlalchemy as sa
from alembic import op

revision: str = "r20261021_fe3db3"
down_revision: str | None = "r20261020_fe3db2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE: Final = "floors"
COLUMN: Final = "hidden_in_3d"


def upgrade() -> None:
    """Thêm cột NOT NULL có `server_default false` (dòng cũ nhận `false` ngay)."""
    op.add_column(TABLE, sa.Column(COLUMN, sa.Boolean(), server_default=sa.text("false"), nullable=False))


def downgrade() -> None:
    """Bỏ cột (mất cờ ẩn 3D, tầng hiện lại trong cảnh; dữ liệu khác giữ nguyên)."""
    op.drop_column(TABLE, COLUMN)
