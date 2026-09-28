"""Nghiệp vụ của #36, N17-N20 (B3-04 [6]): nhận `AsyncSession`, `ProjectAccess`, `Clock`; không `commit`.

`router.py` chỉ gọi vào đây. Tách khỏi HTTP để lỗi ném ra (`AppError`, `VersionConflictError`)
đi qua đúng một đường dịch của khung, và để giao dịch của `AppRoute` là ranh giới duy nhất:
N19 rollback **cả** bản "trước" khi `write_layer` ném 409 (W20) hay tính lại tỉ lệ hỏng.

Mọi đường tìm phiên bản đi qua `_locate` — "phiên bản như #36" là `(project_id, id)` **và** tầng
chưa xoá; id sai mẫu hay của dự án khác đều là 404 `resource:"version"` (K08). Không đường nào
ở đây chọn cột `snapshot` ngoài `IS NOT NULL` trừ N18/N19 (`_load_snapshot`), và không đường
nào xoá dòng `versions`.
"""

import unicodedata
from dataclasses import dataclass, replace
from typing import Final

from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.access.activity import record_activity
from apps.api.access.kinds import ActivityKind
from apps.api.core.pagination import CursorPage, PageParams, decode_cursor, encode_cursor
from apps.api.floors.lookup import get_floor
from apps.api.projects.access import ProjectAccess
from apps.api.spatial_read.documents import FloorDocument
from apps.api.spatial_read.wire import dimensions_out, layer_out
from apps.api.spatial_write.writer import LayerWrite, write_layer
from apps.api.versions.errors import VERSION_FLOOR_MISMATCH, VERSION_SNAPSHOT_PURGED
from apps.api.versions.messages import after_note, before_note
from apps.api.versions.schemas import FloorVersionSnapshotOut, FloorVersionSummaryOut, VersionOut
from apps.api.versions.snapshots import (
    DecodedSnapshot,
    VersionRow,
    create_version,
    decode_snapshot,
    lock_floor_document,
    record_version,
    summary_query,
    version_row,
)
from packages.core.clock import Clock
from packages.core.error_codes import NOT_FOUND, VALIDATION
from packages.core.ids import is_id
from packages.core.text import nfc
from packages.db.models.auth import User
from packages.db.models.floors import FloorRow
from packages.db.models.versions import VersionRecord
from packages.domain.scale.rescale import RescaleError, rescale_dimensions, rescale_unreviewed
from packages.domain.spatial import Dimension, SpatialLayer

LIST_OP: Final = "versions_list_versions"
"""`op` ký vào cursor của N17: cursor của danh sách khác không dùng lại được (W22)."""

LABEL_MAX_UNITS: Final = 60
"""Độ dài nhãn tối đa tính bằng **đơn vị UTF-16**, như `z.string().max(60)` của FE."""

_FORBIDDEN_LABEL_CATEGORIES: Final = frozenset({"Cc", "Cf"})
"""Ký tự điều khiển và định dạng (gồm U+202A-U+202E, U+2066-U+2069): nhãn không được chứa."""


@dataclass(frozen=True)
class _Located:
    """Một phiên bản đã tìm thấy cùng `level_id` và tên của tầng chứa nó."""

    row: VersionRow
    level_id: str
    floor_name: str


@dataclass(frozen=True)
class RestoreOutcome:
    """Kết quả N19: `replayed=True` là lượt gửi lại đã thành công (C09b) → router trả 200 thay 201."""

    row: VersionRow
    replayed: bool


def summary_out(row: VersionRow) -> FloorVersionSummaryOut:
    """`VersionRow` → dây `FloorVersionSummary`; dùng chung N17, N19, N20."""
    return FloorVersionSummaryOut(
        id=row.id,
        sequence=row.sequence,
        floor_revision=row.floor_revision,
        created_at=row.created_at,
        creator_id=row.creator_id,
        creator_name=row.creator_name,
        note=row.note,
        label=row.label,
        has_snapshot=row.has_snapshot,
    )


