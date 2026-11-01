"""Phát hành object của thư viện lên storage (B2-06 [6] "Phát hành object"; lõi của lịch và CLI).

Không nhập `fastapi`, `jwt`, `argon2`: `jobs.py` (worker) và `cli.py` dùng lại lõi này.
K36: session DB chỉ mở ngắn để đọc rồi **đóng** trước khi gọi storage, và mở lại ngắn để
ghi; không có kết nối DB nào bị giữ trong lúc `stat`/`put`. K22: dòng chỉ được ghi
`published_at` sau khi cả hai object đã `put` và `stat` lại khớp `sha256` và `kind`.
Mục lệch hay storage hỏng chỉ làm hỏng mục đó; lượt sau thử lại.
"""

import hashlib
import logging
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Final

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.library.settings import get_library_settings
from packages.core.clock import Clock
from packages.core.error_codes import DEPENDENCY_UNAVAILABLE
from packages.core.errors import AppError
from packages.db.engine import session_scope
from packages.db.models.library import LibraryItemRow
from packages.domain.library import (
    CATALOGUE,
    FILE_CATALOGUE,
    CatalogueItem,
    FileItem,
    GlbAsset,
    build_glb,
    build_preview_png,
    measure_glb,
)
from packages.storage.keys import library_object
from packages.storage.port import ObjectStorage

_log: Final = logging.getLogger(__name__)

BATCH: Final = 100
MODEL_NAME: Final = "model.glb"
PREVIEW_NAME: Final = "preview.png"
GLB_TYPE: Final = "model/gltf-binary"
PNG_TYPE: Final = "image/png"

_PUBLISHED: Final = "published"
_VERIFIED: Final = "verified"
_SKIPPED: Final = "skipped"
_FAILED: Final = "failed"


@dataclass(frozen=True, slots=True)
class PublishReport:
    """Kết quả một lượt: `published` đã `put` ít nhất một object, `verified` object sẵn khớp,
    `skipped` không cần làm, `failed` lệch hay storage hỏng."""

    published: int = 0
    verified: int = 0
    skipped: int = 0
    failed: int = 0


@dataclass(frozen=True, slots=True)
class _Blob:
    """Một object cần có: khoá, byte, `sha256`, loại nội dung và `kind` mà `sniff` phải thấy."""

    key: str
    data: bytes
    sha256: str
    content_type: str
    kind: str


@dataclass(frozen=True, slots=True)
class _Plan:
    """Tài sản của một mục: số đo của GLB, object mô hình và ảnh xem trước (mẫu từ tệp có thể không có ảnh)."""

    item_id: str
    glb: GlbAsset
    model: _Blob
    preview: _Blob | None


@dataclass(frozen=True, slots=True)
class _Known:
    """Phần dòng DB mà quyết định phát hành cần (đọc xong là đóng session)."""

    id: str
    published_at: datetime | None
    model_sha256: str | None
    preview_sha256: str | None
    verified_at: datetime | None


def _plan_of(item: CatalogueItem) -> _Plan:
    """Dựng GLB và PNG của `item` (tất định: cùng đầu vào → cùng `sha256`)."""
    glb = build_glb(item)
    png = build_preview_png(item)
    model = _Blob(library_object(item.id, MODEL_NAME), glb.data, glb.sha256, GLB_TYPE, "glb")
    preview = _Blob(library_object(item.id, PREVIEW_NAME), png, hashlib.sha256(png).hexdigest(), PNG_TYPE, "png")
    return _Plan(item.id, glb, model, preview)


def _same_shas(known: _Known, plan: _Plan) -> bool:
    """Đúng khi dòng đã phát hành và `model_sha256` khớp tài sản vừa dựng.

    Không so `preview_sha256`: byte PNG phụ thuộc bản zlib, nên so nó làm hai môi trường khác bản zlib `put` lại
    ảnh và đặt lại `published_at` mỗi lượt. Ảnh lệch được `_ensure` vá ở lượt kiểm kế tiếp (`library_verify_after_s`).
    """
    return known.published_at is not None and known.model_sha256 == plan.model.sha256


