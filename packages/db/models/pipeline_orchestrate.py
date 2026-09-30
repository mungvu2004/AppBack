"""Bảng `pipeline_run_models`: ghim model và sổ theo dõi của một lượt chạy (B5-06a [5]).

`run_id` vừa là PK vừa là FK `ON DELETE CASCADE` tới `pipeline_runs.id` nên mỗi lượt nhiều
nhất một dòng ghim và xoá cứng lượt là một lệnh `DELETE` (cùng khuôn `quality_assessments`).
`pinned`, `used` là JSONB theo hợp đồng `RunPins` ([2]); DB không kiểm hình dạng, chỉ CHECK
hai trần đếm không âm. Chỉ mục một phần `(run_id) WHERE artifacts_purged_at IS NULL` phục vụ
lịch dọn artifact (B5-06c, W12) tra "lượt chưa dọn" mà không quét dòng đã dọn xong.
"""

from datetime import datetime
from typing import Any, Final

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base, TimestampMixin
from packages.db.models.drawings import PIPELINE_RUNS

PIPELINE_RUN_MODELS: Final = "pipeline_run_models"


class PipelineRunModelsRow(Base, TimestampMixin):
    """Ghim ba họ model và sổ dùng/quét bù của một lượt; một dòng mỗi lượt (upsert theo `run_id`)."""

    __tablename__ = PIPELINE_RUN_MODELS

    run_id: Mapped[str] = mapped_column(Text, ForeignKey(f"{PIPELINE_RUNS}.id", ondelete="CASCADE"), primary_key=True)
    pinned: Mapped[Any] = mapped_column(JSONB)
    used: Mapped[Any] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    persisted_revision: Mapped[int | None] = mapped_column(BigInteger, default=None)
    step_requeue_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(default=None)
    artifacts_purged_at: Mapped[datetime | None] = mapped_column(default=None)

    __table_args__ = (
        CheckConstraint("persisted_revision IS NULL OR persisted_revision >= 0", name="persisted_revision_min"),
        CheckConstraint("step_requeue_count >= 0", name="step_requeue_count_min"),
        Index(
            f"ix_{PIPELINE_RUN_MODELS}_run_id_not_purged",
            "run_id",
            postgresql_where=text("artifacts_purged_at IS NULL"),
        ),
    )
