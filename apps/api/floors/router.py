"""5 route tầng (B2-03 [2], [7]).

Router **mỏng**, theo mẫu `apps/api/projects/router.py`: cổng quyền đặt ở `dependencies=`
khi kết quả không cần cho nghiệp vụ (#10, #12, #34 đã có `project_id` trên đường); #11 và
#13 phải **bind** kết quả của `require_project` vì `project_id` chỉ resolver mới suy ra
được (đường phẳng của tầng, B2-03 [5]). `request.app` đi thẳng xuống `service` để cổng
`floor.drawings` resolve theo app của request (`extensions.override` của test).
"""

from typing import Annotated, Final

from fastapi import Depends
from starlette.requests import Request

from apps.api.core.deps import ClockDep, CurrentPrincipal, DbSession
from apps.api.core.routing import protected_router
from apps.api.floors import service
from apps.api.floors.resolvers import project_of_floor, project_of_floor_list
from apps.api.floors.schemas import FloorCreateIn, FloorPatchIn, FloorReorderIn
from apps.api.projects.access import ProjectAccess, require_project
from apps.api.projects.wire import FloorOut

router = protected_router(tags=["floors"])
ROUTERS: Final = (router,)

FloorAccess = Annotated[ProjectAccess, Depends(require_project("layer.edit", resolver=project_of_floor))]
ListAccess = Annotated[ProjectAccess, Depends(require_project("layer.edit", resolver=project_of_floor_list))]


@router.post("/projects/{project_id}/floors", status_code=201, dependencies=[Depends(require_project("layer.edit"))])
async def floors_create_floor(
    project_id: str, body: FloorCreateIn, request: Request, db: DbSession, principal: CurrentPrincipal, clock: ClockDep
) -> FloorOut:
    """#10 — tạo tầng (201), hoặc khôi phục tầng xoá mềm còn trong cửa sổ."""
    return await service.create_floor(db, project_id, body, principal, clock, app=request.app)


@router.delete("/floors/{floor_id}")
async def floors_delete_floor(
    floor_id: str, request: Request, db: DbSession, principal: CurrentPrincipal, clock: ClockDep, access: FloorAccess
) -> FloorOut:
    """#11 — xoá mềm; thân là ảnh chụp ngay trước khi xoá."""
    return await service.delete_floor(db, access.project_id, floor_id, principal, clock, app=request.app)


@router.get("/projects/{project_id}/floors", dependencies=[Depends(require_project())])
async def floors_list_floors(project_id: str, request: Request, db: DbSession) -> list[FloorOut]:
    """#12 — mọi tầng chưa xoá của dự án, tối đa `FLOORS_MAX`."""
    return await service.list_floors(db, project_id, app=request.app)


@router.patch("/floors/reorder")
async def floors_reorder_floors(
    body: FloorReorderIn,
    request: Request,
    db: DbSession,
    principal: CurrentPrincipal,
    clock: ClockDep,
    access: ListAccess,
) -> list[FloorOut]:
    """#13 — sắp xếp lại theo `floorIds`; resolver đã kiểm hình dạng (một nguồn luật), service khoá lại và kiểm tập."""
    return await service.reorder_floors(
        db, access.project_id, access.project_name, body.floor_ids, principal, clock, app=request.app
    )


@router.patch("/projects/{project_id}/floors/{floor_id}/spatial", dependencies=[Depends(require_project("layer.edit"))])
async def floors_patch_spatial_floor(
    project_id: str,
    floor_id: str,
    body: FloorPatchIn,
    request: Request,
    db: DbSession,
    principal: CurrentPrincipal,
    clock: ClockDep,
) -> FloorOut:
    """#34 — sửa tầng (last-write-wins); `id` khác đường → 422 `PATH_BODY_MISMATCH`."""
    return await service.patch_floor(db, project_id, floor_id, body, principal, clock, app=request.app)
