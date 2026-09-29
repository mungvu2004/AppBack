"""ml_registry

Revision ID: r20260928_b6_01
Revises: r20260928_b4_02
Create Date: 2026-09-28

Hai bảng registry model ML (B6-01 [5], BE-00 §6.1): expand thuần, một bảng mới mỗi bảng và
một FK `model_families.active_version_id → model_versions.id`. Hằng số (tên bảng, tập giá trị,
checksum bản ghim) **chép tay** từ `packages/db/models/admin_ml_registry.py` và
`packages/ml_contracts/pinned.py`: migration không nhập module model hay `ml_contracts`, nên
một lần đổi `PINNED[*].onnx_sha256` về sau phải là revision dữ liệu **mới** (DEBT NO-061),
không phải sửa file này.

Dữ liệu gốc do `seed_rows` dựng — hàm thuần, nên test gọi được với bảng hằng giả: bản nào có
checksum chưa ghim (`"0" * 64`) thì `failed` + `MODEL_NOT_PINNED` và họ của nó **không** được
kích hoạt, để migration vẫn chạy khi chưa đo được SHA của trọng số nhà cung cấp.

Luật expand/contract: BE-00 §6.1 (`tools/lint_migrations.py` chặn drop/rename/NOT NULL).
"""

from collections.abc import Sequence
from typing import Final

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "r20260928_b6_01"
down_revision: str | None = "r20260928_b4_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MODEL_VERSIONS: Final = "model_versions"
MODEL_FAMILIES: Final = "model_families"

FAMILY_VALUES: Final = ("wallSegmentation", "openingAndFurnitureDetection", "dimensionReading")
EVALUATION_STATUSES: Final = ("pending", "running", "completed", "failed")
WEIGHTS_FORMATS: Final = ("safetensors", "onnx")
LABEL_MAX: Final = 80
SHA256_LEN: Final = 64
SHA256_PATTERN: Final = "^[0-9a-f]{64}$"
ERROR_CODE_PATTERN: Final = "^[A-Z][A-Z0-9_]{2,63}$"
CREATOR_MAX: Final = 64

UNPINNED: Final = "0" * SHA256_LEN
"""`packages/ml_contracts/pinned.py:33` — SHA của bản chưa đo được."""

SEED_LABEL: Final = "gốc"
SEED_CREATOR: Final = "system:pipeline"
SEED_FORMAT: Final = "onnx"
NOT_PINNED_CODE: Final = "MODEL_NOT_PINNED"

BASELINE_SEED: Final[tuple[tuple[str, str, str, str], ...]] = (
    (
        "openingAndFurnitureDetection",
        "mdl_01KB6010000000000000000001",
        "yolov8n",
        "1e252b7363e1936a0f06a40c221f144f65e86ae8ef01c96e71f7fb33cc3a334d",
    ),
    (
        "dimensionReading",
        "mdl_01KB6010000000000000000002",
        "rapidocrRec",
        "48fc40f24f6d2a207a2b1091d3437eb3cc3eb6b676dc3ef9c37384005483683b",
    ),
)
"""`(họ, id bản gốc, tên bản ghim, onnx_sha256)` — `BASELINE` + `PINNED` lúc B6-01 hợp nhất.

`wallSegmentation` vắng: SegFormer không xuất ONNX, họ tường chạy đường cổ điển (BE-00 §9).
"""


def _in_values(column: str, values: tuple[str, ...]) -> str:
    """`CHECK` "cột thuộc tập giá trị" — cùng chuỗi với `one_of` của model (bước 6 so tên và thân)."""
    quoted = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({quoted})"


