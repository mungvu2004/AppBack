"""#28 `GET` và #29 `POST` khuôn thuộc tính của dự án (B2-07 [2], [7])."""

from typing import Annotated, Final

from fastapi import Depends

from apps.api.core.deps import ClockDep, DbSession
from apps.api.core.routing import protected_router
from apps.api.projects.access import ProjectAccess, require_project
from apps.api.templates import service
from apps.api.templates.schemas import PropertyTemplate, PropertyTemplateDraft

router = protected_router(tags=["propertyTemplates"])
ROUTERS: Final = (router,)

EditAccess = Annotated[ProjectAccess, Depends(require_project("layer.edit"))]


@router.get("/projects/{project_id}/property-templates", dependencies=[Depends(require_project())])
async def templates_list_templates(project_id: str, db: DbSession) -> list[PropertyTemplate]:
    """#28: danh sách cũ (mảng trần), cũ nhất trước."""
    return await service.list_templates(db, project_id)


@router.post("/projects/{project_id}/property-templates", status_code=201)
async def templates_create_template(
    body: PropertyTemplateDraft, access: EditAccess, db: DbSession, clock: ClockDep
) -> PropertyTemplate:
    """#29: 201; hai lượt bấm là hai khuôn."""
    return await service.create_template(db, access.project_id, body, access.principal, clock)
