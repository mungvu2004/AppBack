# contract: nới CHECK library_items.item_group thêm decor
"""lib_decor_group

Revision ID: r20261102_lib_decor_group
Revises: r20261102_mf_01
Create Date: 2026-11-02

Thư viện thêm nhóm `decor` (cây, thảm, đèn, rèm…) cho các mẫu nạp từ tệp `.glb`. Postgres không sửa được biểu
thức CHECK tại chỗ nên bỏ rồi dựng lại với tập rộng hơn (mọi dòng cũ vẫn đạt). Hằng số chép tay từ
`packages/db/models/library.py`, không nhập module model.
"""

from collections.abc import Sequence
from typing import Final

from alembic import op

revision: str = "r20261102_lib_decor_group"
down_revision: str | None = "r20261102_mf_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE: Final = "library_items"
CHECK_NAME: Final = "ck_library_items_item_group"
_OLD: Final = "item_group IN ('table', 'chair', 'bed', 'sofa', 'storage', 'sanitary', 'kitchen', 'technical')"
_NEW: Final = "item_group IN ('table', 'chair', 'bed', 'sofa', 'storage', 'sanitary', 'kitchen', 'technical', 'decor')"


def upgrade() -> None:
    """Thay CHECK `item_group` bằng bản có thêm `'decor'`."""
    op.drop_constraint(op.f(CHECK_NAME), TABLE, type_="check")
    op.create_check_constraint(op.f(CHECK_NAME), TABLE, _NEW)


def downgrade() -> None:
    """Xoá mục nhóm `decor` (seed lần sau tạo lại khi nâng cấp) rồi dựng lại CHECK tám nhóm."""
    op.execute("DELETE FROM library_items WHERE item_group = 'decor'")
    op.drop_constraint(op.f(CHECK_NAME), TABLE, type_="check")
    op.create_check_constraint(op.f(CHECK_NAME), TABLE, _OLD)
