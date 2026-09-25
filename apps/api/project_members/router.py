"""Hai route thành viên dự án N3, N4 (B2-02 [2], [7]); router **mỏng**, việc ở `service.py`.

Cả hai đòi `project.settings.edit` trong dự án (viewer 403, người ngoài 404, K08). Người thực
hiện lấy từ `Principal` qua `ProjectAccess` (K05). N3 trả 201 khi thêm mới và 200 khi đã là
thành viên: status đặt động trên `Response` của khung nên response idempotency lưu giữ đúng status.
"""

from typing import Annotated, Final

from fastapi import Depends
from starlette.requests import Request
from starlette.responses import Response

from apps.api.core.deps import ClockDep, DbSession, Storage
from apps.api.core.ratelimit import key_user, rate_limit
from apps.api.core.routing import protected_router
from apps.api.project_members import service
from apps.api.project_members.schemas import AddMemberBody
from apps.api.project_members.settings import get_project_members_settings
from apps.api.projects.access import ProjectAccess, require_project
from apps.api.projects.wire import UserOut

router = protected_router(tags=["members"])
ROUTERS: Final = (router,)

_add_limit: Final = rate_limit(
    "members_add",
    limit=lambda: get_project_members_settings().member_add_rate_limit,
    window_s=lambda: get_project_members_settings().member_add_rate_window_s,
    key=key_user,
    store="safe",
    on_error="closed",
)
"""Hạn mức N3 theo người thực hiện; đọc lười mỗi lượt để test C11 đặt 3 bằng biến môi trường."""

EditAccess = Annotated[ProjectAccess, Depends(require_project("project.settings.edit"))]


@router.post("/projects/{project_id}/members", status_code=201, dependencies=[Depends(_add_limit)])
async def members_add_member(
    body: AddMemberBody,
    access: EditAccess,
    request: Request,
    response: Response,
    db: DbSession,
    storage: Storage,
    clock: ClockDep,
) -> UserOut:
    """N3 — thêm thành viên theo email: 201 khi mới, 200 khi đã là thành viên."""
    out, created = await service.add_project_member(
        db,
        storage,
        project_id=access.project_id,
        project_name=access.project_name,
        actor_id=access.principal.user_id,
        email=body.email,
        clock=clock,
        app=request.app,
    )
    if not created:
        response.status_code = 200
    return out


@router.delete("/projects/{project_id}/members/{user_id}")
async def members_remove_member(
    user_id: str, access: EditAccess, db: DbSession, storage: Storage, clock: ClockDep
) -> UserOut:
    """N4 — gỡ thành viên; thân là `UserOut` của người vừa gỡ."""
    return await service.remove_project_member(
        db, storage, project_id=access.project_id, actor_id=access.principal.user_id, user_id=user_id, clock=clock
    )
