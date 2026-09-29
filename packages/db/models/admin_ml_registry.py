"""Bảng `model_versions`, `model_families`: registry model ML (B6-01 [5], BE-00 §9).

Hai bảng tách nhau vì hai nhịp sống khác nhau: một dòng `model_families` cho **mỗi** họ tồn
tại mãi và mang `revision` cho ghi có version (W20), còn `model_versions` chỉ thêm. Không FK
nào trỏ từ `model_versions` sang bảng job hay dataset: hai bảng ấy ra đời sau (B6-02, B6-03a),
nên `training_job_id`, `dataset_version_id` chỉ là id đã kiểm mẫu ở tầng nghiệp vụ.

Trọng số nằm ở **một** trong hai chỗ: `pinned_name` (bản ghim nhà cung cấp, ONNX xuất lúc build
ảnh `ml`) hay `weights_key` (object trong kho). CHECK `weights_location` giữ đúng một, nên không
có bản nào vừa không trọng số vừa được kích hoạt. `evaluation_error_code` chỉ có nghĩa khi
`failed`, và `metrics` ⇔ `completed` — hai luật này là bản sao DB của luật ⇔ trong `adminMl.ts`
(HOP-DONG-MOI §8), để một dòng lệch trạng thái không bao giờ ra tới dây.
"""

from datetime import datetime
from typing import Final, Literal

from sqlalchemy import CHAR, BigInteger, CheckConstraint, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base, TimestampMixin
from packages.db.models.auth import one_of
from packages.ml_contracts.families import MODEL_FAMILIES as FAMILY_VALUES

MODEL_VERSIONS: Final = "model_versions"
MODEL_FAMILIES: Final = "model_families"

EVALUATION_STATUSES: Final[tuple[str, ...]] = ("pending", "running", "completed", "failed")
"""Trạng thái đánh giá (`MODEL_EVALUATION_STATUSES` của `adminMl.ts`)."""

WEIGHTS_FORMATS: Final[tuple[str, ...]] = ("safetensors", "onnx")
"""Định dạng trọng số nhận được (`MODEL_WEIGHTS_FORMATS` của `adminMl.ts`)."""

EvaluationStatus = Literal["pending", "running", "completed", "failed"]
WeightsFormat = Literal["safetensors", "onnx"]

LABEL_MAX: Final = 80
SHA256_LEN: Final = 64
SHA256_PATTERN: Final = "^[0-9a-f]{64}$"
ERROR_CODE_PATTERN: Final = "^[A-Z][A-Z0-9_]{2,63}$"
CREATOR_MAX: Final = 64

_FAMILY_CHECK: Final = one_of("family", FAMILY_VALUES)


class ModelVersionRow(Base, TimestampMixin):
    """Một bản trọng số; chỉ thêm, không sửa trọng số (object bất biến, M06)."""

    __tablename__ = MODEL_VERSIONS

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    family: Mapped[str] = mapped_column(Text)
    label: Mapped[str] = mapped_column(Text)
    weights_format: Mapped[str] = mapped_column(Text)
    checksum_sha256: Mapped[str] = mapped_column(CHAR(SHA256_LEN))
    weights_key: Mapped[str | None] = mapped_column(Text, default=None)
    pinned_name: Mapped[str | None] = mapped_column(Text, default=None)
    training_job_id: Mapped[str | None] = mapped_column(Text, default=None)
    dataset_version_id: Mapped[str | None] = mapped_column(Text, default=None)
    evaluation_status: Mapped[str] = mapped_column(Text)
    evaluation_error_code: Mapped[str | None] = mapped_column(Text, default=None)
    # `none_as_null=True`: mặc định của SQLAlchemy biến `None` thành **JSON** `null`, thứ mà
    # `metrics IS NOT NULL` coi là có giá trị — CHECK `metrics_completed` sẽ chặn mọi bản chưa
    # `completed`. Bản không có số đo phải là NULL của SQL.
    metrics: Mapped[dict[str, float] | None] = mapped_column(JSONB(none_as_null=True), default=None)
    evaluation_attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    evaluation_requested_at: Mapped[datetime | None] = mapped_column(default=None)
    creator_id: Mapped[str] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(_FAMILY_CHECK, name="family"),
        CheckConstraint(f"char_length(label) BETWEEN 1 AND {LABEL_MAX}", name="label_length"),
        CheckConstraint(one_of("weights_format", WEIGHTS_FORMATS), name="weights_format"),
        CheckConstraint(f"checksum_sha256 ~ '{SHA256_PATTERN}'", name="checksum_format"),
        # Đúng một chỗ chứa trọng số: bản ghim nhà cung cấp, hay object trong kho.
        CheckConstraint("(weights_key IS NULL) <> (pinned_name IS NULL)", name="weights_location"),
        CheckConstraint("(training_job_id IS NULL) = (dataset_version_id IS NULL)", name="training_pair"),
        CheckConstraint(one_of("evaluation_status", EVALUATION_STATUSES), name="evaluation_status"),
        # Mã lỗi đánh giá chỉ tồn tại ở bản `failed` (và không bao giờ ra dây, K01).
        CheckConstraint(
            "evaluation_error_code IS NULL"
            f" OR (evaluation_status = 'failed' AND evaluation_error_code ~ '{ERROR_CODE_PATTERN}')",
            name="evaluation_error_code",
        ),
        CheckConstraint("(metrics IS NOT NULL) = (evaluation_status = 'completed')", name="metrics_completed"),
        CheckConstraint("evaluation_attempts >= 0", name="evaluation_attempts_min"),
        CheckConstraint(f"char_length(creator_id) BETWEEN 1 AND {CREATOR_MAX}", name="creator_id_length"),
        # Một job huấn luyện sinh nhiều nhất một bản (J06 của `register_trained_version`).
        Index(
            f"uq_{MODEL_VERSIONS}_training_job_id",
            "training_job_id",
            unique=True,
            postgresql_where=text("training_job_id IS NOT NULL"),
        ),
        # N25: mới nhất trước, lọc theo họ; cursor đi theo `(created_at, id)`.
        Index(f"ix_{MODEL_VERSIONS}_family_created_at_id", "family", text("created_at DESC"), text("id DESC")),
    )


class ModelFamilyRow(Base, TimestampMixin):
    """Một họ và bản đang kích hoạt; `revision` là số ghi có version của N24 (W20).

    `last_writer_id` (`sub` người ghi, K05 — không FK vì người có thể bị xoá) cùng
    `last_body_sha256` nhận ra lượt ghi lặp của chính người đó (C09b).
    """

    __tablename__ = MODEL_FAMILIES

    family: Mapped[str] = mapped_column(Text, primary_key=True)
    revision: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    active_version_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey(f"{MODEL_VERSIONS}.id", ondelete="RESTRICT"), default=None
    )
    last_writer_id: Mapped[str | None] = mapped_column(Text, default=None)
    last_body_sha256: Mapped[str | None] = mapped_column(CHAR(SHA256_LEN), default=None)

    __table_args__ = (
        CheckConstraint(_FAMILY_CHECK, name="family"),
        CheckConstraint("revision >= 0", name="revision_min"),
        CheckConstraint(
            f"last_body_sha256 IS NULL OR last_body_sha256 ~ '{SHA256_PATTERN}'", name="last_body_sha256_format"
        ),
    )