def seed_rows(
    baseline: Sequence[tuple[str, str, str, str]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """`(hàng model_versions, hàng model_families)` của dữ liệu gốc — thuần, không chạm DB.

    Mỗi họ trong `FAMILY_VALUES` được đúng một dòng `model_families` `revision = 0`; họ có bản
    gốc **đã ghim** thì dòng ấy kích hoạt sẵn bản đó. Bản chưa ghim vào bảng ở trạng thái
    `failed` + `MODEL_NOT_PINNED` và **không** được kích hoạt: worker `ml` không nạp nổi nó,
    nên kích hoạt sẵn sẽ làm mọi lượt pipeline của họ đó hỏng ngay.
    """
    versions: list[dict[str, object]] = []
    active: dict[str, str] = {}
    for family, version_id, pinned_name, checksum in baseline:
        pinned = checksum != UNPINNED
        versions.append(
            {
                "id": version_id,
                "family": family,
                "label": SEED_LABEL,
                "weights_format": SEED_FORMAT,
                "checksum_sha256": checksum,
                "pinned_name": pinned_name,
                "evaluation_status": "pending" if pinned else "failed",
                "evaluation_error_code": None if pinned else NOT_PINNED_CODE,
                "evaluation_attempts": 0,
                "creator_id": SEED_CREATOR,
            }
        )
        if pinned:
            active[family] = version_id
    families: list[dict[str, object]] = [
        {"family": family, "revision": 0, "active_version_id": active.get(family)} for family in FAMILY_VALUES
    ]
    return versions, families


def _versions_table() -> sa.TableClause:
    """Bảng nhẹ cho `bulk_insert`: chỉ cột dữ liệu gốc ghi; `created_at` để server default."""
    return sa.table(
        MODEL_VERSIONS,
        sa.column("id", sa.Text),
        sa.column("family", sa.Text),
        sa.column("label", sa.Text),
        sa.column("weights_format", sa.Text),
        sa.column("checksum_sha256", sa.CHAR(SHA256_LEN)),
        sa.column("pinned_name", sa.Text),
        sa.column("evaluation_status", sa.Text),
        sa.column("evaluation_error_code", sa.Text),
        sa.column("evaluation_attempts", sa.Integer),
        sa.column("creator_id", sa.Text),
    )


def _families_table() -> sa.TableClause:
    """Bảng nhẹ cho `bulk_insert` của `model_families`."""
    return sa.table(
        MODEL_FAMILIES,
        sa.column("family", sa.Text),
        sa.column("revision", sa.BigInteger),
        sa.column("active_version_id", sa.Text),
    )


def _create_model_versions() -> None:
    """Bảng `model_versions` + hai index (unique partial theo job, danh sách N25)."""
    op.create_table(
        MODEL_VERSIONS,
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("family", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("weights_format", sa.Text(), nullable=False),
        sa.Column("checksum_sha256", sa.CHAR(SHA256_LEN), nullable=False),
        sa.Column("weights_key", sa.Text(), nullable=True),
        sa.Column("pinned_name", sa.Text(), nullable=True),
        sa.Column("training_job_id", sa.Text(), nullable=True),
        sa.Column("dataset_version_id", sa.Text(), nullable=True),
        sa.Column("evaluation_status", sa.Text(), nullable=False),
        sa.Column("evaluation_error_code", sa.Text(), nullable=True),
        sa.Column("metrics", JSONB(), nullable=True),
        sa.Column("evaluation_attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("evaluation_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("creator_id", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(_in_values("family", FAMILY_VALUES), name=op.f(f"ck_{MODEL_VERSIONS}_family")),
        sa.CheckConstraint(
            f"char_length(label) BETWEEN 1 AND {LABEL_MAX}", name=op.f(f"ck_{MODEL_VERSIONS}_label_length")
        ),
        sa.CheckConstraint(
            _in_values("weights_format", WEIGHTS_FORMATS), name=op.f(f"ck_{MODEL_VERSIONS}_weights_format")
        ),
        sa.CheckConstraint(f"checksum_sha256 ~ '{SHA256_PATTERN}'", name=op.f(f"ck_{MODEL_VERSIONS}_checksum_format")),
        sa.CheckConstraint(
            "(weights_key IS NULL) <> (pinned_name IS NULL)", name=op.f(f"ck_{MODEL_VERSIONS}_weights_location")
        ),
        sa.CheckConstraint(
            "(training_job_id IS NULL) = (dataset_version_id IS NULL)",
            name=op.f(f"ck_{MODEL_VERSIONS}_training_pair"),
        ),
        sa.CheckConstraint(
            _in_values("evaluation_status", EVALUATION_STATUSES),
            name=op.f(f"ck_{MODEL_VERSIONS}_evaluation_status"),
        ),
        sa.CheckConstraint(
            "evaluation_error_code IS NULL"
            f" OR (evaluation_status = 'failed' AND evaluation_error_code ~ '{ERROR_CODE_PATTERN}')",
            name=op.f(f"ck_{MODEL_VERSIONS}_evaluation_error_code"),
        ),
        sa.CheckConstraint(
            "(metrics IS NOT NULL) = (evaluation_status = 'completed')",
            name=op.f(f"ck_{MODEL_VERSIONS}_metrics_completed"),
        ),
        sa.CheckConstraint("evaluation_attempts >= 0", name=op.f(f"ck_{MODEL_VERSIONS}_evaluation_attempts_min")),
        sa.CheckConstraint(
            f"char_length(creator_id) BETWEEN 1 AND {CREATOR_MAX}",
            name=op.f(f"ck_{MODEL_VERSIONS}_creator_id_length"),
        ),
        sa.PrimaryKeyConstraint("id", name=f"pk_{MODEL_VERSIONS}"),
    )
    op.create_index(
        f"uq_{MODEL_VERSIONS}_training_job_id",
        MODEL_VERSIONS,
        ["training_job_id"],
        unique=True,
        postgresql_where=sa.text("training_job_id IS NOT NULL"),
    )
    op.create_index(
        f"ix_{MODEL_VERSIONS}_family_created_at_id",
        MODEL_VERSIONS,
        ["family", sa.text("created_at DESC"), sa.text("id DESC")],
    )


def _create_model_families() -> None:
    """Bảng `model_families`; FK sang `model_versions` nên phải tạo sau bảng kia."""
    op.create_table(
        MODEL_FAMILIES,
        sa.Column("family", sa.Text(), nullable=False),
        sa.Column("revision", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("active_version_id", sa.Text(), nullable=True),
        sa.Column("last_writer_id", sa.Text(), nullable=True),
        sa.Column("last_body_sha256", sa.CHAR(SHA256_LEN), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(_in_values("family", FAMILY_VALUES), name=op.f(f"ck_{MODEL_FAMILIES}_family")),
        sa.CheckConstraint("revision >= 0", name=op.f(f"ck_{MODEL_FAMILIES}_revision_min")),
        sa.CheckConstraint(
            f"last_body_sha256 IS NULL OR last_body_sha256 ~ '{SHA256_PATTERN}'",
            name=op.f(f"ck_{MODEL_FAMILIES}_last_body_sha256_format"),
        ),
        sa.ForeignKeyConstraint(
            ["active_version_id"],
            [f"{MODEL_VERSIONS}.id"],
            name=op.f(f"fk_{MODEL_FAMILIES}_active_version_id_{MODEL_VERSIONS}"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("family", name=f"pk_{MODEL_FAMILIES}"),
    )


def upgrade() -> None:
    """Expand: hai bảng, hai index, rồi dữ liệu gốc (2 bản + 3 họ)."""
    _create_model_versions()
    _create_model_families()
    versions, families = seed_rows(BASELINE_SEED)
    op.bulk_insert(_versions_table(), versions)
    op.bulk_insert(_families_table(), families)


def downgrade() -> None:
    """Bỏ hai bảng (kéo theo index và dữ liệu gốc); `model_families` trước vì nó giữ FK."""
    op.drop_table(MODEL_FAMILIES)
    op.drop_table(MODEL_VERSIONS)