async def _locate(db: AsyncSession, project_id: str, version_id: str, *, for_update: bool = False) -> _Located:
    """Phiên bản như #36 (kèm `level_id`, tên tầng), hay 404 `resource:"version"`.

    Id sai mẫu trả 404 mà không chạm DB. `for_update` khoá **chỉ** dòng `versions` (`of=`): khoá
    cả `floors` ở đây sẽ đảo thứ tự khoá của BE-00 §7.
    """
    if not is_id("ver", version_id):
        raise NOT_FOUND.error(resource="version")
    stmt = (
        summary_query()
        .add_columns(FloorRow.level_id.label("level_id"), FloorRow.name.label("floor_name"))
        .join(FloorRow, FloorRow.pk == VersionRecord.floor_pk)
        .where(VersionRecord.project_id == project_id, VersionRecord.id == version_id, FloorRow.deleted_at.is_(None))
    )
    if for_update:
        stmt = stmt.with_for_update(of=VersionRecord)
    found = (await db.execute(stmt)).mappings().one_or_none()
    if found is None:
        raise NOT_FOUND.error(resource="version")
    return _Located(row=version_row(found), level_id=found["level_id"], floor_name=found["floor_name"])


async def _load_snapshot(db: AsyncSession, version_id: str) -> DecodedSnapshot:
    """Ảnh chụp đã giải mã; mất, lệch lược đồ hay hỏng đều là `VERSION_SNAPSHOT_PURGED` (không 500)."""
    raw = (await db.execute(select(VersionRecord.snapshot).where(VersionRecord.id == version_id))).scalar_one()
    decoded = decode_snapshot(raw, version_id=version_id)
    if decoded is None:
        raise VERSION_SNAPSHOT_PURGED.error()
    return decoded


async def _user_name(db: AsyncSession, user_id: str) -> str:
    """Tên người gọi đọc **trong giao dịch**: bản ghi lưu tên **lúc ghi**, đổi tên sau không sửa dòng cũ."""
    return (await db.execute(select(User.name).where(User.id == user_id))).scalar_one()


async def read_version(db: AsyncSession, access: ProjectAccess, version_id: str) -> VersionOut:
    """#36 — sáu trường của `Version` cũ."""
    row = (await _locate(db, access.project_id, version_id)).row
    return VersionOut(
        id=row.id,
        project_id=row.project_id,
        sequence=row.sequence,
        created_at=row.created_at,
        creator_id=row.creator_id,
        note=row.note,
    )


async def list_versions(
    db: AsyncSession, access: ProjectAccess, *, floor_id: str, page: PageParams
) -> CursorPage[FloorVersionSummaryOut]:
    """N17 — `sequence` giảm dần, phân trang bằng cursor `sequence < :pos`; không chọn cột `snapshot`.

    Đọc `limit + 1` dòng: dòng thừa chỉ để biết còn trang sau, không trả ra.
    """
    filters = {"floorId": floor_id}
    position = None if page.cursor is None else int(decode_cursor(page.cursor, LIST_OP, filters)["sequence"])
    floor = await get_floor(db, project_id=access.project_id, level_id=floor_id)
    if floor is None:
        raise NOT_FOUND.error(resource="floor")
    stmt = summary_query().where(VersionRecord.floor_pk == floor.pk)
    if position is not None:
        stmt = stmt.where(VersionRecord.sequence < position)
    rows = (await db.execute(stmt.order_by(desc(VersionRecord.sequence)).limit(page.limit + 1))).mappings().all()
    items = [version_row(row) for row in rows[: page.limit]]
    more = len(rows) > page.limit
    return CursorPage[FloorVersionSummaryOut](
        items=[summary_out(item) for item in items],
        next_cursor=encode_cursor(LIST_OP, filters, {"sequence": items[-1].sequence}) if more else None,
    )


