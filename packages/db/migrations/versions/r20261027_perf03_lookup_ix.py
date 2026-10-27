"""perf03_lookup_ix

Revision ID: r20261027_perf03_lookup_ix
Revises: r20261026_b4_02_p0_11
Create Date: 2026-10-27

PERF-03 (P16), expand thuần: hai index tra "mới nhất trước" mà N7 (`drawings/latest.py`) và
`progress_wire` (`drawings/progress.py`) cần. Đo trên f14: 16.598 lượt seq scan `pipeline_runs`
theo `upload_id`; `uploads` theo `floor_pk` chỉ có index một phần `status = 'receiving'`.
Thứ tự cột khớp đúng `ORDER BY created_at DESC, id DESC` của hai truy vấn. Tạo `CONCURRENTLY`
trong `autocommit_block` để không khoá ghi hai bảng đang có dữ liệu.
"""

from collections.abc import Sequence
from typing import Final

import sqlalchemy as sa
from alembic import op

revision: str = "r20261027_perf03_lookup_ix"
down_revision: str | None = "r20261026_b4_02_p0_11"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RUNS_IX: Final = "ix_pipeline_runs_upload_id_created_at"
UPLOADS_IX: Final = "ix_uploads_floor_pk_created_at"
NEWEST_FIRST: Final = (sa.text("created_at DESC"), sa.text("id DESC"))


def upgrade() -> None:
    """Tạo hai index `(khoá tra, created_at DESC, id DESC)` không khoá bảng.

    Tên bảng viết hằng (không lặp qua biến) để `tools/lint_migrations.py` đọc được và kiểm `CONCURRENTLY`.
    """
    with op.get_context().autocommit_block():
        op.create_index(RUNS_IX, "pipeline_runs", ["upload_id", *NEWEST_FIRST], postgresql_concurrently=True)
        op.create_index(UPLOADS_IX, "uploads", ["floor_pk", *NEWEST_FIRST], postgresql_concurrently=True)


def downgrade() -> None:
    """Bỏ hai index (truy vấn quay về quét tuần tự, kết quả không đổi)."""
    with op.get_context().autocommit_block():
        op.drop_index(RUNS_IX, table_name="pipeline_runs", postgresql_concurrently=True)
        op.drop_index(UPLOADS_IX, table_name="uploads", postgresql_concurrently=True)
