"""Bảng `datasets`, `dataset_versions`: dataset huấn luyện và phiên bản bất biến (B6-02 [5], BE-00 §9).

Một `dataset` là một cái tên bền; mỗi lượt dựng ghi một `dataset_versions` mới, `sequence`
tăng dần, không sửa. Bản `ready` **bất biến** ([6]): `manifest_sha256`/`split_counts` chỉ
xuất hiện ở bản đó, `failure_code` chỉ ở bản `failed` — hai luật ⇔ này là bản sao DB của
luật dây trong `adminMl.ts` (HOP-DONG-MOI §8), như `admin_ml_registry`.

Unique partial `(dataset_id) WHERE status = 'building'` là lưới an toàn cuối cho C14: tại
một thời điểm, một dataset có nhiều nhất một bản đang dựng (`versions.start_version`).
"""

from datetime import datetime
from typing import Final

from sqlalchemy import CHAR, CheckConstraint, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base, TimestampMixin
from packages.db.models.auth import one_of
from packages.ml_contracts.families import MODEL_FAMILIES as FAMILY_VALUES

DATASETS: Final = "datasets"
DATASET_VERSIONS: Final = "dataset_versions"

DATASET_STATUSES: Final[tuple[str, ...]] = ("building", "ready", "failed")
"""Vòng đời một phiên bản; `ready`/`failed` là trạng thái cuối (không quay lại, [6])."""

DATASET_SOURCES: Final[tuple[str, ...]] = ("approvedFloors", "cubicasa5k")
"""Nguồn dựng mẫu; `cubicasa5k` dành cho B6-02b, khai sẵn để CHECK không phải sửa sau."""

NAME_MAX: Final = 80
SHA256_LEN: Final = 64
SHA256_PATTERN: Final = "^[0-9a-f]{64}$"
FAILURE_CODE_PATTERN: Final = "^[A-Z][A-Z0-9_]{2,63}$"

_FAMILY_CHECK: Final = one_of("family", FAMILY_VALUES)
_STATUS_CHECK: Final = one_of("status", DATASET_STATUSES)
_SOURCE_CHECK: Final = one_of("source", DATASET_SOURCES)


class DatasetRow(Base, TimestampMixin):
    """Một dataset đặt tên; `name_key` (`casefold` của `name` đã NFC) giữ tên không phân biệt hoa thường."""

    __tablename__ = DATASETS

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    name_key: Mapped[str] = mapped_column(Text, unique=True)
    family: Mapped[str] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(_FAMILY_CHECK, name="family"),
        CheckConstraint(f"char_length(name) BETWEEN 1 AND {NAME_MAX}", name="name_length"),
    )


class DatasetVersionRow(Base, TimestampMixin):
    """Một phiên bản của một dataset; chỉ thêm, chỉ `versions.py` ghi (BE-00 §7)."""

    __tablename__ = DATASET_VERSIONS

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    dataset_id: Mapped[str] = mapped_column(Text, ForeignKey(f"{DATASETS}.id"))
    sequence: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    project_ids: Mapped[list[str] | None] = mapped_column(JSONB(none_as_null=True), default=None)
    manifest_sha256: Mapped[str | None] = mapped_column(CHAR(SHA256_LEN), default=None)
    # `none_as_null=True`: bản chưa `ready` phải là NULL của SQL, không JSON `null`, để CHECK
    # `split_counts_ready` chặn đúng theo trạng thái (cùng lý do `metrics` của `admin_ml_registry`).
    split_counts: Mapped[dict[str, int] | None] = mapped_column(JSONB(none_as_null=True), default=None)
    failure_code: Mapped[str | None] = mapped_column(Text, default=None)
    build_started_at: Mapped[datetime | None] = mapped_column(default=None)
    requeue_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    created_by: Mapped[str] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(_STATUS_CHECK, name="status"),
        CheckConstraint(_SOURCE_CHECK, name="source"),
        CheckConstraint("sequence > 0", name="sequence_min"),
        CheckConstraint("requeue_count >= 0", name="requeue_count_min"),
        CheckConstraint("(manifest_sha256 IS NOT NULL) = (status = 'ready')", name="manifest_ready"),
        CheckConstraint(f"manifest_sha256 IS NULL OR manifest_sha256 ~ '{SHA256_PATTERN}'", name="manifest_format"),
        CheckConstraint("(split_counts IS NOT NULL) = (status = 'ready')", name="split_counts_ready"),
        CheckConstraint(
            "split_counts IS NULL OR split_counts ?& array['train', 'validation', 'test']",
            name="split_counts_keys",
        ),
        CheckConstraint(
            "failure_code IS NULL OR (status = 'failed' AND failure_code ~ '" + FAILURE_CODE_PATTERN + "')",
            name="failure_code",
        ),
        CheckConstraint("(failure_code IS NOT NULL) = (status = 'failed')", name="failure_code_failed"),
        Index(f"uq_{DATASET_VERSIONS}_dataset_id_sequence", "dataset_id", "sequence", unique=True),
        Index(
            f"uq_{DATASET_VERSIONS}_dataset_id_building",
            "dataset_id",
            unique=True,
            postgresql_where=text("status = 'building'"),
        ),
    )
