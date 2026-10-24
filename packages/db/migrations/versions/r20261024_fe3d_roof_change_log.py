"""floor_change_log_entity_type_roof

Revision ID: r20261024_fe3d_roof
Revises: r20261021_fe3db4
Create Date: 2026-10-24
# contract: CHECK entity_type phải thay (drop + create) để nhận thêm 'roof'

Mái Pascal (roof-contract.md) lưu trong JSONB `floor_documents.document` nên không cần cột mới,
nhưng nhật ký ghi mỗi thay đổi mái là một dòng `entity_type = 'roof'`. CHECK cũ chỉ nhận bảy
loại; Postgres không sửa được biểu thức CHECK tại chỗ nên phải bỏ rồi dựng lại với tập mới
(tập rộng hơn: mọi dòng cũ vẫn đạt, không quét dữ liệu nào bị từ chối).
"""

from collections.abc import Sequence
from typing import Final

from alembic import op

revision: str = "r20261024_fe3d_roof"
down_revision: str | None = "r20261021_fe3db4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE: Final = "floor_change_log"
CHECK_NAME: Final = "ck_floor_change_log_entity_type"
_OLD: Final = "entity_type IN ('vertex', 'wall', 'door', 'window', 'furniture', 'room', 'dimension')"
_NEW: Final = "entity_type IN ('vertex', 'wall', 'door', 'window', 'furniture', 'room', 'dimension', 'roof')"


def upgrade() -> None:
    """Thay CHECK `entity_type` bằng bản có thêm `'roof'`."""
    op.drop_constraint(op.f(CHECK_NAME), TABLE, type_="check")
    op.create_check_constraint(op.f(CHECK_NAME), TABLE, _NEW)


def downgrade() -> None:
    """Xoá dòng nhật ký mái (mất lịch sử mái; mái trong tài liệu giữ nguyên) rồi dựng lại CHECK cũ."""
    op.execute("DELETE FROM floor_change_log WHERE entity_type = 'roof'")
    op.drop_constraint(op.f(CHECK_NAME), TABLE, type_="check")
    op.create_check_constraint(op.f(CHECK_NAME), TABLE, _OLD)