async def read_snapshot(
    db: AsyncSession, access: ProjectAccess, *, version_id: str, floor_id: str
) -> FloorVersionSnapshotOut:
    """N18 — `layer` và `dimensions` của ảnh chụp; thứ tự kiểm: 404 → tầng lệch → ảnh chụp."""
    located = await _locate(db, access.project_id, version_id)
    if located.level_id != floor_id:
        raise VERSION_FLOOR_MISMATCH.error(field="floorId")
    decoded = await _load_snapshot(db, version_id)
    return FloorVersionSnapshotOut(
        version_id=version_id, layer=layer_out(decoded.layer), dimensions=dimensions_out(decoded.dimensions)
    )


async def _replayed(
    db: AsyncSession, *, version: VersionRow, doc: FloorDocument, actor_id: str, base_version: int
) -> VersionRow | None:
    """C09b: bản mới nhất chính là kết quả một lượt phục hồi **cùng người, cùng bản, cùng `baseVersion`**.

    Chạy **trước** kiểm ảnh chụp: lượt đầu có thể đã đẩy bản nguồn khỏi các bản còn nội dung.
    So `restore_base_revision` chứ không so `revision - 1`: lượt đầu đi qua nhánh "diff rỗng" của
    W20 có thể đã ghi trên `revision` mới hơn `baseVersion`.
    """
    stmt = summary_query().where(VersionRecord.floor_pk == version.floor_pk)
    # `version` vừa tìm thấy nên tầng luôn có ≥ 1 bản (không bao giờ xoá dòng `versions`): `one()`, không nhánh rỗng.
    latest = (await db.execute(stmt.order_by(desc(VersionRecord.sequence)).limit(1))).mappings().one()
    matches = (
        latest[VersionRecord.restored_from_id] == version.id
        and latest[VersionRecord.creator_id] == actor_id
        and latest[VersionRecord.floor_revision] == doc.revision
        and latest[VersionRecord.restore_base_revision] == base_version
    )
    return version_row(latest) if matches else None


def _rescaled(decoded: DecodedSnapshot, doc: FloorDocument) -> tuple[SpatialLayer, tuple[Dimension, ...]]:
    """Đưa ảnh chụp về tỉ lệ hiện tại: chỉ khi hai tỉ lệ cùng có và khác nhau (W, HOP-DONG-MOI §5).

    Mục đã duyệt giữ nguyên (K21). `RescaleError` (tường dài 0…) → 422 `VALIDATION`, giao dịch rollback.
    """
    old, new = decoded.scale_mm_per_px, doc.scale_mm_per_px
    if old is None or new is None or old == new:
        return decoded.layer, decoded.dimensions
    try:
        return (
            rescale_unreviewed(decoded.layer, float(old), float(new)),
            rescale_dimensions(decoded.dimensions, float(old), float(new)),
        )
    except RescaleError as exc:
        raise VALIDATION.error(count=1) from exc


async def restore_version(
    db: AsyncSession, access: ProjectAccess, *, version_id: str, floor_id: str, base_version: int, clock: Clock
) -> RestoreOutcome:
    """N19 — phục hồi `layer`, `dimensions` của một phiên bản vào tầng, trong giao dịch của request.

    Bản "trước" (`create_version`) gọi trước `write_layer`, bản "sau" (`record_version`) gọi sau và
    chụp **tài liệu thật**. So `baseVersion` là việc của `write_layer` (K07); `VersionConflictError`
    của nó lan ra nguyên vẹn. Không đổi `revision` → không bản mới, không nhật ký (K18).
    """
    located = await _locate(db, access.project_id, version_id)
    version = located.row
    if located.level_id != floor_id:
        raise VERSION_FLOOR_MISMATCH.error(field="body.floorId")
    actor_id = access.principal.user_id
    doc = await lock_floor_document(db, floor_pk=version.floor_pk, clock=clock)
    replay = await _replayed(db, version=version, doc=doc, actor_id=actor_id, base_version=base_version)
    if replay is not None:
        return RestoreOutcome(replay, replayed=True)
    if base_version > doc.revision:
        raise VALIDATION.error(field="baseVersion")
    decoded = await _load_snapshot(db, version.id)
    after, new_revision = await _apply_restore(
        db, version=version, decoded=decoded, doc=doc, actor_id=actor_id, base_version=base_version, clock=clock
    )
    if new_revision != doc.revision:
        await record_activity(
            db,
            actor_id=actor_id,
            kind=ActivityKind.VERSION_RESTORE,
            object_code=version.id,
            object_label=located.floor_name,
            clock=clock,
            project_id=access.project_id,
        )
    return RestoreOutcome(after, replayed=False)


