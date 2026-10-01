"""Hằng và helper dùng chung của test route job huấn luyện (B6-03a, việc A).

Hàng `training_metrics`/`training_logs` chèn **thẳng** ở đây: factory của prep chỉ dựng
job (cầu nối là chủ hai bảng kia, và nó chưa hợp nhất), còn N36/N37 cần đặt chính xác
`(step, split)` và `seq` để kiểm luật "bước cuối chờ đủ split" và cửa sổ muộn.
"""

from datetime import datetime
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.admin_ml_jobs import TrainingLogRow, TrainingMetricRow

JOBS_PATH: Final = "/api/admin/ml/training-jobs"
TRAINING_QUEUE: Final = "ml.training"
"""Hàng của `ml.training.runner.start` (`packages/messaging/celery_app.py` `queue_for`)."""

WALL: Final = "wallSegmentation"
OPENING: Final = "openingAndFurnitureDetection"
DIMENSION: Final = "dimensionReading"

MISSING_JOB_ID: Final = "job_01KB6030000000000000000404"
"""Id đúng mẫu nhưng không có dòng nào — C08 của bốn route có `{job_id}`."""


def job_path(job_id: str) -> str:
    """`/api/admin/ml/training-jobs/{job_id}`."""
    return f"{JOBS_PATH}/{job_id}"


def cancel_path(job_id: str) -> str:
    """Đường N35."""
    return f"{job_path(job_id)}/cancel"


def metrics_path(job_id: str) -> str:
    """Đường N36."""
    return f"{job_path(job_id)}/metrics"


def logs_path(job_id: str) -> str:
    """Đường N37."""
    return f"{job_path(job_id)}/logs"


async def add_metrics(
    db: AsyncSession, *, job_id: str, at: datetime, points: list[tuple[int, str]], epoch: int = 1
) -> None:
    """Chèn `(step, split)` đã cho với một số đo `loss`; `commit` để route đọc bằng session khác."""
    db.add_all(
        TrainingMetricRow(job_id=job_id, split=split, step=step, epoch=epoch, recorded_at=at, loss=0.5)
        for step, split in points
    )
    await db.commit()


async def add_logs(db: AsyncSession, *, job_id: str, at: datetime, seqs: list[int]) -> None:
    """Chèn các dòng log `seq` đã cho; `dedupe_sha` duy nhất theo `seq` (unique `(job_id, dedupe_sha)`)."""
    db.add_all(
        TrainingLogRow(job_id=job_id, seq=seq, at=at, level="info", message=f"dong log {seq}", dedupe_sha=f"{seq:064d}")
        for seq in seqs
    )
    await db.commit()
