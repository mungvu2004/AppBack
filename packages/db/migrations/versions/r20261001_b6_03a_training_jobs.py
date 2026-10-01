"""training_jobs

Revision ID: r20261001_b6_03a
Revises: r20260930_b5_06a
Create Date: 2026-10-01

Ba bảng `training_jobs`, `training_metrics`, `training_logs` (B6-03a [5], BE-00 §6.1): expand
thuần. Hằng số (tên bảng, tập giá trị) **chép tay** từ `packages/db/models/admin_ml_jobs.py`,
theo đúng khuôn `r20260929_b6_02_ml_datasets.py`: migration không nhập module model.

Luật expand/contract: BE-00 §6.1 (`tools/lint_migrations.py` chặn drop/rename/NOT NULL).
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Final

import sqlalchemy as sa
from alembic import op

revision: str = "r20261001_b6_03a"
down_revision: str | None = "r20260930_b5_06a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TRAINING_JOBS: Final = "training_jobs"
TRAINING_METRICS: Final = "training_metrics"
TRAINING_LOGS: Final = "training_logs"
DATASET_VERSIONS: Final = "dataset_versions"
MODEL_VERSIONS: Final = "model_versions"

TRAINABLE_FAMILIES: Final = ("wallSegmentation", "openingAndFurnitureDetection")
TRAINING_JOB_STATUSES: Final = ("queued", "running", "succeeded", "failed", "cancelling", "cancelled")
METRIC_SPLITS: Final = ("train", "validation")
LOG_LEVELS: Final = ("info", "warning", "error")
EPOCHS_MAX: Final = 300
LOG_MESSAGE_MAX: Final = 2000
FAILURE_CODE_PATTERN: Final = "^[A-Z][A-Z0-9_]{2,63}$"
SHA256_LEN: Final = 64
_FINISHED_SQL: Final = "status IN ('succeeded', 'failed', 'cancelled')"


def _in_values(column: str, values: tuple[str, ...]) -> str:
    """`CHECK` "cột thuộc tập giá trị" — cùng chuỗi với `one_of` của model (bước 6 so tên và thân)."""
    quoted = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({quoted})"


def _ck(table: str, name: str, sql: str) -> sa.CheckConstraint:
    """CHECK đặt tên theo `NAMING_CONVENTION` (`ck_<bảng>_<tên>`), như model sinh ra."""
    return sa.CheckConstraint(sql, name=op.f(f"ck_{table}_{name}"))


def _time(name: str, *, nullable: bool = True, now: bool = False) -> sa.Column[datetime]:
    """Cột `timestamptz`; `now=True` cho `created_at`/`updated_at` (mặc định `now()` như `TimestampMixin`)."""
    default = sa.text("now()") if now else None
    return sa.Column(name, sa.DateTime(timezone=True), server_default=default, nullable=nullable)


def _create_training_jobs() -> None:
    """Bảng `training_jobs`: CHECK gương mọi refine `TrainingJobSchema` (HOP-DONG-MOI §8)."""
    t = TRAINING_JOBS
    op.create_table(
        t,
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("family", sa.Text(), nullable=False),
        sa.Column("dataset_version_id", sa.Text(), nullable=False),
        sa.Column("base_model", sa.Text(), nullable=False),
        sa.Column("epochs", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'queued'"), nullable=False),
        sa.Column("current_epoch", sa.Integer(), nullable=True),
        sa.Column("result_model_version_id", sa.Text(), nullable=True),
        sa.Column("failure_code", sa.Text(), nullable=True),
        _time("started_at"),
        _time("ended_at"),
        _time("last_heartbeat_at"),
        _time("artifacts_purged_at"),
        sa.Column("requeue_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("creator_id", sa.Text(), nullable=False),
        _time("created_at", nullable=False, now=True),
        _time("updated_at", nullable=False, now=True),
        _ck(t, "family", _in_values("family", TRAINABLE_FAMILIES)),
        _ck(t, "status", _in_values("status", TRAINING_JOB_STATUSES)),
        _ck(t, "epochs_range", f"epochs BETWEEN 1 AND {EPOCHS_MAX}"),
        _ck(t, "current_epoch_range", "current_epoch IS NULL OR current_epoch BETWEEN 0 AND epochs"),
        _ck(t, "requeue_count_min", "requeue_count >= 0"),
        _ck(t, "result_succeeded", "(result_model_version_id IS NOT NULL) = (status = 'succeeded')"),
        _ck(t, "failure_code_failed", "(failure_code IS NOT NULL) = (status = 'failed')"),
        _ck(t, "failure_code_format", "failure_code IS NULL OR failure_code ~ '" + FAILURE_CODE_PATTERN + "'"),
        _ck(t, "ended_finished", f"(ended_at IS NOT NULL) = ({_FINISHED_SQL})"),
        _ck(t, "queued_not_started", "status <> 'queued' OR started_at IS NULL"),
        _ck(t, "started_present", "status NOT IN ('running', 'cancelling', 'succeeded') OR started_at IS NOT NULL"),
        _ck(t, "ended_after_started", "ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at"),
        sa.ForeignKeyConstraint(
            ["dataset_version_id"],
            [f"{DATASET_VERSIONS}.id"],
            name=op.f(f"fk_{t}_dataset_version_id_{DATASET_VERSIONS}"),
        ),
        sa.ForeignKeyConstraint(
            ["result_model_version_id"],
            [f"{MODEL_VERSIONS}.id"],
            name=op.f(f"fk_{t}_result_model_version_id_{MODEL_VERSIONS}"),
        ),
        sa.PrimaryKeyConstraint("id", name=f"pk_{t}"),
    )
    op.create_index(f"ix_{t}_created_at_id", t, ["created_at", "id"])
    op.create_index(
        f"ix_{t}_status_active",
        t,
        ["status"],
        postgresql_where=sa.text("status IN ('queued', 'running', 'cancelling')"),
    )


def _create_training_metrics() -> None:
    """Bảng `training_metrics`: PK `(job_id, split, step)` là lưới J06 của cầu nối."""
    t = TRAINING_METRICS
    op.create_table(
        t,
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("split", sa.Text(), nullable=False),
        sa.Column("step", sa.Integer(), nullable=False),
        sa.Column("epoch", sa.Integer(), nullable=False),
        _time("recorded_at", nullable=False),
        sa.Column("loss", sa.Float(), nullable=True),
        sa.Column("iou", sa.Float(), nullable=True),
        sa.Column("map50", sa.Float(), nullable=True),
        _time("created_at", nullable=False, now=True),
        _time("updated_at", nullable=False, now=True),
        _ck(t, "split", _in_values("split", METRIC_SPLITS)),
        _ck(t, "step_min", "step >= 0"),
        _ck(t, "epoch_min", "epoch >= 1"),
        _ck(t, "has_value", "loss IS NOT NULL OR iou IS NOT NULL OR map50 IS NOT NULL"),
        _ck(t, "loss_min", "loss IS NULL OR loss >= 0"),
        _ck(t, "iou_range", "iou IS NULL OR iou BETWEEN 0 AND 1"),
        _ck(t, "map50_range", "map50 IS NULL OR map50 BETWEEN 0 AND 1"),
        sa.ForeignKeyConstraint(
            ["job_id"], [f"{TRAINING_JOBS}.id"], name=op.f(f"fk_{t}_job_id_{TRAINING_JOBS}"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("job_id", "split", "step", name=f"pk_{t}"),
    )


def _create_training_logs() -> None:
    """Bảng `training_logs`: PK `(job_id, seq)`, unique `(job_id, dedupe_sha)` chặn dòng lặp (J06)."""
    t = TRAINING_LOGS
    op.create_table(
        t,
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        _time("at", nullable=False),
        sa.Column("level", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("dedupe_sha", sa.CHAR(SHA256_LEN), nullable=False),
        _time("created_at", nullable=False, now=True),
        _time("updated_at", nullable=False, now=True),
        _ck(t, "seq_min", "seq >= 0"),
        _ck(t, "level", _in_values("level", LOG_LEVELS)),
        _ck(t, "message_length", f"char_length(message) BETWEEN 1 AND {LOG_MESSAGE_MAX}"),
        sa.ForeignKeyConstraint(
            ["job_id"], [f"{TRAINING_JOBS}.id"], name=op.f(f"fk_{t}_job_id_{TRAINING_JOBS}"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("job_id", "seq", name=f"pk_{t}"),
    )
    op.create_index(f"uq_{t}_job_id_dedupe_sha", t, ["job_id", "dedupe_sha"], unique=True)


def upgrade() -> None:
    """Expand: ba bảng theo thứ tự FK (job trước số đo, log)."""
    _create_training_jobs()
    _create_training_metrics()
    _create_training_logs()


def downgrade() -> None:
    """Bỏ ba bảng theo thứ tự ngược FK."""
    op.drop_table(TRAINING_LOGS)
    op.drop_table(TRAINING_METRICS)
    op.drop_table(TRAINING_JOBS)
