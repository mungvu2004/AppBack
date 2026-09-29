"""Bốn route dataset ML N28-N31 (B6-02 [2], [7]); router **mỏng**.

Cả bốn đòi `require_admin` (khoá `admin`), khai một lần ở router: `engineer`,
`viewer` → 403. `idempotency="auto"` (mặc định của khung) cho N29, N31: cả hai
ghi và có thân JSON nhỏ, nên bảng idempotency chung ghi lại được lượt lặp (K18).
"""

from typing import Annotated, Final

from fastapi import Depends

from apps.api.access.deps import require_admin
from apps.api.admin_ml_datasets import service
from apps.api.admin_ml_datasets.schemas import (
    BuildDatasetVersionIn,
    CreateDatasetIn,
    DatasetOut,
    DatasetPage,
    DatasetVersionOut,
    DatasetVersionPage,
)
from apps.api.admin_ml_datasets.settings import MlDatasetsSettings, get_ml_datasets_settings
from apps.api.core.deps import ClockDep, CurrentPrincipal, DbSession
from apps.api.core.pagination import PageParams, page_params
from apps.api.core.routing import protected_router

router = protected_router(tags=["admin_ml_datasets"], dependencies=[Depends(require_admin)])
ROUTERS: Final = (router,)

MlSettings = Annotated[MlDatasetsSettings, Depends(get_ml_datasets_settings)]


@router.get("/admin/ml/datasets")
async def ml_list_datasets(
    db: DbSession,
    page: Annotated[PageParams, Depends(page_params())],
    family: str | None = None,
) -> DatasetPage:
    """N28 — datasets, mới nhất trước; `family` lạ → 422 `field:"family"`."""
    return await service.list_datasets(db, family=family, page=page)


@router.post("/admin/ml/datasets", status_code=201)
async def ml_create_dataset(
    body: CreateDatasetIn, db: DbSession, principal: CurrentPrincipal, clock: ClockDep
) -> DatasetOut:
    """N29 — đặt tên một dataset mới; tên đã dùng (không phân biệt hoa thường) → 409."""
    return await service.create_dataset(db, name=body.name, family=body.family, principal=principal, clock=clock)


@router.get("/admin/ml/datasets/{dataset_id}/versions")
async def ml_list_dataset_versions(
    dataset_id: str, db: DbSession, page: Annotated[PageParams, Depends(page_params())]
) -> DatasetVersionPage:
    """N30 — phiên bản của một dataset, `sequence` giảm dần; dataset không có → 404."""
    return await service.list_dataset_versions(db, dataset_id=dataset_id, page=page)


@router.post("/admin/ml/datasets/{dataset_id}/versions", status_code=202)
async def ml_build_dataset_version(
    dataset_id: str,
    body: BuildDatasetVersionIn,
    db: DbSession,
    principal: CurrentPrincipal,
    clock: ClockDep,
    settings: MlSettings,
) -> DatasetVersionOut:
    """N31 — mở một phiên bản `building`, gửi task dựng mẫu; đã có bản đang dựng → 409."""
    return await service.build_dataset_version(
        db,
        dataset_id=dataset_id,
        project_ids=body.project_ids,
        principal=principal,
        clock=clock,
        settings=settings,
    )
