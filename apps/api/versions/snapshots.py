"""Lõi phiên bản theo tầng: chụp, gỡ ảnh chụp cũ, giải ảnh chụp (B3-04 [5], [6]).

Chạy **trong giao dịch của người gọi** và không bao giờ `commit`: bản "trước" gọi trước
`write_layer`, bản "sau" gọi sau, cùng một giao dịch — rollback thì cả hai biến mất.

Thứ tự khoá theo BE-00 §7: `floors` (FOR SHARE) → `floor_documents` (FOR UPDATE) →
`versions`. Vì mọi người ghi `versions` của một tầng đều giữ khoá dòng tài liệu, `max(sequence)`
đọc được an toàn mà không cần khoá bảng.

Module nhập được trong ngữ cảnh worker: không `fastapi`, `starlette`, `jwt`, `argon2`, không
phần HTTP của `apps.api.core`.
"""

import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from functools import cache
from typing import Any, Final, cast

from pydantic import PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import RowMapping, Select, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.spatial_read.codec import DocumentCorruptError, document_from_json, document_to_json
from apps.api.spatial_read.documents import (
    DOCUMENT_SCHEMA_VERSION,
    FloorDocument,
    ensure_document,
    load_document,
)
from packages.core.clock import Clock
from packages.core.error_codes import NOT_FOUND
from packages.core.ids import new_id
from packages.core.text import nfc
from packages.db.models.floors import FloorRow
from packages.db.models.spatial import CHANGED_BY_RE
from packages.db.models.versions import VersionRecord
from packages.domain.spatial import Dimension, SpatialLayer

_log: Final = logging.getLogger(__name__)
_CREATOR_RE: Final = re.compile(CHANGED_BY_RE)


class VersionsSettings(BaseSettings):
    """Số phiên bản mới nhất còn giữ ảnh chụp (`VERSIONS_KEEP_SNAPSHOTS`)."""

    model_config = SettingsConfigDict(extra="ignore", env_file=None)

    versions_keep_snapshots: PositiveInt = 50


@cache
def get_versions_settings() -> VersionsSettings:
    """Cấu hình của tiến trình, đọc biến môi trường một lần."""
    return VersionsSettings()


def reset_versions_settings_cache() -> None:
    """Chỉ cho test và CLI: đọc lại biến môi trường ở lần gọi sau."""
    get_versions_settings.cache_clear()


@dataclass(frozen=True)
class VersionRow:
    """Siêu dữ liệu một phiên bản (không có ảnh chụp); `has_snapshot=False` khi đã bị gỡ."""

    id: str
    floor_pk: int
    project_id: str
    sequence: int
    floor_revision: int
    created_at: datetime
    creator_id: str
    creator_name: str
    note: str | None
    label: str | None
    has_snapshot: bool


@dataclass(frozen=True)
class DecodedSnapshot:
    """Ảnh chụp đã giải mã: lớp, kích thước và tỉ lệ mm/px lúc chụp (`None` khi chưa hiệu chỉnh)."""

    layer: SpatialLayer
    dimensions: tuple[Dimension, ...]
    scale_mm_per_px: Decimal | None


class _SnapshotMismatchError(ValueError):
    """Nội bộ: ảnh chụp lệch hình dạng của `snapshot_of`; `decode_snapshot` đổi nó thành `None`."""


def snapshot_of(doc: FloorDocument) -> dict[str, object]:
    """Ảnh chụp lồng của một tài liệu; `scaleMmPerPx` là chuỗi `Decimal` và vắng khi tỉ lệ NULL (K20)."""
    snapshot: dict[str, object] = {"schemaVersion": DOCUMENT_SCHEMA_VERSION}
    if doc.scale_mm_per_px is not None:
        snapshot["scaleMmPerPx"] = str(doc.scale_mm_per_px)
    snapshot["document"] = document_to_json(doc.layer, (), doc.dimensions)
    return snapshot


