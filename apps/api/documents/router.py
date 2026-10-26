"""Route tài liệu chưa gán tầng: N39 `documents_init_upload` (PHASE-1-CONTRACT §4.1).

Router mỏng như `apps/api/drawings/router.py`: quyền `floor.upload` trước hạn mức, nghiệp vụ ở
`service.py`. Hạn mức dùng chung trần của #5 (`DRAWINGS_INIT_RATE_*`) nhưng khoá riêng.
"""

from typing import Final

from fastapi import Depends

from apps.api.core.deps import ClockDep, CurrentPrincipal, DbSession
from apps.api.core.ratelimit import key_user, rate_limit
from apps.api.core.routing import protected_router, route_options
from apps.api.documents import service
from apps.api.documents.schemas import DocumentInitBody, DocumentInitOut
from apps.api.drawings.settings import get_drawings_settings
from apps.api.projects.access import require_project

router = protected_router(tags=["documents"])
ROUTERS: Final = (router,)

_upload_gate: Final = Depends(require_project("floor.upload"))

_init_limit: Final = rate_limit(
    "documents_init",
    limit=lambda: get_drawings_settings().drawings_init_rate_limit,
    window_s=lambda: get_drawings_settings().drawings_init_rate_window_s,
    key=key_user,
    store="cache",
    on_error="open",
)


@router.post(
    "/projects/{project_id}/documents/uploads",
    status_code=201,
    dependencies=[_upload_gate, Depends(_init_limit)],
)
@route_options(idempotency="auto")
async def documents_init_upload(
    project_id: str, body: DocumentInitBody, db: DbSession, principal: CurrentPrincipal, clock: ClockDep
) -> DocumentInitOut:
    """N39 — mở một tài liệu và lượt tải tệp gốc của nó; không cần tầng."""
    wire = await service.init_document_upload(db, project_id=project_id, body=body, principal=principal, clock=clock)
    return DocumentInitOut.model_validate(wire)
