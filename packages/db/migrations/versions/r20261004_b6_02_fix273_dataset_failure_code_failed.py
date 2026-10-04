"""dataset_versions_failure_code_failed

Revision ID: r20261004_b6_02_fix273
Revises: r20261001_b6_03a
Create Date: 2026-10-04

NO-275 (FIX-273), expand thuần (BE-00 §6.1): CHECK `failure_code` của `dataset_versions` chỉ
chặn một chiều (có mã thì phải `failed`); thêm chiều ngược — `failed` phải có mã — bằng một
CHECK **mới** `failure_code_failed`, cùng khuôn `training_jobs` (B6-03a). CHECK cũ giữ nguyên
(nó còn lo định dạng mã); drop/rename bị `lint_migrations` cấm trong expand.
"""

from collections.abc import Sequence
from typing import Final

from alembic import op

revision: str = "r20261004_b6_02_fix273"
down_revision: str | None = "r20261001_b6_03a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DATASET_VERSIONS: Final = "dataset_versions"
CHECK_NAME: Final = "ck_dataset_versions_failure_code_failed"


def upgrade() -> None:
    """Gán mã cho dòng `failed` còn thiếu (nếu có) rồi thêm CHECK hai chiều."""
    op.execute(
        "UPDATE dataset_versions SET failure_code = 'UNKNOWN_FAILURE' WHERE status = 'failed' AND failure_code IS NULL"
    )
    op.create_check_constraint(op.f(CHECK_NAME), DATASET_VERSIONS, "(failure_code IS NOT NULL) = (status = 'failed')")


def downgrade() -> None:
    """Bỏ CHECK mới; dòng đã backfill giữ nguyên mã."""
    op.drop_constraint(op.f(CHECK_NAME), DATASET_VERSIONS, type_="check")
