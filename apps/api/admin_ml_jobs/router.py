"""Sáu route job huấn luyện N32-N37 (B6-03a [2], [7]); router **mỏng**.

Cả sáu đòi `require_admin` (khoá `admin`), khai một lần ở router: `engineer`, `viewer`
→ 403 trước khi endpoint chạy. `idempotency="auto"` (mặc định của khung) đủ cho N33 và
N35: cả hai ghi, thân JSON nhỏ, nên bảng idempotency chung ghi lại được lượt lặp (K18).

N36/N37 **không** dùng `page_params`: cursor của chúng là một chuỗi số (`since` = bước
hay `seq`, loại trừ) mà FE tự dựng lại được, không phải cursor ký HMAC — nên hai tham
số `since`/`limit` khai tại chỗ, với cùng trần 200 của HOP-DONG-MOI §0.
"""

from typing import Annotated, Final

from fastapi import Depends, Query

from apps.api.access.deps import require_admin
from apps.api.admin_ml_jobs import service
from apps.api.admin_ml_jobs.schemas import (
    CancelTrainingJobIn,
    CreateTrainingJobIn,
    TrainingJobOut,
    TrainingJobPage,
    TrainingLogPage,
    TrainingMetricPage,
)
from apps.api.core.deps import ClockDep, CurrentPrincipal, DbSession
from apps.api.core.pagination import DEFAULT_LIMIT, MAX_LIMIT, PageParams, page_params
from apps.api.core.routing import protected_router

router = protected_router(tags=["admin_ml_jobs"], dependencies=[Depends(require_admin)])
ROUTERS: Final = (router,)

SINCE_MIN: Final = -1
"""`since` loại trừ, nên `-1` là "từ đầu" (`step`/`seq` nhỏ nhất là 0)."""

Since = Annotated[int, Query(ge=SINCE_MIN)]
StreamLimit = Annotated[int, Query(ge=1, le=MAX_LIMIT)]


@router.get("/admin/ml/training-jobs")
async def ml_list_jobs(
    db: DbSession,
    page: Annotated[PageParams, Depends(page_params(max_limit=MAX_LIMIT))],
    family: str | None = None,
    status: str | None = None,
) -> TrainingJobPage:
    """N32 — job huấn luyện, mới nhất trước; `family`/`status` lạ → 422 `field`."""
    return await service.list_jobs(db, family=family, status=status, page=page)


@router.post("/admin/ml/training-jobs", status_code=202)
async def ml_create_job(
    body: CreateTrainingJobIn, db: DbSession, principal: CurrentPrincipal, clock: ClockDep
) -> TrainingJobOut:
    """N33 — mở một job `queued` và gửi runner; bản dataset chưa `ready` hay khác họ → 422."""
    return await service.create_job(
        db,
        family=body.family,
        dataset_version_id=body.dataset_version_id,
        base_model=body.base_model,
        epochs=body.epochs,
        principal=principal,
        clock=clock,
    )


@router.get("/admin/ml/training-jobs/{job_id}")
async def ml_read_job(job_id: str, db: DbSession) -> TrainingJobOut:
    """N34 — một job; không có hay id sai mẫu → 404 `resource:"trainingJob"`."""
    return await service.read_job(db, job_id=job_id)


@router.post("/admin/ml/training-jobs/{job_id}/cancel")
async def ml_cancel_job(
    job_id: str, body: CancelTrainingJobIn, db: DbSession, principal: CurrentPrincipal, clock: ClockDep
) -> TrainingJobOut:
    """N35 — `queued` → `cancelled`, `running` → `cancelling`; job đã xong → 409."""
    return await service.cancel_job(db, job_id=job_id, principal=principal, clock=clock)


@router.get("/admin/ml/training-jobs/{job_id}/metrics")
async def ml_list_job_metrics(
    job_id: str, db: DbSession, clock: ClockDep, since: Since = SINCE_MIN, limit: StreamLimit = DEFAULT_LIMIT
) -> TrainingMetricPage:
    """N36 — điểm số đo `step > since`, `step` tăng; bước cuối chờ đủ `split` mới ra."""
    return await service.list_job_metrics(db, job_id=job_id, since=since, limit=limit, clock=clock)


@router.get("/admin/ml/training-jobs/{job_id}/logs")
async def ml_list_job_logs(
    job_id: str, db: DbSession, clock: ClockDep, since: Since = SINCE_MIN, limit: StreamLimit = DEFAULT_LIMIT
) -> TrainingLogPage:
    """N37 — dòng log `seq > since`, `seq` tăng; cùng luật `nextCursor` với N36."""
    return await service.list_job_logs(db, job_id=job_id, since=since, limit=limit, clock=clock)
