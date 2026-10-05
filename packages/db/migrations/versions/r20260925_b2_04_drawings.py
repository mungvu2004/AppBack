"""drawings

Revision ID: r20260925_b2_04
Revises: r20260925_b2_02
Create Date: 2026-09-25

Bốn bảng mới của lượt tải bản vẽ (B2-04 [5], BE-00 §6.1): expand thuần, không đụng bảng
nào đang có. Hằng số chép tay từ `packages/db/models/drawings.py`, không nhập module model
(BE-00 §6.1: migration phải tự đứng vững kể cả khi model sau này đổi) — kể cả 6 id bước,
vốn suy từ `PIPELINE_STEPS` ở phía model.

Mọi FK tới `projects.id`, `floors.pk`, `uploads.id` là `ON DELETE CASCADE` (như
`r20260923_b2_03_floors.py`): lịch dọn xoá cứng dự án/tầng bằng một lệnh `DELETE`.

Luật expand/contract: BE-00 §6.1 (`tools/lint_migrations.py` chặn drop/rename/NOT NULL).
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Final

import sqlalchemy as sa
from alembic import op

revision: str = "r20260925_b2_04"
down_revision: str | None = "r20260925_b2_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UPLOADS: Final = "uploads"
UPLOAD_CHUNKS: Final = "upload_chunks"
PIPELINE_RUNS: Final = "pipeline_runs"
DRAWINGS: Final = "drawings"
PROJECTS: Final = "projects"
FLOORS: Final = "floors"

_UPLOAD_STATUS: Final = "status IN ('receiving', 'complete', 'rejected')"
_RUN_STATUS: Final = "status IN ('pending', 'running', 'completed', 'failed')"
_RUN_STEP: Final = (
    "current_step IN ('preprocess', 'wallSegmentation', 'openingAndFurnitureDetection', "
    "'dimensionReading', 'spatialDataBuild', 'qualityCheck')"
)


def _timestamps() -> tuple[sa.Column[datetime], ...]:
    """Hai cột của `TimestampMixin` — bốn bảng dùng chung, khai một lần."""
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def _create_uploads() -> None:
    """`uploads` + index một phần phục vụ khử trùng init (#5)."""
    op.create_table(
        UPLOADS,
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("floor_pk", sa.BigInteger(), nullable=False),
        sa.Column("file_name", sa.Text(), nullable=False),
        sa.Column("declared_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("declared_type", sa.Text(), nullable=False),
        sa.Column("sniffed_kind", sa.Text(), nullable=True),
        sa.Column("page_index", sa.Integer(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("rejected_code", sa.Text(), nullable=True),
        sa.Column("original_key", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(_UPLOAD_STATUS, name=op.f(f"ck_{UPLOADS}_status")),
        sa.CheckConstraint("declared_size_bytes > 0", name=op.f(f"ck_{UPLOADS}_declared_size_bytes_positive")),
        sa.CheckConstraint("chunk_count > 0", name=op.f(f"ck_{UPLOADS}_chunk_count_positive")),
        sa.CheckConstraint("page_index >= 0", name=op.f(f"ck_{UPLOADS}_page_index_non_negative")),
        sa.ForeignKeyConstraint(
            ["project_id"], [f"{PROJECTS}.id"], name=op.f(f"fk_{UPLOADS}_project_id_{PROJECTS}"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["floor_pk"], [f"{FLOORS}.pk"], name=op.f(f"fk_{UPLOADS}_floor_pk_{FLOORS}"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=f"pk_{UPLOADS}"),
    )
    op.create_index(
        f"ix_{UPLOADS}_floor_pk_created_by_created_at",
        UPLOADS,
        ["floor_pk", "created_by", "created_at"],
        postgresql_where=sa.text("status = 'receiving'"),
    )


def _create_upload_chunks() -> None:
    """`upload_chunks`; PK ghép `(upload_id, chunk_index)` nên gửi lại khúc là ghi đè."""
    op.create_table(
        UPLOAD_CHUNKS,
        sa.Column("upload_id", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("chunk_index >= 0", name=op.f(f"ck_{UPLOAD_CHUNKS}_chunk_index_non_negative")),
        sa.CheckConstraint("size_bytes > 0", name=op.f(f"ck_{UPLOAD_CHUNKS}_size_bytes_positive")),
        sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name=op.f(f"ck_{UPLOAD_CHUNKS}_sha256_format")),
        sa.ForeignKeyConstraint(
            ["upload_id"],
            [f"{UPLOADS}.id"],
            name=op.f(f"fk_{UPLOAD_CHUNKS}_upload_id_{UPLOADS}"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("upload_id", "chunk_index", name=f"pk_{UPLOAD_CHUNKS}"),
    )


def _create_pipeline_runs() -> None:
    """`pipeline_runs` + index cho lịch quét bù `(status, updated_at)` và cho `start_run`/N7."""
    op.create_table(
        PIPELINE_RUNS,
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("upload_id", sa.Text(), nullable=False),
        sa.Column("floor_pk", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("current_step", sa.Text(), nullable=False),
        sa.Column("progress_percent", sa.Integer(), nullable=False),
        sa.Column("requeue_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_by", sa.Text(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(_RUN_STATUS, name=op.f(f"ck_{PIPELINE_RUNS}_status")),
        sa.CheckConstraint(_RUN_STEP, name=op.f(f"ck_{PIPELINE_RUNS}_current_step")),
        sa.CheckConstraint(
            "progress_percent BETWEEN 0 AND 100", name=op.f(f"ck_{PIPELINE_RUNS}_progress_percent_range")
        ),
        sa.CheckConstraint("requeue_count >= 0", name=op.f(f"ck_{PIPELINE_RUNS}_requeue_count_non_negative")),
        sa.ForeignKeyConstraint(
            ["upload_id"],
            [f"{UPLOADS}.id"],
            name=op.f(f"fk_{PIPELINE_RUNS}_upload_id_{UPLOADS}"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["floor_pk"], [f"{FLOORS}.pk"], name=op.f(f"fk_{PIPELINE_RUNS}_floor_pk_{FLOORS}"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=f"pk_{PIPELINE_RUNS}"),
    )
    op.create_index(f"ix_{PIPELINE_RUNS}_status_updated_at", PIPELINE_RUNS, ["status", "updated_at"])
    op.create_index(f"ix_{PIPELINE_RUNS}_floor_pk_created_at", PIPELINE_RUNS, ["floor_pk", "created_at"])


def _create_drawings() -> None:
    """`drawings`; `floor_pk` unique nên mỗi tầng nhiều nhất một bản vẽ đang dùng."""
    op.create_table(
        DRAWINGS,
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("floor_pk", sa.BigInteger(), nullable=False),
        sa.Column("upload_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("page_key", sa.Text(), nullable=False),
        sa.Column("width_px", sa.Integer(), nullable=False),
        sa.Column("height_px", sa.Integer(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("uploader_id", sa.Text(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("width_px > 0", name=op.f(f"ck_{DRAWINGS}_width_px_positive")),
        sa.CheckConstraint("height_px > 0", name=op.f(f"ck_{DRAWINGS}_height_px_positive")),
        sa.ForeignKeyConstraint(
            ["floor_pk"], [f"{FLOORS}.pk"], name=op.f(f"fk_{DRAWINGS}_floor_pk_{FLOORS}"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["upload_id"], [f"{UPLOADS}.id"], name=op.f(f"fk_{DRAWINGS}_upload_id_{UPLOADS}"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=f"pk_{DRAWINGS}"),
        sa.UniqueConstraint("floor_pk", name=op.f(f"uq_{DRAWINGS}_floor_pk")),
    )


def upgrade() -> None:
    """Expand: bốn bảng mới, theo thứ tự FK (`uploads` trước `upload_chunks`/lượt chạy/bản vẽ)."""
    _create_uploads()
    _create_upload_chunks()
    _create_pipeline_runs()
    _create_drawings()


def downgrade() -> None:
    """Bỏ bốn bảng theo thứ tự ngược; index đi theo `DROP TABLE`."""
    op.drop_table(DRAWINGS)
    op.drop_table(PIPELINE_RUNS)
    op.drop_table(UPLOAD_CHUNKS)
    op.drop_table(UPLOADS)
