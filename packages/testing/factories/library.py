"""Factory mục thư viện .glb cho test (B2-06), theo mẫu `packages/testing/factories/floors.py`.

Ghi thẳng `library_items`; mục `published` có object **thật** trong `storage` (GLB và PNG dựng
bằng `build_glb`/`build_preview_png` của một `CatalogueItem` tổng hợp một khối) và số đo, khoá,
`sha256` lấy từ chính chúng, đúng như lịch phát hành sẽ ghi. Có `commit`: route đọc bằng
session khác nên chỉ `flush` thì không thấy.
"""

from hashlib import sha256
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.clock import SystemClock
from packages.core.text import nfc
from packages.db.models.auth import User
from packages.db.models.library import LibraryItemRow
from packages.domain.library import CatalogueItem, Part, build_glb, build_preview_png
from packages.storage.keys import library_object
from packages.storage.port import ObjectStorage

_BOX: Final = Part(-300, 0, -300, 600, 500, 600, (160, 112, 72))


async def make_library_item(
    db: AsyncSession,
    storage: ObjectStorage,
    *,
    id: str,
    owner: User | None = None,
    group: str = "table",
    sort_order: int = 0,
    preview: bool = True,
    published: bool = True,
    retired: bool = False,
) -> LibraryItemRow:
    """Một mục đã `commit`; `published` → object thật trong `storage`, `preview=False` → không ảnh."""
    row = LibraryItemRow(id=id, name=nfc(f"Mẫu {id}"), item_group=group, sort_order=sort_order)
    row.owner_id = None if owner is None else owner.id
    now = SystemClock().now()
    if published:
        item = CatalogueItem(id, row.name, group, (_BOX,))
        glb = build_glb(item)
        row.model_key = library_object(id, "model.glb")
        await storage.put(row.model_key, glb.data, content_type="model/gltf-binary", max_bytes=glb.size_bytes)
        row.width_mm, row.depth_mm, row.height_mm = glb.width_mm, glb.depth_mm, glb.height_mm
        row.triangle_count, row.file_size_bytes, row.model_sha256 = glb.triangle_count, glb.size_bytes, glb.sha256
        row.published_at = row.verified_at = now
        if preview:
            png = build_preview_png(item)
            row.preview_key = library_object(id, "preview.png")
            await storage.put(row.preview_key, png, content_type="image/png", max_bytes=len(png))
            row.preview_sha256 = sha256(png).hexdigest()
    if retired:
        row.retired_at = now
    db.add(row)
    await db.commit()
    return row
