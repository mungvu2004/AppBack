"""Seed danh tính danh mục thư viện .glb: `id, name, item_group, sort_order` (B2-06 [5]).

Chỉ ghi danh tính. Số đo, khoá object, `sha256` và mốc phát hành do lịch `publish_library_assets`
(hay CLI) điền khi object có thật, nên seed **không** dựng storage: bước 6 của verify chạy seed
không có storage. `sort_order` = chỉ số trong danh mục x 10 (`CatalogueItem` không có
`sort_order`; bước 10 chừa chỗ chèn mục mới giữa hai mục mà không đánh số lại).

Idempotent: `ON CONFLICT (id) DO UPDATE … WHERE` chỉ chạm dòng có giá trị khác. Mục của hệ
thống (`owner_id IS NULL`) không còn trong danh mục → `retired_at = now()`; quay lại → `NULL`.
"""

from typing import Final

from sqlalchemy import func, or_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.library import LibraryItemRow
from packages.domain.library import CATALOGUE, CatalogueItem

ORDER: Final = 50
ENVS: Final = frozenset({"dev", "test", "ci", "staging", "production"})
SORT_STEP: Final = 10


async def sync_catalogue(session: AsyncSession, catalogue: tuple[CatalogueItem, ...]) -> None:
    """Đồng bộ danh tính của `catalogue` vào `library_items` rồi rút mục vắng; chạy lại không đổi gì."""
    if not catalogue:
        return
    rows = [
        {"id": item.id, "name": item.name, "item_group": item.group, "sort_order": index * SORT_STEP}
        for index, item in enumerate(catalogue)
    ]
    stmt = insert(LibraryItemRow).values(rows)
    excluded = stmt.excluded
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=[LibraryItemRow.id],
            set_={
                "name": excluded.name,
                "item_group": excluded.item_group,
                "sort_order": excluded.sort_order,
                "retired_at": None,
                "updated_at": func.now(),
            },
            where=or_(
                LibraryItemRow.name.is_distinct_from(excluded.name),
                LibraryItemRow.item_group.is_distinct_from(excluded.item_group),
                LibraryItemRow.sort_order.is_distinct_from(excluded.sort_order),
                LibraryItemRow.retired_at.is_not(None),
            ),
        )
    )
    await session.execute(
        update(LibraryItemRow)
        .where(
            LibraryItemRow.owner_id.is_(None),
            LibraryItemRow.retired_at.is_(None),
            LibraryItemRow.id.not_in([item.id for item in catalogue]),
        )
        .values(retired_at=func.now(), updated_at=func.now())
    )


async def seed(session: AsyncSession) -> None:
    """Seed danh mục dựng sẵn (`CATALOGUE`); test tiêm danh mục khác qua `sync_catalogue`."""
    await sync_catalogue(session, CATALOGUE)
