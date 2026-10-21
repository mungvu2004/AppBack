"""project_scene_style

Revision ID: r20261020_fe3db2
Revises: r20261004_b1_03_fix325
Create Date: 2026-10-20

FE3D-B2, expand thuần (BE-00 §6.1): `project_settings.scene_style` — phong cách cảnh 3D của dự án
(người cộng tác thấy cùng một kiểu nhà). Cột nullable, không backfill: dòng cũ NULL = FE dùng mặc
định của nó. CHECK giới hạn 5 id, chép cứng ở đây (migration không nhập model).
"""

from collections.abc import Sequence
from typing import Final

import sqlalchemy as sa
from alembic import op

revision: str = "r20261020_fe3db2"
down_revision: str | None = "r20261004_b1_03_fix325"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE: Final = "project_settings"
CHECK_NAME: Final = "ck_project_settings_scene_style_values"
SCENE_STYLES: Final = ("am-ap", "hien-dai-sang", "go-am", "toi-gian", "sang-trong-toi")


def upgrade() -> None:
    """Thêm cột nullable rồi CHECK (dòng cũ đều NULL nên CHECK đúng ngay)."""
    op.add_column(TABLE, sa.Column("scene_style", sa.Text(), nullable=True))
    allowed = ", ".join(f"'{style}'" for style in SCENE_STYLES)
    op.create_check_constraint(op.f(CHECK_NAME), TABLE, f"scene_style IS NULL OR scene_style IN ({allowed})")


def downgrade() -> None:
    """Bỏ CHECK rồi cột (mất phong cách đã chọn, cài đặt khác giữ nguyên)."""
    op.drop_constraint(op.f(CHECK_NAME), TABLE, type_="check")
    op.drop_column(TABLE, "scene_style")
