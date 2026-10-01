"""Bảng `training_jobs`, `training_metrics`, `training_logs`: job huấn luyện và tiến trình (B6-03a [5]).

CHECK của `training_jobs` là bản sao DB của mọi refine `TrainingJobSchema` (HOP-DONG-MOI §8):
`result_model_version_id` ⇔ `succeeded`, `failure_code` ⇔ `failed`, `ended_at` ⇔ trạng thái
cuối, `queued` không có `started_at`. Thứ tự khoá (BE-00 §9): `training_jobs` trước
`training_metrics`, `training_logs` và trước mọi bảng `model_*`.

`training_metrics`, `training_logs` chỉ thêm; khoá chính `(job_id, split, step)`,
`(job_id, seq)` và unique `(job_id, dedupe_sha)` là lưới J06 cuối cùng của cầu nối.
"""

from datetime import datetime
from typing import Final

from sqlalchemy import CHAR, CheckConstraint, Float, ForeignKey, Index, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base, TimestampMixin
from packages.db.models.admin_ml_datasets import DATASET_VERSIONS
from packages.db.models.admin_ml_registry import MODEL_VERSIONS
from packages.db.models.auth import one_of
from packages.ml_contracts.families import TRAINABLE_FAMILIES

TRAINING_JOBS: Final = "training_jobs"
TRAINING_METRICS: Final = "training_metrics"
TRAINING_LOGS: Final = "training_logs"

TRAINING_JOB_STATUSES: Final[tuple[str, ...]] = ("queued", "running", "succeeded", "failed", "cancelling", "cancelled")
"""`TRAINING_JOB_STATUSES` (HOP-DONG-MOI §8); ba trạng thái cuối ở `FINISHED_STATUSES`."""

FINISHED_STATUSES: Final[tuple[str, ...]] = ("succeeded", "failed", "cancelled")
"""Trạng thái không đổi nữa: có `ended_at`, cửa sổ muộn tính từ đó."""

METRIC_SPLITS: Final[tuple[str, ...]] = ("train", "validation")
LOG_LEVELS: Final[tuple[str, ...]] = ("info", "warning", "error")

EPOCHS_MAX: Final = 300
LOG_MESSAGE_MAX: Final = 2000
FAILURE_CODE_PATTERN: Final = "^[A-Z][A-Z0-9_]{2,63}$"
SHA256_LEN: Final = 64

_FINISHED_SQL: Final = "status IN ('succeeded', 'failed', 'cancelled')"


class TrainingJobRow(Base, TimestampMixin):
    """Một job huấn luyện; N33 chèn, N35 và cầu nối `training_bridge` đổi trạng thái dưới `FOR UPDATE`."""

    __tablename__ = TRAINING_JOBS

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    family: Mapped[str] = mapped_column(Text)
    dataset_version_id: Mapped[str] = mapped_column(Text, ForeignKey(f"{DATASET_VERSIONS}.id"))
    base_model: Mapped[str] = mapped_column(Text)
    epochs: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text, server_default=text("'queued'"))
    current_epoch: Mapped[int | None] = mapped_column(Integer, default=None)
    result_model_version_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey(f"{MODEL_VERSIONS}.id"), default=None
    )
    failure_code: Mapped[str | None] = mapped_column(Text, default=None)
    started_at: Mapped[datetime | None] = mapped_column(default=None)
    ended_at: Mapped[datetime | None] = mapped_column(default=None)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(default=None)
    artifacts_purged_at: Mapped[datetime | None] = mapped_column(default=None)
    requeue_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    creator_id: Mapped[str] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(one_of("family", TRAINABLE_FAMILIES), name="family"),
        CheckConstraint(one_of("status", TRAINING_JOB_STATUSES), name="status"),
        CheckConstraint(f"epochs BETWEEN 1 AND {EPOCHS_MAX}", name="epochs_range"),
        CheckConstraint("current_epoch IS NULL OR current_epoch BETWEEN 0 AND epochs", name="current_epoch_range"),
        CheckConstraint("requeue_count >= 0", name="requeue_count_min"),
        CheckConstraint("(result_model_version_id IS NOT NULL) = (status = 'succeeded')", name="result_succeeded"),
        CheckConstraint("(failure_code IS NOT NULL) = (status = 'failed')", name="failure_code_failed"),
        CheckConstraint(
            "failure_code IS NULL OR failure_code ~ '" + FAILURE_CODE_PATTERN + "'", name="failure_code_format"
        ),
        CheckConstraint(f"(ended_at IS NOT NULL) = ({_FINISHED_SQL})", name="ended_finished"),
        CheckConstraint("status <> 'queued' OR started_at IS NULL", name="queued_not_started"),
        CheckConstraint(
            "status NOT IN ('running', 'cancelling', 'succeeded') OR started_at IS NOT NULL", name="started_present"
        ),
        CheckConstraint("ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at", name="ended_after_started"),
        Index(f"ix_{TRAINING_JOBS}_created_at_id", "created_at", "id"),
        Index(
            f"ix_{TRAINING_JOBS}_status_active",
            "status",
            postgresql_where=text("status IN ('queued', 'running', 'cancelling')"),
        ),
    )