def _scale_of(value: object) -> Decimal | None:
    """`scaleMmPerPx` của ảnh chụp: vắng → `None`; không phải chuỗi số dương hữu hạn → lệch."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise _SnapshotMismatchError("scaleMmPerPx không phải chuỗi")
    try:
        scale = Decimal(value)
    except InvalidOperation as error:
        raise _SnapshotMismatchError("scaleMmPerPx không phải số") from error
    if not scale.is_finite() or scale <= 0:
        raise _SnapshotMismatchError("scaleMmPerPx phải dương hữu hạn")
    return scale


def _decode(raw: Mapping[str, object]) -> DecodedSnapshot:
    """Giải một ảnh chụp không rỗng; mọi lệch → `_SnapshotMismatchError` hoặc `DocumentCorruptError`."""
    if raw.get("schemaVersion") != DOCUMENT_SCHEMA_VERSION:
        raise _SnapshotMismatchError("schemaVersion lệch")
    document = raw.get("document")
    if not isinstance(document, Mapping):
        raise _SnapshotMismatchError("thiếu document")
    layer, _axes, dimensions = document_from_json(document)
    return DecodedSnapshot(layer=layer, dimensions=dimensions, scale_mm_per_px=_scale_of(raw.get("scaleMmPerPx")))


def decode_snapshot(raw: Mapping[str, object] | None, *, version_id: str) -> DecodedSnapshot | None:
    """Giải cột `snapshot`; `None` khi đã gỡ (không log) hoặc lệch / hỏng (log `snapshot_schema_mismatch`).

    Người gọi coi hai trường hợp `None` như nhau (`VERSION_SNAPSHOT_PURGED`), chỉ log phân biệt.
    Không tự `model_validate`: mọi giải mã đi qua `codec` như đường đọc tài liệu.
    """
    if raw is None:
        return None
    try:
        return _decode(raw)
    except (_SnapshotMismatchError, DocumentCorruptError):
        _log.warning("snapshot_schema_mismatch", extra={"version_id": version_id})
        return None


def summary_query() -> Select[Any]:
    """`SELECT` mọi cột trừ `snapshot`, cộng `has_snapshot`; #36, N17, N20 dùng chung.

    Cột jsonb lớn không bao giờ được kéo về chỉ để liệt kê (N17 cấm đọc `snapshot`).
    """
    columns = (
        VersionRecord.id,
        VersionRecord.floor_pk,
        VersionRecord.project_id,
        VersionRecord.sequence,
        VersionRecord.floor_revision,
        VersionRecord.created_at,
        VersionRecord.creator_id,
        VersionRecord.creator_name,
        VersionRecord.note,
        VersionRecord.label,
        VersionRecord.restored_from_id,
        VersionRecord.restore_base_revision,
    )
    return select(*columns, VersionRecord.snapshot.is_not(None).label("has_snapshot"))


def version_row(row: RowMapping) -> VersionRow:
    """Một dòng của `summary_query()` → `VersionRow`."""
    return VersionRow(
        id=row["id"],
        floor_pk=row["floor_pk"],
        project_id=row["project_id"],
        sequence=row["sequence"],
        floor_revision=row["floor_revision"],
        created_at=row["created_at"],
        creator_id=row["creator_id"],
        creator_name=row["creator_name"],
        note=row["note"],
        label=row["label"],
        has_snapshot=row["has_snapshot"],
    )


async def lock_floor_document(db: AsyncSession, *, floor_pk: int, clock: Clock) -> FloorDocument:
    """Khoá theo BE-00 §7: `floors` FOR SHARE (chưa xoá mềm) rồi dòng tài liệu FOR UPDATE.

    Tầng không có / đã xoá mềm → `NOT_FOUND` `resource="floor"`. Tầng chưa có tài liệu thì
    `ensure_document` (an toàn khi đua) rồi khoá lại: hai giao dịch cùng tầng mới nối đuôi nhau.
    """
    stmt = select(FloorRow.pk).where(FloorRow.pk == floor_pk, FloorRow.deleted_at.is_(None)).with_for_update(read=True)
    if (await db.execute(stmt)).scalar_one_or_none() is None:
        raise NOT_FOUND.error(resource="floor")
    doc = await load_document(db, floor_pk, for_update=True)
    if doc is None:
        await ensure_document(db, floor_pk=floor_pk, clock=clock)
        doc = await load_document(db, floor_pk, for_update=True)
    return cast("FloorDocument", doc)  # ensure_document vừa bảo đảm dòng tồn tại


def _check_actor(actor_id: str, actor_name: str, note: str | None) -> None:
    """Bước 1: đầu vào sai là lỗi lập trình của người gọi (K21), không phải lỗi người dùng."""
    if _CREATOR_RE.fullmatch(actor_id) is None:
        raise ValueError(f"actor_id sai mẫu: {actor_id!r}")
    if not nfc(actor_name).strip():
        raise ValueError("actor_name rỗng")
    if note is not None and note == "":
        raise ValueError("note rỗng; dùng None để không ghi chú")


async def _latest(db: AsyncSession, floor_pk: int) -> RowMapping | None:
    """Bản mới nhất của tầng (`sequence` lớn nhất), `None` khi chưa có bản nào."""
    stmt = summary_query().where(VersionRecord.floor_pk == floor_pk).order_by(VersionRecord.sequence.desc()).limit(1)
    return (await db.execute(stmt)).mappings().first()


async def record_version(
    db: AsyncSession,
    *,
    floor_pk: int,
    actor_id: str,
    actor_name: str,
    note: str | None,
    clock: Clock,
    restored_from_id: str | None = None,
    restore_base_revision: int | None = None,
) -> VersionRow:
    """Khuôn chụp phiên bản (bước 1-5 của [6]); `create_version` là vỏ công khai không có hai trường phục hồi.

    Bản mới nhất đã ở đúng `revision` của tài liệu → trả nó, không chèn (K18: giao lặp không
    nhân đôi). Ngược lại chèn `sequence = max + 1` rồi gỡ ảnh chụp của các bản quá trần —
    chỉ đặt `snapshot = NULL`, không bao giờ xoá dòng.
    """
    _check_actor(actor_id, actor_name, note)
    doc = await lock_floor_document(db, floor_pk=floor_pk, clock=clock)
    latest = await _latest(db, floor_pk)
    if latest is not None and latest["floor_revision"] == doc.revision:
        return version_row(latest)
    now = clock.now()
    record = VersionRecord(
        id=new_id("ver", clock),
        floor_pk=floor_pk,
        project_id=(await db.execute(select(FloorRow.project_id).where(FloorRow.pk == floor_pk))).scalar_one(),
        sequence=1 if latest is None else latest["sequence"] + 1,
        floor_revision=doc.revision,
        creator_id=actor_id,
        creator_name=nfc(actor_name),
        note=note,
        snapshot=snapshot_of(doc),
        restored_from_id=restored_from_id,
        restore_base_revision=restore_base_revision,
        created_at=now,
        updated_at=now,
    )
    db.add(record)
    await db.flush()
    await _purge_old_snapshots(db, floor_pk=floor_pk, sequence=record.sequence, now=now)
    return _row_of(record)


def _row_of(record: VersionRecord) -> VersionRow:
    """`VersionRow` của bản vừa chèn (chưa có nhãn, còn ảnh chụp)."""
    return VersionRow(
        id=record.id,
        floor_pk=record.floor_pk,
        project_id=record.project_id,
        sequence=record.sequence,
        floor_revision=record.floor_revision,
        created_at=record.created_at,
        creator_id=record.creator_id,
        creator_name=record.creator_name,
        note=record.note,
        label=None,
        has_snapshot=True,
    )


async def _purge_old_snapshots(db: AsyncSession, *, floor_pk: int, sequence: int, now: datetime) -> None:
    """Bước 5: gỡ ảnh chụp của bản cũ hơn `keep` bản mới nhất; siêu dữ liệu còn nguyên."""
    keep = get_versions_settings().versions_keep_snapshots
    await db.execute(
        update(VersionRecord)
        .where(
            VersionRecord.floor_pk == floor_pk,
            VersionRecord.snapshot.is_not(None),
            VersionRecord.sequence <= sequence - keep,
        )
        .values(snapshot=None, updated_at=now)
    )


async def create_version(
    db: AsyncSession, *, floor_pk: int, actor_id: str, actor_name: str, note: str | None, clock: Clock
) -> VersionRow:
    """Chụp phiên bản của tầng trong giao dịch người gọi (pipeline, bản "trước"/"sau" của phục hồi)."""
    return await record_version(db, floor_pk=floor_pk, actor_id=actor_id, actor_name=actor_name, note=note, clock=clock)
