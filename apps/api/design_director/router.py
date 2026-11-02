"""Route N47-N48 của AI chọn phong cách; router mỏng, nghiệp vụ ở `service.py`.

`discover_routers()` tự nạp `ROUTERS` của module này. N47 chỉ đòi là thành viên; N48 đòi
`project.settings.edit` như đổi `sceneStyle` ở N6 (viewer → 403); người ngoài → 404 (K08).
N48 `idempotency="off"` như N42: gửi lặp cùng thân tự dùng lại concept cùng `input_key`.
"""

from typing import Annotated, Final

from fastapi import Depends

from apps.api.core.deps import ClockDep, CurrentPrincipal, DbSession
from apps.api.core.routing import protected_router, route_options
from apps.api.design_director import service
from apps.api.design_director.schemas import DesignConcept, DesignConceptState, SelectDesignConceptIn
from apps.api.design_director.settings import DesignDirectorSettings, get_design_director_settings
from apps.api.projects.access import require_project

router = protected_router(tags=["design_director"])
ROUTERS: Final = (router,)

_edit_gate: Final = Depends(require_project("project.settings.edit"))
_member_gate: Final = Depends(require_project())
DirectorSettings = Annotated[DesignDirectorSettings, Depends(get_design_director_settings)]


@router.get("/projects/{project_id}/design-concept", dependencies=[_member_gate])
async def design_director_read_state(project_id: str, db: DbSession, settings: DirectorSettings) -> DesignConceptState:
    """N47 — công tắc, kiểu AI đề xuất và concept đang chọn của dự án."""
    return await service.read_state(db, project_id=project_id, settings=settings)


@router.post("/projects/{project_id}/design-concept", status_code=202, dependencies=[_edit_gate])
@route_options(idempotency="off")
async def design_director_select_concept(
    project_id: str,
    body: SelectDesignConceptIn,
    db: DbSession,
    principal: CurrentPrincipal,
    clock: ClockDep,
    settings: DirectorSettings,
) -> DesignConcept:
    """N48 — 202 với concept đã chọn (mới `queued` hoặc dùng lại cùng đầu vào); 503 tắt, 429 hết hạn mức."""
    return await service.select_concept(
        db,
        project_id=project_id,
        style_id=body.style_id,
        user_id=principal.user_id,
        clock=clock,
        settings=settings,
    )