class TrainingMetricRow(Base):
    """Một điểm số đo; `(job_id, split, step)` đã có thì cầu nối bỏ điểm mới (J06)."""

    __tablename__ = TRAINING_METRICS

    job_id: Mapped[str] = mapped_column(Text, ForeignKey(f"{TRAINING_JOBS}.id", ondelete="CASCADE"), primary_key=True)
    split: Mapped[str] = mapped_column(Text, primary_key=True)
    step: Mapped[int] = mapped_column(Integer, primary_key=True)
    epoch: Mapped[int] = mapped_column(Integer)
    recorded_at: Mapped[datetime]
    loss: Mapped[float | None] = mapped_column(Float, default=None)
    iou: Mapped[float | None] = mapped_column(Float, default=None)
    map50: Mapped[float | None] = mapped_column(Float, default=None)

    __table_args__ = (
        CheckConstraint(one_of("split", METRIC_SPLITS), name="split"),
        CheckConstraint("step >= 0", name="step_min"),
        CheckConstraint("epoch >= 1", name="epoch_min"),
        CheckConstraint("loss IS NOT NULL OR iou IS NOT NULL OR map50 IS NOT NULL", name="has_value"),
        CheckConstraint("loss IS NULL OR loss >= 0", name="loss_min"),
        CheckConstraint("iou IS NULL OR iou BETWEEN 0 AND 1", name="iou_range"),
        CheckConstraint("map50 IS NULL OR map50 BETWEEN 0 AND 1", name="map50_range"),
    )


class TrainingLogRow(Base):
    """Một dòng log đã dựng từ mẫu câu (`render_log`); `seq` = lớn nhất + 1 dưới khoá job."""

    __tablename__ = TRAINING_LOGS

    job_id: Mapped[str] = mapped_column(Text, ForeignKey(f"{TRAINING_JOBS}.id", ondelete="CASCADE"), primary_key=True)
    seq: Mapped[int] = mapped_column(Integer, primary_key=True)
    at: Mapped[datetime]
    level: Mapped[str] = mapped_column(Text)
    message: Mapped[str] = mapped_column(Text)
    dedupe_sha: Mapped[str] = mapped_column(CHAR(SHA256_LEN))

    __table_args__ = (
        CheckConstraint("seq >= 0", name="seq_min"),
        CheckConstraint(one_of("level", LOG_LEVELS), name="level"),
        CheckConstraint(f"char_length(message) BETWEEN 1 AND {LOG_MESSAGE_MAX}", name="message_length"),
        Index(f"uq_{TRAINING_LOGS}_job_id_dedupe_sha", "job_id", "dedupe_sha", unique=True),
    )
