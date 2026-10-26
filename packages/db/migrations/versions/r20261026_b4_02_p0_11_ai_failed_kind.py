# contract: nới CHECK notifications.kind thêm aiFailed
"""notifications_kind_ai_failed

Revision ID: r20261026_b4_02_p0_11
Revises: r20261026_b5_06a_p0_08
Create Date: 2026-10-26

Lượt chạy hỏng báo người tải lên (FIX-P0-11/12) bằng loại thông báo mới `aiFailed`. CHECK `kind` cũ chỉ nhận ba
loại; Postgres không sửa được biểu thức CHECK tại chỗ nên phải bỏ rồi dựng lại với tập mới (tập rộng hơn: mọi dòng
cũ vẫn đạt). Hằng số chép tay từ `packages/db/models/notifications.py`, không nhập module model.
"""

from collections.abc import Sequence
from typing import Final

from alembic import op

revision: str = "r20261026_b4_02_p0_11"
down_revision: str | None = "r20261026_b5_06a_p0_08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE: Final = "notifications"
CHECK_NAME: Final = "ck_notifications_kind"
_OLD: Final = "kind IN ('aiCompleted', 'violationFound', 'projectInvite')"
_NEW: Final = "kind IN ('aiCompleted', 'violationFound', 'projectInvite', 'aiFailed')"


def upgrade() -> None:
    """Thay CHECK `kind` bằng bản có thêm `'aiFailed'`."""
    op.drop_constraint(op.f(CHECK_NAME), TABLE, type_="check")
    op.create_check_constraint(op.f(CHECK_NAME), TABLE, _NEW)


def downgrade() -> None:
    """Xoá thông báo `aiFailed` (mất các thông báo lượt hỏng đã gửi) rồi dựng lại CHECK ba loại."""
    op.execute("DELETE FROM notifications WHERE kind = 'aiFailed'")
    op.drop_constraint(op.f(CHECK_NAME), TABLE, type_="check")
    op.create_check_constraint(op.f(CHECK_NAME), TABLE, _OLD)
