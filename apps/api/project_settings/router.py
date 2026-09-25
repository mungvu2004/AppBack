"""Hai route cài đặt dự án N5, N6 (B2-02 [2], [7]); router **mỏng**, việc ở `service.py`.

N5 cho mọi thành viên; N6 đòi `project.settings.edit` (admin, engineer) và là ghi có version: thiếu
`baseVersion` bị khung chặn 428 trước Pydantic. Route GV không dùng bảng idempotency — header
`Idempotency-Key` FE tự gắn bị bỏ qua.
"""

from typing import Annotated, Final

from fastapi import Depends

from apps.api.core.deps import ClockDep, DbSession
from apps.api.core.routing import protected_router, route_options
from apps.api.project_settings import service
from apps.api.project_settings.schemas import ProjectSettingsOut, ProjectSettingsWriteIn
from apps.api.projects.access import ProjectAccess, require_project

router = protected_router(tags=["project_settings"])
ROUTERS: Final = (router,)


@router.get("/projects/{project_id}/settings")
async def settings_read_settings(
    access: Annotated[ProjectAccess, Depends(require_project())], db: DbSession
) -> ProjectSettingsOut:
    """N5 — cài đặt dự án; chưa ghi lần nào thì trả mặc định `revision 0`."""
    return await service.get_settings(db, access.project_id)


@router.put("/projects/{project_id}/settings")
@route_options(versioned=True)
async def settings_replace_settings(
    body: ProjectSettingsWriteIn,
    access: Annotated[ProjectAccess, Depends(require_project("project.settings.edit"))],
    db: DbSession,
    clock: ClockDep,
) -> ProjectSettingsOut:
    """N6 — thay cài đặt có version; base cũ → 409 `remoteChanges: []`, lượt lặp của chính mình → 200."""
    return await service.replace_settings(db, access, base_version=body.base_version, body=body.body, clock=clock)
