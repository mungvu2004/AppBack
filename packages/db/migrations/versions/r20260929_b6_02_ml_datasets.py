"""ml_datasets

Revision ID: r20260929_b6_02
Revises: r20260928_b6_01
Create Date: 2026-09-29

Hai bảng dataset huấn luyện (B6-02 [5], BE-00 §6.1): expand thuần, hai bảng mới và một FK
`dataset_versions.dataset_id → datasets.id`. Hằng số (tên bảng, tập giá trị) **chép tay** từ
`packages/db/models/admin_ml_datasets.py`, theo đúng khuôn `r20260928_b6_01_ml_registry.py`:
migration không nhập module model.

Luật expand/contract: BE-00 §6.1 (`tools/lint_migrations.py` chặn drop/rename/NOT NULL).
"""

from collections.abc import Sequence
from typing import Final

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "r20260929_b6_02"
down_revision: str | None = "r20260928_b6_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DATASETS: Final = "datasets"
DATASET_VERSIONS: Final = "dataset_versions"

FAMILY_VALUES: Final = ("wallSegmentation", "openingAndFurnitureDetection", "dimensionReading")
DATASET_STATUSES: Final = ("building", "ready", "failed")
DATASET_SOURCES: Final = ("approvedFloors", "cubicasa5k")
NAME_MAX: Final = 80
SHA256_LEN: Final = 64
SHA256_PATTERN: Final = "^[0-9a-f]{64}$"
FAILURE_CODE_PATTERN: Final = "^[A-Z][A-Z0-9_]{2,63}$"


def _in_values(column: str, values: tuple[str, ...]) -> str:
    """`CHECK` "cột thuộc tập giá trị" — cùng chuỗi với `one_of` của model (bước 6 so tên và thân)."""
    quoted = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({quoted})"


def _create_datasets() -> None:
    """Bảng `datasets`: tên bền, `name_key` unique không phân biệt hoa thường."""
    op.create_table(
        DATASETS,
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("name_key", sa.Text(), nullable=False),
        sa.Column("family", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(_in_values("family", FAMILY_VALUES), name=op.f(f"ck_{DATASETS}_family")),
        sa.CheckConstraint(f"char_length(name) BETWEEN 1 AND {NAME_MAX}", name=op.f(f"ck_{DATASETS}_name_length")),
        sa.PrimaryKeyConstraint("id", name=f"pk_{DATASETS}"),
        # `UniqueConstraint`, **không** `create_index(unique=True)`: model khai `name_key` bằng
        # `mapped_column(..., unique=True)`, mà SQLAlchemy dịch cờ đó thành một UNIQUE *constraint*.
        # Hai cách này tạo ra cùng một index ở Postgres nhưng **khác nhau** trong metadata, nên lệch
        # một bên là đủ để bước "model khớp DB" của `migrate_check` đỏ. `ON CONFLICT (name_key)` của
        # N29 vẫn chạy: UNIQUE constraint luôn có index đỡ phía dưới.
        sa.UniqueConstraint("name_key", name=op.f(f"uq_{DATASETS}_name_key")),
    )


def _create_dataset_versions() -> None:
    """Bảng `dataset_versions`; FK sang `datasets` nên phải tạo sau bảng kia."""
    op.create_table(
        DATASET_VERSIONS,
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("dataset_id", sa.Text(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("project_ids", JSONB(), nullable=True),
        sa.Column("manifest_sha256", sa.CHAR(SHA256_LEN), nullable=True),
        sa.Column("split_counts", JSONB(), nullable=True),
        sa.Column("failure_code", sa.Text(), nullable=True),
        sa.Column("build_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requeue_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(_in_values("status", DATASET_STATUSES), name=op.f(f"ck_{DATASET_VERSIONS}_status")),
        sa.CheckConstraint(_in_values("source", DATASET_SOURCES), name=op.f(f"ck_{DATASET_VERSIONS}_source")),
        sa.CheckConstraint("sequence > 0", name=op.f(f"ck_{DATASET_VERSIONS}_sequence_min")),
        sa.CheckConstraint("requeue_count >= 0", name=op.f(f"ck_{DATASET_VERSIONS}_requeue_count_min")),
        sa.CheckConstraint(
            "(manifest_sha256 IS NOT NULL) = (status = 'ready')", name=op.f(f"ck_{DATASET_VERSIONS}_manifest_ready")
        ),
        sa.CheckConstraint(
            f"manifest_sha256 IS NULL OR manifest_sha256 ~ '{SHA256_PATTERN}'",
            name=op.f(f"ck_{DATASET_VERSIONS}_manifest_format"),
        ),
        sa.CheckConstraint(
            "(split_counts IS NOT NULL) = (status = 'ready')",
            name=op.f(f"ck_{DATASET_VERSIONS}_split_counts_ready"),
        ),
        sa.CheckConstraint(
            "split_counts IS NULL OR split_counts ?& array['train', 'validation', 'test']",
            name=op.f(f"ck_{DATASET_VERSIONS}_split_counts_keys"),
        ),
        sa.CheckConstraint(
            "failure_code IS NULL OR (status = 'failed' AND failure_code ~ '" + FAILURE_CODE_PATTERN + "')",
            name=op.f(f"ck_{DATASET_VERSIONS}_failure_code"),
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id"], [f"{DATASETS}.id"], name=op.f(f"fk_{DATASET_VERSIONS}_dataset_id_{DATASETS}")
        ),
        sa.PrimaryKeyConstraint("id", name=f"pk_{DATASET_VERSIONS}"),
    )
    op.create_index(
        f"uq_{DATASET_VERSIONS}_dataset_id_sequence", DATASET_VERSIONS, ["dataset_id", "sequence"], unique=True
    )
    op.create_index(
        f"uq_{DATASET_VERSIONS}_dataset_id_building",
        DATASET_VERSIONS,
        ["dataset_id"],
        unique=True,
        postgresql_where=sa.text("status = 'building'"),
    )


def upgrade() -> None:
    """Expand: hai bảng, một UNIQUE constraint, hai unique index (một partial) — BE-00 §6.1."""
    _create_datasets()
    _create_dataset_versions()


def downgrade() -> None:
    """Bỏ hai bảng (kéo theo index); `dataset_versions` trước vì nó giữ FK."""
    op.drop_table(DATASET_VERSIONS)
    op.drop_table(DATASETS)
