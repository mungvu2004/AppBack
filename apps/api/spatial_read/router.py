"""Ba route đọc lớp không gian: #33, N15, N16 (B3-02 [2], [7]).

Router **mỏng** như `apps/api/floors/router.py`: `require_project()` đặt ở `dependencies=`
và vì thế chạy **trước** mọi câu tìm tầng (K08) — người ngoài dự án nhận 404
`resource:"project"` mà không biết tầng nào có thật. Quyền là "thành viên bất kỳ": viewer
đọc được.

**Không route nào ghi** ([6]). Tầng chưa có dòng `floor_documents` dùng `empty_document`;
`ensure_document` là việc của người ghi (B3-03).

`request.app` đi thẳng xuống `floor_outs` và `load_pages` để `extensions.override` của test
áp đúng app của request thay vì bảng dò toàn cục.
"""

from typing import Final

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from apps.api.core.deps import DbSession
from apps.api.core.routing import protected_router
from apps.api.floors.lookup import floor_outs, get_floor
from apps.api.projects.access import require_project
from apps.api.projects.wire import FloorOut
from apps.api.spatial_read.assemble import effective_scale_source, level_out, scale_status
from apps.api.spatial_read.documents import empty_document, load_document
from apps.api.spatial_read.graph import spatial_graph
from apps.api.spatial_read.pages import load_pages
from apps.api.spatial_read.wire import FloorLayerDocumentOut, SpatialGraphDocumentOut, dimensions_out, layer_out
from packages.core.error_codes import NOT_FOUND
from packages.db.models.floors import FloorRow

router = protected_router(tags=["spatial"])
ROUTERS: Final = (router,)


async def _floor_or_404(db: AsyncSession, project_id: str, floor_id: str) -> FloorRow:
    """Tầng chưa xoá của dự án, hay 404 `resource:"floor"` — một luật cho cả #33 và N16."""
    floor = await get_floor(db, project_id=project_id, level_id=floor_id)
    if floor is None:
        raise NOT_FOUND.error(resource="floor")
    return floor


async def _floor_out_or_404(db: AsyncSession, project_id: str, floor_pk: int, *, app: object) -> FloorOut:
    """`FloorOut` của một tầng vừa tìm thấy; rỗng nghĩa là tầng bị xoá **giữa** hai câu lệnh.

    Trả 404 thay vì `IndexError`: một lượt xoá chen vào giữa hai truy vấn là chuyện bình
    thường của đọc không khoá, và câu trả lời đúng cho nó là "tầng không còn".
    """
    outs = await floor_outs(db, project_id=project_id, floor_pks=[floor_pk], app=app)
    if not outs:
        raise NOT_FOUND.error(resource="floor")
    return outs[0]


@router.get("/projects/{project_id}/floors/{floor_id}/spatial", dependencies=[Depends(require_project())])
async def spatial_read_floor(project_id: str, floor_id: str, request: Request, db: DbSession) -> FloorOut:
    """#33 — siêu dữ liệu một tầng, đúng `Floor` mà #12 trả (cùng đường `floor_outs`)."""
    floor = await _floor_or_404(db, project_id, floor_id)
    return await _floor_out_or_404(db, project_id, floor.pk, app=request.app)


@router.get("/projects/{project_id}/spatial", dependencies=[Depends(require_project())])
async def spatial_read_graph(project_id: str, request: Request, db: DbSession) -> SpatialGraphDocumentOut:
    """N15 — cả đồ thị của dự án kèm `revision` từng tầng; dự án chưa có tầng → danh sách rỗng."""
    return await spatial_graph(db, project_id, app=request.app)


@router.get("/projects/{project_id}/floors/{floor_id}/spatial/layer", dependencies=[Depends(require_project())])
async def spatial_read_layer(project_id: str, floor_id: str, request: Request, db: DbSession) -> FloorLayerDocumentOut:
    """N16 — lớp của một tầng: `revision`, `level`, `scaleStatus`, bốn danh sách, trục, kích thước."""
    floor = await _floor_or_404(db, project_id, floor_id)
    stored = await load_document(db, floor.pk)
    document = empty_document(floor.pk) if stored is None else stored
    page_key = (await load_pages(db, [floor.pk], app=request.app)).get(floor.pk)
    out = await _floor_out_or_404(db, project_id, floor.pk, app=request.app)
    return FloorLayerDocumentOut(
        revision=document.revision,
        level=level_out(out, document, page_key),
        scale_status=scale_status(effective_scale_source(document, page_key)),
        layer=layer_out(document.layer),
        axes=[],
        dimensions=dimensions_out(document.dimensions),
    )
