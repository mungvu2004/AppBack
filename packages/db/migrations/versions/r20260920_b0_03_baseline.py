"""baseline

Revision ID: r20260920_b0_03
Revises:
Create Date: 2026-09-20

Gốc duy nhất của cây revision (BE-00 §6.1): rỗng, không tạo bảng nào. Bảng nghiệp vụ
thuộc revision của prompt chủ, `down_revision` trỏ về head hiện hành.
"""

from collections.abc import Sequence

revision: str = "r20260920_b0_03"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
