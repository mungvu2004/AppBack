"""Năm route phiên bản theo tầng: #36, N17-N20 (B3-04 [2], [7]); router **mỏng**, việc ở `service.py`.

`require_project(...)` là tham số/`dependencies=` nên chạy **trước** guard 428 và Pydantic: người
ngoài dự án nhận 404 `resource:"project"` (K08), viewer nhận 403 ở N19/N20. N19 khai
`versioned=True` (guard 428 khi thiếu `baseVersion`, không dùng bảng idempotency); N20 giữ
idempotency `auto`. Handler **không** `commit` — `AppRoute` commit khi handler xong.

N19 trả 201 cho bản mới và 200 cho lượt gửi lại đã thành công (C09b): `responses={200: …}` để
OpenAPI nói đúng hai đường ấy.
"""

from typing import Annotated, Final

from fastapi import Depends, Query
from starlette.responses import Response

from apps.api.core.deps import ClockDep, DbSession
from apps.api.core.pagination import CursorPage, PageParams, page_params
from apps.api.core.routing import protected_router, route_options
from apps.api.projects.access import ProjectAccess, require_project
from apps.api.versions import service
from apps.api.versions.schemas import (
    FloorVersionSnapshotOut,
    FloorVersionSummaryOut,
    VersionLabelIn,
    VersionOut,
    VersionRestoreIn,
)

router = protected_router(tags=["versions"])
ROUTERS: Final = (router,)

_Member = Annotated[ProjectAccess, Depends(require_project())]
_Editor = Annotated[ProjectAccess, Depends(require_project("layer.edit"))]


@router.get("/projects/{project_id}/versions")
async def versions_list_versions(
    floor_id: Annotated[str, Query(alias="floorId", min_length=1)],
    access: _Member,
    db: DbSession,
    page: Annotated[PageParams, Depends(page_params(max_limit=200))],
) -> CursorPage[FloorVersionSummaryOut]:
    """N17 — lịch sử phiên bản một tầng, `sequence` giảm dần."""
    return await service.list_versions(db, access, floor_id=floor_id, page=page)


@router.get("/projects/{project_id}/versions/{version_id}")
async def versions_read_version(version_id: str, access: _Member, db: DbSession) -> VersionOut:
    """#36 — một phiên bản dưới dạng `Version` cũ của FE."""
    return await service.read_version(db, access, version_id)


@router.get("/projects/{project_id}/versions/{version_id}/snapshot")
async def versions_read_snapshot(
    version_id: str, floor_id: Annotated[str, Query(alias="floorId", min_length=1)], access: _Member, db: DbSession
) -> FloorVersionSnapshotOut:
    """N18 — nội dung ảnh chụp (`layer`, `dimensions`) của một phiên bản."""
    return await service.read_snapshot(db, access, version_id=version_id, floor_id=floor_id)


@router.post(
    "/projects/{project_id}/versions/{version_id}/restore",
    status_code=201,
    responses={200: {"model": FloorVersionSummaryOut}},
)
@route_options(versioned=True)
async def versions_restore_version(
    version_id: str, body: VersionRestoreIn, response: Response, access: _Editor, db: DbSession, clock: ClockDep
) -> FloorVersionSummaryOut:
    """N19 — phục hồi tầng về một phiên bản: 201 bản "sau", 200 khi là lượt gửi lại (C09b)."""
    outcome = await service.restore_version(
        db,
        access,
        version_id=version_id,
        floor_id=body.body.floor_id,
        base_version=body.base_version,
        clock=clock,
    )
    if outcome.replayed:
        response.status_code = 200
    return service.summary_out(outcome.row)


@router.patch("/projects/{project_id}/versions/{version_id}/label")
async def versions_label_version(
    version_id: str, body: VersionLabelIn, access: _Editor, db: DbSession, clock: ClockDep
) -> FloorVersionSummaryOut:
    """N20 — đặt hoặc gỡ nhãn; không sinh phiên bản mới."""
    row = await service.label_version(db, access, version_id=version_id, label=body.label, clock=clock)
    return service.summary_out(row)
