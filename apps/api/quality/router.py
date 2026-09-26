"""Route của API chất lượng ảnh: #30 đọc, #31 áp bốn góc, #32 nắn nghiêng (B2-05b [2], [7]).

Router **mỏng**: quyền ở `dependencies=`, nghiệp vụ ở `service.py`/`assessments.py`. #30 chỉ
đòi là thành viên; #31, #32 đòi `floor.upload` (viewer → 403) và `idempotency="auto"` vì có
tác dụng ngoài giao dịch (lượt pipeline) mà FE có thể gửi lại — FE thường không gửi khoá,
nên service tự bảo đảm lượt lặp không nhân đôi việc.
"""

from typing import Final

from fastapi import Depends

from apps.api.core.deps import ClockDep, DbSession, Storage
from apps.api.core.routing import protected_router, route_options
from apps.api.floors.lookup import get_floor
from apps.api.projects.access import require_project
from apps.api.quality import service
from apps.api.quality.assessments import read_view
from apps.api.quality.schemas import QualityAssessmentOut, SetCornersIn, StraightenIn
from packages.core.error_codes import NOT_FOUND

router = protected_router(tags=["quality"])
ROUTERS: Final = (router,)

_upload_gate: Final = Depends(require_project("floor.upload"))
_member_gate: Final = Depends(require_project())
_FLOOR: Final = "/projects/{project_id}/floors/{floor_id}/quality"


@router.get(_FLOOR, dependencies=[_member_gate])
async def quality_read_assessment(
    project_id: str, floor_id: str, db: DbSession, storage: Storage
) -> QualityAssessmentOut:
    """#30 — kết quả đo của mọi tầng có bản vẽ; tầng hỏi không có → 404 `floor`."""
    if await get_floor(db, project_id=project_id, level_id=floor_id) is None:
        raise NOT_FOUND.error(resource="floor")
    return await read_view(db, storage, project_id=project_id, level_id=floor_id)


@router.post(f"{_FLOOR}/corners", dependencies=[_upload_gate])
@route_options(idempotency="auto")
async def quality_set_corners(
    project_id: str, floor_id: str, body: SetCornersIn, db: DbSession, storage: Storage, clock: ClockDep
) -> QualityAssessmentOut:
    """#31 — áp bốn góc lên trang chưa nắn, đồng bộ; xong xếp hàng lại pipeline."""
    return await service.set_corners(db, storage, project_id=project_id, level_id=floor_id, body=body, clock=clock)


@router.post(f"{_FLOOR}/straighten", dependencies=[_upload_gate])
@route_options(idempotency="auto")
async def quality_straighten(
    project_id: str, floor_id: str, body: StraightenIn, db: DbSession, storage: Storage, clock: ClockDep
) -> QualityAssessmentOut:
    """#32 — nắn nghiêng trang đang dùng, đồng bộ; xong xếp hàng lại pipeline."""
    del body  # thân `{}` strict: pydantic đã chặn khoá lạ
    return await service.straighten(db, storage, project_id=project_id, level_id=floor_id, clock=clock)
