"""`GET /api/library` (#14) và `GET /api/library/{item_id}` (#15) — chỉ đọc (B2-06 [2], [7]).

Route bảo vệ, chỉ cần `current_principal`: khoá quyền `—` nên không gắn `require_permission`.
"""

from typing import Final

from apps.api.core.deps import CurrentPrincipal, DbSession, Storage
from apps.api.core.routing import protected_router
from apps.api.library import service
from apps.api.library.schemas import LibraryItemOut

router = protected_router(tags=["library"])
ROUTERS: Final = (router,)


@router.get("/library")
async def library_list_items(principal: CurrentPrincipal, db: DbSession, storage: Storage) -> list[LibraryItemOut]:
    """#14: danh sách cũ (mảng trần) mọi mục người gọi thấy."""
    return await service.list_items(db, storage, principal.user_id)


@router.get("/library/{item_id}")
async def library_read_item(
    item_id: str, principal: CurrentPrincipal, db: DbSession, storage: Storage
) -> LibraryItemOut:
    """#15: một mục; không thấy hay không hiển thị → 404 `libraryItem`."""
    return await service.read_item(db, storage, principal.user_id, item_id)
