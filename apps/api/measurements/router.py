"""#16 `GET`, #17 `POST`, #18 `DELETE` phép đo của dự án (B2-07 [2], [7]).

`project_id` nằm trên đường nên cổng quyền đi qua `dependencies=`/`EditAccess`: người ngoài
dự án → 404 `project` (K08), `viewer` không có `layer.edit` → 403.
"""

from typing import Annotated, Final

from fastapi import Depends
from starlette.responses import Response

from apps.api.core.deps import ClockDep, DbSession
from apps.api.core.routing import protected_router
from apps.api.measurements import service
from apps.api.measurements.schemas import MeasurementRecord, MeasurementRecordIn
from apps.api.projects.access import ProjectAccess, require_project

router = protected_router(tags=["measurements"])
ROUTERS: Final = (router,)

EditAccess = Annotated[ProjectAccess, Depends(require_project("layer.edit"))]


@router.get("/projects/{project_id}/measurements", dependencies=[Depends(require_project())])
async def measurements_list_records(project_id: str, db: DbSession) -> list[MeasurementRecord]:
    """#16: danh sách cũ (mảng trần), thứ tự số của id."""
    return await service.list_records(db, project_id)


@router.post("/projects/{project_id}/measurements", status_code=201)
async def measurements_create_record(
    body: MeasurementRecordIn, response: Response, access: EditAccess, db: DbSession, clock: ClockDep
) -> MeasurementRecord:
    """#17: 201 khi tạo mới, 200 khi gửi lại đúng bản đã lưu (hoàn tác xoá gửi lại nguyên bản ghi)."""
    record, created = await service.create_record(db, access.project_id, body, access.principal, clock)
    if not created:
        response.status_code = 200
    return record


@router.delete("/projects/{project_id}/measurements/{measurement_id}", status_code=204)
async def measurements_delete_record(measurement_id: str, access: EditAccess, db: DbSession, clock: ClockDep) -> None:
    """#18: xoá cứng, 204 thân rỗng."""
    await service.delete_record(db, access.project_id, measurement_id, clock)