async def _apply_restore(
    db: AsyncSession,
    *,
    version: VersionRow,
    decoded: DecodedSnapshot,
    doc: FloorDocument,
    actor_id: str,
    base_version: int,
    clock: Clock,
) -> tuple[VersionRow, int]:
    """Bước 6-8 của N19: bản "trước", `write_layer` sau khi tính lại tỉ lệ, bản "sau".

    Trả `(bản sau, revision mới)`. `revision` không đổi nghĩa là ảnh chụp trùng hiện trạng: bản
    "sau" khi đó là bản mới nhất có sẵn (`record_version` không chèn, K18).
    """
    actor_name = await _user_name(db, actor_id)
    await create_version(
        db,
        floor_pk=version.floor_pk,
        actor_id=actor_id,
        actor_name=actor_name,
        note=before_note(version.sequence),
        clock=clock,
    )
    layer, dimensions = _rescaled(decoded, doc)
    result = await write_layer(
        db,
        floor_pk=version.floor_pk,
        base_revision=base_version,
        body=LayerWrite(layer=layer, scale_mm_per_px=None, dimensions=dimensions),
        actor_id=actor_id,
        actor_name=actor_name,
        clock=clock,
    )
    after = await record_version(
        db,
        floor_pk=version.floor_pk,
        actor_id=actor_id,
        actor_name=actor_name,
        note=after_note(version.sequence),
        clock=clock,
        restored_from_id=version.id,
        restore_base_revision=base_version,
    )
    return after, result.revision


def normalize_label(raw: str) -> str | None:
    """Nhãn chuẩn: `nfc` rồi `strip`; rỗng → `None` (gỡ nhãn).

    Đo độ dài bằng đơn vị UTF-16 như zod của FE (ký tự ngoài BMP = 2), và cấm ký tự `Cc`/`Cf`
    (điều khiển, đảo chiều U+202E…). Sai → 422 `VALIDATION` `field:"label"`.
    """
    text = nfc(raw).strip()
    units = len(text.encode("utf-16-le")) // 2
    if units > LABEL_MAX_UNITS or any(unicodedata.category(ch) in _FORBIDDEN_LABEL_CATEGORIES for ch in text):
        raise VALIDATION.error(field="label")
    return text or None


async def label_version(
    db: AsyncSession, access: ProjectAccess, *, version_id: str, label: str, clock: Clock
) -> VersionRow:
    """N20 — đặt/gỡ nhãn; khoá dòng `FOR UPDATE`, nhãn không đổi → không ghi, không nhật ký.

    Không sinh phiên bản, không đổi `revision` tầng, không `touch_project`: nhãn là siêu dữ liệu
    của lịch sử, không phải nội dung tầng. Bản đã mất ảnh chụp vẫn gắn nhãn được.
    """
    new_label = normalize_label(label)
    located = await _locate(db, access.project_id, version_id, for_update=True)
    if located.row.label == new_label:
        return located.row
    await db.execute(
        update(VersionRecord).where(VersionRecord.id == version_id).values(label=new_label, updated_at=clock.now())
    )
    await record_activity(
        db,
        actor_id=access.principal.user_id,
        kind=ActivityKind.VERSION_LABEL,
        object_code=version_id,
        object_label=located.floor_name,
        clock=clock,
        project_id=access.project_id,
    )
    return replace(located.row, label=new_label)
