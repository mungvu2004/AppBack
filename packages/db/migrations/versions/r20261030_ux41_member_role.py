"""ux41_member_role

Revision ID: r20261030_ux41_member_role
Revises: r20261030_ux41_upload_sha256
Create Date: 2026-10-30

U24, expand thuần (BE-00 §6.1): `project_memberships.role` — vai của người này trong **một** dự án
(`engineer` = sửa, `viewer` = xem). Cột cho phép NULL, không `server_default`: dòng cũ và mã cũ
không ghi cột đều là NULL = theo vai hệ thống, đúng hành vi trước đây, không backfill.
"""

from collections.abc import Sequence
from typing import Final

import sqlalchemy as sa
from alembic import op

revision: str = "r20261030_ux41_member_role"
down_revision: str | None = "r20261030_ux41_upload_sha256"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE: Final = "project_memberships"
COLUMN: Final = "role"
CHECK_NAME: Final = "ck_project_memberships_role"


def upgrade() -> None:
    """Thêm cột NULL được (dòng cũ = theo vai hệ thống) và CHECK hai vai."""
    op.add_column(TABLE, sa.Column(COLUMN, sa.Text(), nullable=True))
    op.create_check_constraint(op.f(CHECK_NAME), TABLE, f"{COLUMN} IN ('engineer', 'viewer')")


def downgrade() -> None:
    """Bỏ CHECK rồi bỏ cột (mọi thành viên quay về vai hệ thống; dữ liệu khác giữ nguyên)."""
    op.drop_constraint(op.f(CHECK_NAME), TABLE, type_="check")
    op.drop_column(TABLE, COLUMN)