def _needs_work(known: _Known, plan: _Plan, now: datetime, verify_after: timedelta) -> bool:
    """Đúng khi mục cần làm: chưa phát hành, sha lệch, hoặc lần kiểm cuối đã quá cũ."""
    return not _same_shas(known, plan) or known.verified_at is None or now - known.verified_at > verify_after


async def _read_known(sessionmaker: async_sessionmaker[AsyncSession]) -> list[_Known]:
    """Session ngắn: mục của hệ thống chưa rút theo `id`; đóng trước khi đụng storage (K36)."""
    stmt = (
        select(
            LibraryItemRow.id,
            LibraryItemRow.published_at,
            LibraryItemRow.model_sha256,
            LibraryItemRow.preview_sha256,
            LibraryItemRow.verified_at,
        )
        .where(LibraryItemRow.owner_id.is_(None), LibraryItemRow.retired_at.is_(None))
        .order_by(LibraryItemRow.id)
    )
    async with sessionmaker() as session:
        return [_Known(*row) for row in (await session.execute(stmt)).all()]


async def _ensure(storage: ObjectStorage, blob: _Blob) -> tuple[bool, bool]:
    """Bảo đảm `blob` có trong storage: `(đã put, khớp)`; `stat` lại sau `put` kiểm `sha256` và `kind`."""
    info = await storage.stat(blob.key)
    wrote = info is None or info.sha256 != blob.sha256
    if wrote:
        await storage.put(blob.key, blob.data, content_type=blob.content_type, max_bytes=len(blob.data))
        info = await storage.stat(blob.key)
    matched = info is not None and info.sha256 == blob.sha256 and info.kind == blob.kind
    return wrote, matched


async def _record(sessionmaker: async_sessionmaker[AsyncSession], plan: _Plan, known: _Known, now: datetime) -> None:
    """Session ngắn: `UPDATE … WHERE id` số đo, khoá, sha; giữ `published_at` cũ khi sha không đổi."""
    glb = plan.glb
    values = {
        "width_mm": glb.width_mm,
        "depth_mm": glb.depth_mm,
        "height_mm": glb.height_mm,
        "triangle_count": glb.triangle_count,
        "file_size_bytes": glb.size_bytes,
        "model_key": plan.model.key,
        "model_sha256": plan.model.sha256,
        "preview_key": None if plan.preview is None else plan.preview.key,
        "preview_sha256": None if plan.preview is None else plan.preview.sha256,
        "published_at": known.published_at if _same_shas(known, plan) else now,
        "verified_at": now,
    }
    async with session_scope(sessionmaker) as session:
        await session.execute(update(LibraryItemRow).where(LibraryItemRow.id == plan.item_id).values(**values))


async def _publish_one(
    sessionmaker: async_sessionmaker[AsyncSession], storage: ObjectStorage, plan: _Plan, known: _Known, now: datetime
) -> str:
    """Bước 3-4 cho một mục; trả `published`/`verified`/`failed`. Chỉ nuốt `DEPENDENCY_UNAVAILABLE`."""
    try:
        results = [await _ensure(storage, blob) for blob in (plan.model, plan.preview) if blob is not None]
    except AppError as exc:
        if exc.code is not DEPENDENCY_UNAVAILABLE:
            raise
        _log.warning("library_publish_failed", extra={"item_id": plan.item_id, "code": exc.code.code})
        return _FAILED
    if not all(matched for _, matched in results):
        _log.error("library_asset_mismatch", extra={"item_id": plan.item_id})
        return _FAILED
    await _record(sessionmaker, plan, known, now)
    return _PUBLISHED if any(wrote for wrote, _ in results) else _VERIFIED


