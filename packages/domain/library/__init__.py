"""Thư viện .glb (lớp miền, chỉ thư viện chuẩn): danh mục dựng bằng mã và mẫu từ tệp, dựng/đo `.glb`, ảnh PNG.

Danh mục là dữ liệu sản phẩm sinh tất định bằng mã (B2-06); tầng API/DB/storage chỉ nhập
các tên dưới đây. Không nhập `packages.storage`, `packages.db`, `apps.*` (import-linter).
"""

from packages.domain.library.catalogue import (
    CATALOGUE,
    ITEM_ID_MAX_LEN,
    ITEM_ID_RE,
    LIBRARY_GROUPS,
    CatalogueItem,
    Part,
    is_item_id,
)
from packages.domain.library.files import FILE_CATALOGUE, FileItem
from packages.domain.library.glb import GlbAsset, build_glb, measure_glb
from packages.domain.library.preview import build_preview_png

__all__ = [
    "CATALOGUE",
    "FILE_CATALOGUE",
    "ITEM_ID_MAX_LEN",
    "ITEM_ID_RE",
    "LIBRARY_GROUPS",
    "CatalogueItem",
    "FileItem",
    "GlbAsset",
    "Part",
    "build_glb",
    "build_preview_png",
    "is_item_id",
    "measure_glb",
]
