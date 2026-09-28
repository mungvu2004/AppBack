"""Hai route cấu hình luật N21, N22 (B3-05 [2], [7]); router **mỏng**, việc ở `service.py`.

N21 cho mọi thành viên; N22 đòi `ruleset.edit` (chỉ `admin`) và là ghi có version: thiếu `baseVersion` bị khung
chặn 428 trước Pydantic, quyền kiểm trước 428. Route GV không dùng bảng idempotency.
"""

from typing import Annotated, Final

from fastapi import Depends

from apps.api.core.deps import ClockDep, DbSession
from apps.api.core.routing import protected_router, route_options
from apps.api.projects.access import ProjectAccess, require_project
from apps.api.rules import service
from apps.api.rules.schemas import ProjectRuleConfigOut, RuleConfigWriteIn

router = protected_router(tags=["rules"])
ROUTERS: Final = (router,)


@router.get("/projects/{project_id}/rule-config")
async def rules_read_config(
    access: Annotated[ProjectAccess, Depends(require_project())], db: DbSession
) -> ProjectRuleConfigOut:
    """N21 — cấu hình luật của dự án; chưa lưu thì `{revision: 0, overrides: {}}`."""
    return await service.get_config(db, access.project_id)


@router.put("/projects/{project_id}/rule-config")
@route_options(versioned=True)
async def rules_replace_config(
    body: RuleConfigWriteIn,
    access: Annotated[ProjectAccess, Depends(require_project("ruleset.edit"))],
    db: DbSession,
    clock: ClockDep,
) -> ProjectRuleConfigOut:
    """N22 — thay cấu hình luật có version; base cũ → 409 `remoteChanges: []`, lượt lặp của chính mình → 200."""
    return await service.replace_config(db, access, base_version=body.base_version, body=body.body, clock=clock)
