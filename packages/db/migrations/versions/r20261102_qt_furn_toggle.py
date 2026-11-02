"""project_detect_furniture

Revision ID: r20261102_qt_furn_toggle
Revises: r20261102_lib_decor_group
Create Date: 2026-11-02

QT-FURN-TOGGLE, expand thuần (BE-00 §6.1): `project_settings.detect_furniture` — dự án có dựng đồ
đạc AI vào lớp không gian hay không (cửa đi, cửa sổ vẫn dò). NOT NULL mặc định `false`: chủ dự án
tắt nhận diện đồ từ 02/11/2026, dòng cũ cũng tắt.
"""

from collections.abc import Sequence
from typing import Final

import sqlalchemy as sa
from alembic import op

revision: str = "r20261102_qt_furn_toggle"
down_revision: str | None = "r20261102_lib_decor_group"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE: Final = "project_settings"


def upgrade() -> None:
    """Thêm cột boolean có mặc định phía server (dòng cũ nhận `false` ngay)."""
    op.add_column(TABLE, sa.Column("detect_furniture", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    """Bỏ cột (mất lựa chọn bật đồ, cài đặt khác giữ nguyên)."""
    op.drop_column(TABLE, "detect_furniture")
