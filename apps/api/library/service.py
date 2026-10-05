"""Đọc thư viện (#14, #15): điều kiện hiển thị, thứ tự, URL ký cục bộ (B2-06 [6] "Đọc").

Mục hiển thị khi đã phát hành, chưa rút và (của hệ thống hoặc của chính người gọi); mục
`mine` của người khác vắng như không có (không lộ tồn tại). URL do `signed_url` tính cục bộ,
không `stat` (W23): CHECK `published` của bảng bảo đảm mục hiển thị luôn có số đo và khoá.
"""

from collections.abc import Sequence
from typing import Final, cast

from sqlalchemy import ColumnElement, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.library.schemas import LibraryItemOut
from apps.api.library.settings import get_library_settings
from packages.core.error_codes import NOT_FOUND
from packages.db.models.library import LibraryItemRow
from packages.domain.library import is_item_id
from packages.storage.port import ObjectStorage, SignRequest

RESOURCE: Final = "libraryItem"


def visible_to(user_id: str) -> ColumnElement[bool]:
    """Điều kiện hiển thị của một mục đối với `user_id` (dùng chung cho #14 và #15)."""
    return and_(
        LibraryItemRow.published_at.is_not(None),
        LibraryItemRow.retired_at.is_(None),
        or_(LibraryItemRow.owner_id.is_(None), LibraryItemRow.owner_id == user_id),
    )


async def _to_outs(storage: ObjectStorage, rows: Sequence[LibraryItemRow], user_id: str) -> list[LibraryItemOut]:
    """Dựng response từ các dòng đã phát hành; URL ký `attachment`, không `kind`, không `stat`.

    Mô hình và ảnh xem trước của mọi dòng ký trong **một** lượt `signed_urls` (NO-207).
    """
    requests: list[SignRequest] = []
    for row in rows:
        # CHECK `published`: mục hiển thị luôn có khoá mô hình
        requests.append(SignRequest(cast("str", row.model_key), "attachment", filename=f"{row.id}.glb"))
        if row.preview_key is not None:
            requests.append(SignRequest(row.preview_key, "attachment", filename=f"{row.id}.png"))
    signed = iter(await storage.signed_urls(requests))
    outs = []
    for row in rows:
        model = next(signed)
        preview = None if row.preview_key is None else next(signed)
        outs.append(
            LibraryItemOut.model_validate(
                {
                    "id": row.id,
                    "name": row.name,
                    "group": row.item_group,
                    "source": "mine" if row.owner_id == user_id else "catalogue",
                    "width_mm": row.width_mm,
                    "depth_mm": row.depth_mm,
                    "height_mm": row.height_mm,
                    "triangle_count": row.triangle_count,
                    "file_size_bytes": row.file_size_bytes,
                    "model_url": model.url,
                    "preview_url": None if preview is None else preview.url,
                }
            )
        )
    return outs


async def list_items(db: AsyncSession, storage: ObjectStorage, user_id: str) -> list[LibraryItemOut]:
    """#14: mục hiển thị theo `(sort_order, id)`, tối đa `LIBRARY_LIST_MAX`, một truy vấn."""
    stmt = (
        select(LibraryItemRow)
        .where(visible_to(user_id))
        .order_by(LibraryItemRow.sort_order, LibraryItemRow.id)
        .limit(get_library_settings().library_list_max)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return await _to_outs(storage, rows, user_id)


async def read_item(db: AsyncSession, storage: ObjectStorage, user_id: str, item_id: str) -> LibraryItemOut:
    """#15: một mục hiển thị; id sai mẫu → 404 không truy vấn, không hiển thị → 404."""
    if not is_item_id(item_id):
        raise NOT_FOUND.error(resource=RESOURCE)
    row = (
        await db.execute(select(LibraryItemRow).where(LibraryItemRow.id == item_id, visible_to(user_id)))
    ).scalar_one_or_none()
    if row is None:
        raise NOT_FOUND.error(resource=RESOURCE)
    return (await _to_outs(storage, [row], user_id))[0]
