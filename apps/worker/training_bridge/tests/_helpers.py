"""Nền chung của test cầu nối: một job trên dataset `ready`, và payload B5-01 dựng sẵn.

Mọi test ở đây chạy trên dịch vụ thật (Postgres, Redis, kho `local_storage`) và gọi **lõi**
`run_*` với tài nguyên tiêm vào — chỉ `test_smoke.py` đi qua Celery (K23, luật 17).
"""

import hashlib
from collections.abc import Mapping
from typing import Literal
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.clock import Clock
from packages.db.models.admin_ml_jobs import TrainingJobRow
from packages.messaging.payloads.training import trained_version_id
from packages.ml_contracts.families import FAMILY_METRIC, TrainableFamily
from packages.ml_contracts.payloads import (
    MetricPoint,
    TrainingFinishedPayload,
    TrainingHeartbeatPayload,
    TrainingLogPayload,
    TrainingMetricsPayload,
)
from packages.storage.keys import model_artifact
from packages.storage.port import ObjectStorage
from packages.testing.factories.admin_ml_datasets import make_dataset, make_dataset_version
from packages.testing.factories.admin_ml_jobs import make_training_job

FAMILY: TrainableFamily = "openingAndFurnitureDetection"
METRIC = FAMILY_METRIC[FAMILY]
WEIGHTS_NAME = "weights-0123456789abcdef0123456789abcdef.onnx"
WEIGHTS_BODY = b"onnx-weights-for-tests"
WEIGHTS_SHA = hashlib.sha256(WEIGHTS_BODY).hexdigest()
ONNX_TYPE = "application/octet-stream"

Split = Literal["train", "validation"]
Level = Literal["info", "warning", "error"]
Status = Literal["succeeded", "failed", "cancelled"]
"""Ba `Literal` của payload B5-01, khai lại ở đây để hàm dựng payload không cần `type: ignore`."""


async def seed_job(
    db: AsyncSession,
    *,
    status: str = "running",
    family: TrainableFamily = FAMILY,
    epochs: int = 3,
    current_epoch: int | None = None,
    clock: Clock | None = None,
) -> TrainingJobRow:
    """Một job huấn luyện đã `commit`, trên một dataset `ready` của cùng họ.

    Mọi test cần một `dataset_version_id` có thật (FK `training_jobs`), nên dataset dựng ở
    đây thay vì ở từng test. `clock` là đồng hồ **của test**: job phải sinh ra ở mốc đó, vì
    CHECK `ended_after_started` so `ended_at` do cầu nối ghi với `started_at` của job — một
    job dựng ở giờ thật rồi chốt bằng `fake_clock` là mốc kết thúc lùi trước mốc bắt đầu.
    """
    dataset = await make_dataset(db, family=family)
    version = await make_dataset_version(db, dataset=dataset)
    return await make_training_job(
        db,
        dataset_version_id=version.id,
        family=family,
        status=status,
        epochs=epochs,
        current_epoch=current_epoch,
        created_at=None if clock is None else clock.now(),
    )


def weights_key(job_id: str, name: str = WEIGHTS_NAME) -> str:
    """Khoá trọng số đúng mẫu [5]: `model_artifact(trained_version_id(job), weights-<token>.onnx)`."""
    return model_artifact(trained_version_id(job_id), name)


async def put_weights(storage: ObjectStorage, key: str, body: bytes = WEIGHTS_BODY) -> str:
    """Đặt object trọng số vào kho và trả `sha256` kho đo được (cầu nối so với `checksum_sha256`)."""
    info = await storage.put(key, body, content_type=ONNX_TYPE, max_bytes=len(body) + 1)
    return info.sha256


def heartbeat(job_id: str, *, epoch: int = 1, sent_at_ms: int = 1) -> TrainingHeartbeatPayload:
    """Payload `heartbeat` tối thiểu."""
    return TrainingHeartbeatPayload(job_id=job_id, epoch=epoch, sent_at_ms=sent_at_ms)


def metric_point(*, step: int = 0, split: Split = "train", at_ms: int = 1, **values: float) -> MetricPoint:
    """Một điểm số đo; không truyền số đo nào thì mặc định `loss`."""
    measured = values or {"loss": 0.5}
    return MetricPoint(step=step, epoch=1, split=split, recorded_at_ms=at_ms, **measured)


def metrics(job_id: str, *points: MetricPoint) -> TrainingMetricsPayload:
    """Lô `metrics`; không truyền điểm nào thì một điểm `loss` ở bước 0."""
    return TrainingMetricsPayload(job_id=job_id, points=points or (metric_point(),))


def log_line(
    job_id: str,
    *,
    template: str,
    params: Mapping[str, str | int | float | bool],
    level: Level = "info",
) -> TrainingLogPayload:
    """Payload `log` một dòng (mẫu câu + tham số; cầu nối tự dựng văn bản)."""
    values = dict(params)
    return TrainingLogPayload(job_id=job_id, level=level, template=template, params=values)


def finished(
    job_id: str,
    *,
    status: Status = "succeeded",
    key: str | None = None,
    checksum: str | None = None,
    metric_values: Mapping[str, float] | None = None,
    error_code: str | None = None,
) -> TrainingFinishedPayload:
    """Payload `finished`; `succeeded` mặc định mang khoá đúng mẫu và số đo của họ."""
    if status != "succeeded":
        return TrainingFinishedPayload(job_id=job_id, status=status, error_code=error_code)
    return TrainingFinishedPayload(
        job_id=job_id,
        status="succeeded",
        weights_key=key if key is not None else weights_key(job_id),
        checksum_sha256=checksum if checksum is not None else WEIGHTS_SHA,
        metrics=dict(metric_values) if metric_values is not None else {METRIC: 0.75},
    )


def ms(at: datetime) -> int:
    """Mốc gửi theo millis của một `datetime` (payload B5-01 dùng `*_at_ms`)."""
    return int(at.timestamp() * 1000)
