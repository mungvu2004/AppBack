"""Năm route quản trị registry model ML N23-N27 (B6-01 [2], [7]); router **mỏng**.

Cả năm đòi `require_admin` (khoá `admin`), khai một lần ở router: `engineer`, `viewer` → 403.

- N24 là ghi có version (`versioned=True`): thiếu `baseVersion` bị khung chặn 428 trước Pydantic,
  và route GV không dùng bảng idempotency.
- N26 nhận multipart tới 512 MiB nên buộc `idempotency="off"` (`routing.py:78`), và handler
  nhận `Request` thô để `upload.py` đọc `request.stream()` — không `UploadFile`, không `Form`
  (chúng gom cả thân vào RAM hay đĩa tạm, K36).
"""

from typing import Annotated, Final

from fastapi import Depends
from starlette.requests import Request

from apps.api.access.deps import require_admin
from apps.api.admin_ml_registry import service, upload
from apps.api.admin_ml_registry.schemas import (
    ModelFamilyOut,
    ModelFamilyPage,
    ModelVersionOut,
    ModelVersionPage,
    SetActiveModelVersionIn,
)
from apps.api.admin_ml_registry.settings import UPLOAD_BODY_LIMIT, MlRegistrySettings, get_ml_registry_settings
from apps.api.core.deps import ClockDep, CurrentPrincipal, DbSession, Storage
from apps.api.core.pagination import PageParams, page_params
from apps.api.core.routing import protected_router, route_options

router = protected_router(tags=["admin_ml_registry"], dependencies=[Depends(require_admin)])
ROUTERS: Final = (router,)

MlSettings = Annotated[MlRegistrySettings, Depends(get_ml_registry_settings)]
VERSION_LIST_MAX_LIMIT: Final = 200


@router.get("/admin/ml/model-families")
async def ml_list_families(db: DbSession) -> ModelFamilyPage:
    """N23 — đủ ba họ và bản đang kích hoạt của từng họ; không bao giờ có `nextCursor`."""
    return await service.list_families(db)


@router.put("/admin/ml/model-families/{family}/active")
@route_options(versioned=True)
async def ml_activate_version(
    family: str,
    body: SetActiveModelVersionIn,
    db: DbSession,
    principal: CurrentPrincipal,
    clock: ClockDep,
) -> ModelFamilyOut:
    """N24 — kích hoạt một bản cho họ, hay `versionId: null` để quay về đường cổ điển."""
    return await service.set_active_version(
        db,
        family=family,
        base_version=body.base_version,
        version_id=body.body.version_id,
        principal=principal,
        clock=clock,
    )


@router.get("/admin/ml/model-versions")
async def ml_list_versions(
    db: DbSession,
    page: Annotated[PageParams, Depends(page_params(max_limit=VERSION_LIST_MAX_LIMIT))],
    family: str | None = None,
) -> ModelVersionPage:
    """N25 — các bản, mới nhất trước; `family` lạ → 422 `field:"family"`."""
    return await service.list_versions(db, family=family, page=page)


@router.post("/admin/ml/model-versions", status_code=201)
@route_options(body_limit=UPLOAD_BODY_LIMIT, idempotency="off")
async def ml_upload_version(
    request: Request,
    db: DbSession,
    storage: Storage,
    principal: CurrentPrincipal,
    clock: ClockDep,
    settings: MlSettings,
) -> ModelVersionOut:
    """N26 — nhận `metadata` rồi `weights` theo luồng; 201 với bản `pending` vừa ghi."""
    return await upload.upload_version(
        request, db=db, storage=storage, principal=principal, clock=clock, settings=settings
    )


@router.get("/admin/ml/model-versions/{model_version_id}")
async def ml_read_version(model_version_id: str, db: DbSession) -> ModelVersionOut:
    """N27 — một bản; id sai mẫu hay không có → 404 `modelVersion`."""
    return await service.read_version(db, version_id=model_version_id)