async def run_library_publish(
    sessionmaker: async_sessionmaker[AsyncSession],
    storage: ObjectStorage,
    clock: Clock,
    *,
    batch: int = BATCH,
    catalogue: tuple[CatalogueItem, ...] = CATALOGUE,
) -> PublishReport:
    """Một lượt phát hành: tối đa `batch` mục cần làm (thứ tự `id`), phần còn lại để lượt sau."""
    by_id = {item.id: item for item in catalogue}
    verify_after = timedelta(seconds=get_library_settings().library_verify_after_s)
    now = clock.now()
    counts: Counter[str] = Counter()
    attempted = 0
    for known in await _read_known(sessionmaker):
        item = by_id.get(known.id)
        if item is None:
            continue
        plan = _plan_of(item)
        if not _needs_work(known, plan, now, verify_after):
            counts[_SKIPPED] += 1
        elif attempted < batch:
            attempted += 1
            counts[await _publish_one(sessionmaker, storage, plan, known, now)] += 1
    return PublishReport(counts[_PUBLISHED], counts[_VERIFIED], counts[_SKIPPED], counts[_FAILED])


@dataclass(frozen=True, slots=True)
class ImportReport:
    """Kết quả `import-files`: `published` đã ghi dòng, `skipped` thiếu tệp,
    `failed` sha lệch, thiếu dòng hay storage hỏng."""

    published: int = 0
    skipped: int = 0
    failed: int = 0


def _file_plan(item: FileItem, directory: Path) -> _Plan | str:
    """Đọc `<id>.glb` (+ `<id>.png` nếu có) của `item`; trả `_Plan`, hoặc `skipped`/`failed`."""
    path = directory / f"{item.id}.glb"
    if not path.is_file():
        return _SKIPPED
    data = path.read_bytes()
    try:
        glb = measure_glb(data)
    except (ValueError, KeyError, IndexError):
        _log.error("library_file_unreadable", extra={"item_id": item.id})
        return _FAILED
    if glb.sha256 != item.model_sha256:
        _log.error("library_file_sha_mismatch", extra={"item_id": item.id})
        return _FAILED
    model = _Blob(library_object(item.id, MODEL_NAME), data, glb.sha256, GLB_TYPE, "glb")
    png_path = directory / f"{item.id}.png"
    preview = None
    if png_path.is_file():
        png = png_path.read_bytes()
        preview = _Blob(library_object(item.id, PREVIEW_NAME), png, hashlib.sha256(png).hexdigest(), PNG_TYPE, "png")
    return _Plan(item.id, glb, model, preview)


async def import_files(
    sessionmaker: async_sessionmaker[AsyncSession],
    storage: ObjectStorage,
    clock: Clock,
    directory: Path,
    *,
    catalogue: tuple[FileItem, ...] = FILE_CATALOGUE,
) -> ImportReport:
    """Phát hành mẫu từ tệp trong `directory`: so `sha256` với manifest, đo, `put`, rồi ghi dòng (K22, K36).

    Dòng phải có sẵn (seed tạo danh tính); thiếu dòng → `failed`. `published_at` giữ nguyên khi sha không đổi.
    """
    known = {row.id: row for row in await _read_known(sessionmaker)}
    now = clock.now()
    counts: Counter[str] = Counter()
    for item in catalogue:
        plan = _file_plan(item, directory)
        if isinstance(plan, str):
            counts[plan] += 1
        elif (row := known.get(item.id)) is None:
            _log.error("library_file_row_missing", extra={"item_id": item.id})
            counts[_FAILED] += 1
        else:
            result = await _publish_one(sessionmaker, storage, plan, row, now)
            counts[_FAILED if result == _FAILED else _PUBLISHED] += 1
    return ImportReport(counts[_PUBLISHED], counts[_SKIPPED], counts[_FAILED])


def open_storage(clock: Clock) -> ObjectStorage:
    """Storage thật của tiến trình (lịch và CLI dùng chung).

    `create_storage` nhập trễ: `minio` kéo `argon2`, mà `apps.api.*.jobs` không được nhập nó
    (BE-00 §2.1); nhập đầu module sẽ phá ranh giới đó dù mã này không chạm `argon2`.
    """
    from packages.core.settings import get_core_settings
    from packages.storage.factory import create_storage
    from packages.storage.settings import get_storage_settings

    return create_storage(get_storage_settings(), get_core_settings(), clock)
