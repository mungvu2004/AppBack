"""Lõi ghi lớp không gian một tầng, có kiểm version (B3-03 [2], [6]).

Một lượt ghi phải làm xong bốn việc trong đúng một giao dịch của người gọi: quyết xem
bản ghi gửi lên còn hợp thời không (W20, C09b), đổi tỉ lệ cho các mục chưa duyệt khi
người hiệu chỉnh tỉ lệ, nhận quyền sở hữu id thực thể (W4), và để lại nhật ký theo trường
cho FE giải xung đột. Thứ tự khoá là thứ tự của BE-00 §7 — `floors` → `floor_documents`
→ `floor_entity_ids` → `project_floor_summaries` → `projects` — nên hai lượt ghi song
song không thể chờ vòng.

Bước 11-14 nằm trong một SAVEPOINT: `claim_entity_ids` hỏng **sau** khi `UPDATE` đã tăng
`revision`, và không rollback tới savepoint thì người gọi bắt `LAYER_INTEGRITY_BROKEN`
rồi `commit` sẽ giữ lại một bản ghi không ai ghi. Thua đua (`UPDATE` ăn 0 dòng) không
phải lỗi: quay lại bước 3 với `base_revision` **gốc**, tối đa `SPATIAL_WRITE_ATTEMPTS` lần.

Module nhập được trong ngữ cảnh worker (BE-00 §7): không `fastapi`, không phần HTTP của
`apps.api.core`. Lỗi là `AppError` mã của `errors.py`, hay `ValueError` khi **người gọi
Python** truyền sai đối số (không bao giờ do dây gửi lên).
"""

import json
import logging
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
from typing import Final, Literal, Protocol

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.drawings.drawings import current_drawing
from apps.api.projects.summaries import set_layer_counts, touch_project
from apps.api.spatial_read.codec import document_to_json, entity_ids
from apps.api.spatial_read.counts import layer_counts
from apps.api.spatial_read.documents import FloorDocument, ScaleSource, ensure_document, load_document
from apps.api.spatial_read.entity_ids import claim_entity_ids
from apps.api.spatial_write.changes import remote_changes_since
from apps.api.spatial_write.errors import LAYER_INTEGRITY_BROKEN, LAYER_LEVEL_MISMATCH, REVIEW_BY_AI_FORBIDDEN
from apps.api.spatial_write.settings import get_spatial_write_settings
from packages.core.clock import Clock
from packages.core.error_codes import DEPENDENCY_UNAVAILABLE, NOT_FOUND, VALIDATION
from packages.core.errors import MISSING, SYSTEM_PIPELINE, VersionConflictError
from packages.db.models.floors import FloorRow
from packages.db.models.spatial import FloorChangeLogRow, FloorDocumentRow
from packages.domain.scale import RescaleError, rescale_dimensions, rescale_unreviewed
from packages.domain.spatial import (
    ChangeEntityType,
    Dimension,
    FieldChange,
    SpatialLayer,
    ai_reviewed_ids,
    change_entity_type,
    check_integrity,
    diff_layers,
    has_critical,
    has_untracked_changes,
    polygon_area_m2,
)

_log: Final = logging.getLogger(__name__)

ScaleWriter = Literal["human", "pipeline", "project_default"]
"""Ai đặt tỉ lệ của lượt ghi này; `none` không phải lựa chọn của người ghi (W24)."""

_RANK: Final[Mapping[str, int]] = {"human": 3, "pipeline": 2, "project_default": 1, "none": 0}
"""Hạng nguồn tỉ lệ: nguồn hạng thấp không đè được tỉ lệ của nguồn hạng cao (K19)."""

_LISTS: Final = ("walls", "openings", "rooms", "furniture")
"""Thứ tự duyệt danh sách khi dựng `field` của lỗi ([6] bước 2)."""

_TOUCH_FIELD: Final[Mapping[ChangeEntityType, str]] = {
    "wall": "thickness_mm",
    "door": "width_mm",
    "window": "width_mm",
    "room": "name",
    "furniture": "kind",
}
"""Trường đại diện của dấu chạm (HOP-DONG-MOI §1.3): một dòng cho thay đổi ngoài bảng diff."""


class MergeOutcome(Protocol):
    """Kết quả gộp của B3-06 (`MergeResult`); khai bằng Protocol để không nhập ngược B3-06."""

    @property
    def layer(self) -> SpatialLayer:
        """Lớp sau khi gộp, đã ở hệ tỉ lệ đích."""
        ...

    @property
    def id_map(self) -> Mapping[str, str]:
        """Id mục AI bị bỏ → id mục được giữ; `referenceIds` của kích thước đi theo bảng này."""
        ...


@dataclass(frozen=True)
class LayerWrite:
    """Thân một lượt ghi. `dimensions` chỉ hàm Python truyền (B5-06b, N19), `schemas.py` không có."""

    layer: SpatialLayer | None
    scale_mm_per_px: Decimal | None
    dimensions: tuple[Dimension, ...] | None = None


@dataclass(frozen=True)
class WriteResult:
    """Kết quả một lượt ghi; `applied=False` là không có gì đổi (C09b, bước 10) — vẫn là 200."""

    revision: int
    layer: SpatialLayer
    applied: bool


@dataclass(frozen=True)
class _Request:
    """Đối số một lượt ghi đã gom lại, cộng `project_id`/`level_id` đọc dưới khoá ở bước 1."""

    floor_pk: int
    base_revision: int
    body: LayerWrite
    actor_id: str
    actor_name: str
    clock: Clock
    merge: Callable[[SpatialLayer, Decimal | None], MergeOutcome] | None
    scale_source: ScaleWriter
    page_key: str | None
    project_id: str
    level_id: str


@dataclass(frozen=True)
class _Scale:
    """Tỉ lệ đích của lượt ghi; `factor` khác `None` nghĩa là tỉ lệ đổi và lớp phải tính lại."""

    value: Decimal | None
    source: ScaleSource
    page_key: str | None
    factor: tuple[float, float] | None


@dataclass(frozen=True)
class _Next:
    """Lớp sắp ghi và bảng đổi id của đường `merge` (rỗng ở đường thường)."""

    layer: SpatialLayer
    id_map: Mapping[str, str]


def _wire(model: SpatialLayer | Dimension) -> dict[str, object]:
    """Dạng dây của một mô hình miền, đúng luật xuất của `codec` (camelCase, vắng khoá thay `null`)."""
    return model.model_dump(mode="json", by_alias=True, exclude_none=True)


def body_sha256(body: LayerWrite) -> str:
    """Vân tay của một thân, để C09b nhận ra lượt gửi lại của cùng người.

    JSON chuẩn (`sort_keys`, không khoảng trắng, `ensure_ascii=False`) nên thân khác thứ
    tự khoá vẫn cho cùng vân tay; tỉ lệ là `str(Decimal)` vì `10` và `10.000000` là cùng
    một tỉ lệ nhưng khác `float`. Mô hình B3-01 chuẩn hoá NFC ngay lúc kiểm, nên thân gửi
    lại dạng NFD ra đúng vân tay này.

    Đổi lại, `Decimal("10")` và `Decimal("10.000000")` ra **hai** vân tay khác nhau. Vô hại
    cho #35 (Pydantic luôn quantize 6 chữ số trước khi tới đây); người gọi Python phải tự
    quantize nếu muốn C09b khớp, không thì lượt gửi lại chỉ **trượt** C09b rồi rơi vào phép
    kiểm xung đột — hướng an toàn.
    """
    payload = {
        "layer": None if body.layer is None else _wire(body.layer),
        "dimensions": None if body.dimensions is None else [_wire(item) for item in body.dimensions],
        "scaleMillimetresPerPixel": None if body.scale_mm_per_px is None else str(body.scale_mm_per_px),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256(canonical.encode()).hexdigest()


async def write_layer(
    db: AsyncSession,
    *,
    floor_pk: int,
    base_revision: int,
    body: LayerWrite,
    actor_id: str,
    actor_name: str,
    clock: Clock,
    merge: Callable[[SpatialLayer, Decimal | None], MergeOutcome] | None = None,
    scale_source: ScaleWriter = "human",
    page_key: str | None = None,
) -> WriteResult:
    """Ghi lớp (và/hoặc tỉ lệ) của một tầng trong giao dịch của người gọi; **không** `commit`.

    Ném `NOT_FOUND` (`resource="floor"`), `VALIDATION`, `REVIEW_BY_AI_FORBIDDEN`,
    `LAYER_LEVEL_MISMATCH`, `LAYER_INTEGRITY_BROKEN`, `VersionConflictError` (W20), hay
    `DEPENDENCY_UNAVAILABLE` + `Retry-After: 1` khi thua đua `SPATIAL_WRITE_ATTEMPTS` lần
    liền. `ValueError` chỉ khi **người gọi Python** truyền sai đối số ([2]).
    """
    floor = await _locked_floor(db, floor_pk)
    _check_arguments(body, merge=merge, actor_id=actor_id, level_id=floor.level_id)
    if body.layer is not None:
        _check_candidate(body.layer, level_id=floor.level_id)
    request = _Request(
        floor_pk=floor_pk,
        base_revision=base_revision,
        body=body,
        actor_id=actor_id,
        actor_name=actor_name,
        clock=clock,
        merge=merge,
        scale_source=scale_source,
        page_key=page_key,
        project_id=floor.project_id,
        level_id=floor.level_id,
    )
    attempts = get_spatial_write_settings().spatial_write_attempts
    for _ in range(attempts):
        result = await _attempt(db, request)
        if result is not None:
            return result
    # Người vận hành thấy 503 mà không biết tầng nào: một dòng đủ để tra ngay tầng đang bị
    # ghi dồn, không cần bật lại log gỡ lỗi.
    _log.warning("spatial_write_exhausted_attempts", extra={"floor_pk": floor_pk, "attempts": attempts})
    raise DEPENDENCY_UNAVAILABLE.error(retry_after=1)


async def _locked_floor(db: AsyncSession, floor_pk: int) -> FloorRow:
    """Bước 1: khoá `floors … FOR SHARE` và lấy `(project_id, level_id)`; tầng không sống → 404."""
    row = (
        await db.execute(
            select(FloorRow).where(FloorRow.pk == floor_pk, FloorRow.deleted_at.is_(None)).with_for_update(read=True)
        )
    ).scalar_one_or_none()
    if row is None:
        raise NOT_FOUND.error(resource="floor")
    return row


def _check_arguments(
    body: LayerWrite,
    *,
    merge: Callable[[SpatialLayer, Decimal | None], MergeOutcome] | None,
    actor_id: str,
    level_id: str,
) -> None:
    """Ba điều kiện `ValueError` của [2]: lỗi lập trình của người gọi, không phải lỗi của dây."""
    if merge is not None and body.layer is not None:
        raise ValueError("merge và body.layer loại trừ nhau: nền của merge là lớp đang có")
    if merge is None and body.layer is not None and actor_id == SYSTEM_PIPELINE:
        raise ValueError("ghi lớp của pipeline phải đi qua merge, không đè thẳng (K21)")
    for dimension in body.dimensions or ():
        if dimension.source != "ai" or dimension.reviewed or dimension.level_id != level_id:
            raise ValueError(f"kích thước {dimension.id} phải là mục AI chưa duyệt của tầng đang ghi")


def _positions(layer: SpatialLayer) -> Iterator[tuple[str, int, object]]:
    """`(tên danh sách, chỉ số, thực thể)` theo đúng thứ tự dựng `field` của lỗi."""
    for name in _LISTS:
        for index, entity in enumerate(getattr(layer, name)):
            yield name, index, entity


def _field_of(layer: SpatialLayer, entity_id: str, field: str) -> str:
    """`field` của lỗi trỏ vào một mục, ví dụ `body.layer.walls.3.reviewed`."""
    paths = [
        f"body.layer.{name}.{index}.{field}"
        for name, index, entity in _positions(layer)
        if getattr(entity, "id", None) == entity_id
    ]
    return paths[0]


def _check_candidate(layer: SpatialLayer, *, level_id: str) -> None:
    """Bước 2: A5 → `levelId` → toàn vẹn `critical`; lỗi đầu tiên dừng ngay.

    Thứ tự này là hợp đồng với FE: một lớp vừa vi phạm A5 vừa hỏng tham chiếu phải ra
    `REVIEW_BY_AI_FORBIDDEN`, vì đó là lỗi người dùng sửa được ngay trên màn hình.
    """
    reviewed_by_ai = ai_reviewed_ids(layer)
    if reviewed_by_ai:
        raise REVIEW_BY_AI_FORBIDDEN.error(field=_field_of(layer, reviewed_by_ai[0], "reviewed"))
    elsewhere = [
        f"body.layer.{name}.{index}.levelId"
        for name, index, entity in _positions(layer)
        if getattr(entity, "level_id", level_id) != level_id
    ]
    if elsewhere:
        raise LAYER_LEVEL_MISMATCH.error(field=elsewhere[0])
    issues = check_integrity(layer, level_id=level_id)
    if has_critical(issues):
        raise LAYER_INTEGRITY_BROKEN.error(count=sum(1 for issue in issues if issue.severity == "critical"))


async def _current_document(db: AsyncSession, request: _Request) -> FloorDocument:
    """Bước 3: tài liệu hiện tại của tầng, và **đã khoá** khi đi đường `merge`.

    Đường thường đọc thẳng và chỉ tạo dòng khi thật sự thiếu — một truy vấn ở ca thường.
    Đường `merge` phải `ensure_document` **trước** rồi đọc lại `FOR UPDATE`: câu đọc lại bên
    trong `ensure_document` (file của B3-02) không khoá, nên nhánh "tầng chưa có dòng" để
    `merge` chạy **không khoá** ở lượt ghi đầu tiên của một tầng — đúng cảnh `merge` được
    thiết kế để không bao giờ gặp, vì nó không thử lại và thua đua đủ số lần là 503.
    """
    if request.merge is None:
        return await load_document(db, request.floor_pk) or await ensure_document(
            db, floor_pk=request.floor_pk, clock=request.clock
        )
    created = await ensure_document(db, floor_pk=request.floor_pk, clock=request.clock)
    # `or created` chỉ là cầu kiểu tĩnh: `floors` đang bị khoá `FOR SHARE` (bước 1) nên không
    # ai xoá được tầng — và cascade dòng tài liệu — giữa hai câu này.
    return await load_document(db, request.floor_pk, for_update=True) or created


async def _attempt(db: AsyncSession, request: _Request) -> WriteResult | None:
    """Một lượt thử bước 3-15; `None` = thua đua ở bước 11, người gọi thử lại từ bước 3."""
    current = await _current_document(db, request)
    settled = await _settle_base(db, request, current)
    if isinstance(settled, WriteResult):
        return settled
    scale = await _target_scale(db, request, current)
    nxt = _next_layer(request, current, scale)
    dimensions, touched = _next_dimensions(request, current, scale, nxt)
    document = document_to_json(nxt.layer, (), dimensions)
    if _unchanged(current, document, scale):
        return WriteResult(current.revision, current.layer, applied=False)
    return await _commit(
        db, request, current, expected=settled, nxt=nxt, document=document, scale=scale, touched=touched
    )


async def _settle_base(db: AsyncSession, request: _Request, current: FloorDocument) -> int | WriteResult:
    """Bước 4-5: bản ghi mà `UPDATE` sẽ đòi, hay một `WriteResult` sớm của C09b.

    Đường `merge` bỏ hẳn hai bước này: nó đã khoá dòng tài liệu ở bước 3, và nền của nó
    **là** lớp hiện tại chứ không phải bản người dùng cầm trên tay.
    """
    if request.merge is not None:
        return current.revision
    if request.base_revision > current.revision:
        raise VALIDATION.error(field="baseVersion")
    if request.base_revision == current.revision:
        return request.base_revision
    if (
        current.last_writer_id == request.actor_id
        and current.last_body_sha256 == body_sha256(request.body)
        and current.last_base_revision == request.base_revision
    ):
        return WriteResult(current.revision, current.layer, applied=False)
    remote = await remote_changes_since(
        db,
        floor_pk=request.floor_pk,
        base_revision=request.base_revision,
        limit=get_spatial_write_settings().spatial_conflict_changes_max,
    )
    if remote:
        raise VersionConflictError(current_version=current.revision, remote_changes=remote)
    return current.revision


async def _target_scale(db: AsyncSession, request: _Request, current: FloorDocument) -> _Scale:
    """Bước 6: tỉ lệ, nguồn và trang sau lượt ghi; `factor` khác `None` thì lớp phải tính lại.

    Luật theo trang: một lượt `merge` mang tỉ lệ của **trang khác** thì tỉ lệ đang có
    không nói gì về trang ấy, nên hạng của nó tính là `none` và nền không bị `rescale`.
    """
    other_page = (
        request.merge is not None and current.scale_page_key is not None and current.scale_page_key != request.page_key
    )
    rank = 0 if other_page else _RANK[current.scale_source]
    target = request.body.scale_mm_per_px
    if target is None or _RANK[request.scale_source] < rank:
        return _Scale(current.scale_mm_per_px, current.scale_source, current.scale_page_key, factor=None)
    previous = current.scale_mm_per_px
    factor = None if other_page or previous is None or previous == target else (float(previous), float(target))
    return _Scale(target, request.scale_source, await _page_of(db, request, current), factor=factor)


async def _page_of(db: AsyncSession, request: _Request, current: FloorDocument) -> str | None:
    """Trang bản vẽ của tỉ lệ mới: `page_key` của `merge`, không thì trang của lớp đang có."""
    if request.merge is not None:
        return request.page_key
    if current.scale_page_key is not None:
        return current.scale_page_key
    drawing = await current_drawing(db, request.floor_pk)
    return None if drawing is None else drawing.page_key


def _rescaled_layer(layer: SpatialLayer, factor: tuple[float, float]) -> SpatialLayer:
    """`rescale_unreviewed` với lỗi đổi sang 422 của #35 (người dùng sửa bằng cách gửi tỉ lệ khác)."""
    try:
        return rescale_unreviewed(layer, *factor)
    except RescaleError as error:
        raise VALIDATION.error(field="body.scaleMillimetresPerPixel") from error


def _rescaled_dimensions(dimensions: Sequence[Dimension], factor: tuple[float, float]) -> tuple[Dimension, ...]:
    """`rescale_dimensions` với cùng cách đổi lỗi như `_rescaled_layer`."""
    try:
        return rescale_dimensions(dimensions, *factor)
    except RescaleError as error:
        raise VALIDATION.error(field="body.scaleMillimetresPerPixel") from error


def _with_areas(layer: SpatialLayer) -> SpatialLayer:
    """Bước 8: `areaM2` của **mọi** phòng tính lại từ đường bao (W18), kể cả phòng đã duyệt.

    Không tính là sửa mục đã duyệt: diện tích là số dẫn xuất, và để client gửi lên một
    giá trị tự tính thì hai bên sẽ lệch ở chữ số thứ hai.
    """
    rooms = tuple(room.model_copy(update={"area_m2": float(polygon_area_m2(room.outline))}) for room in layer.rooms)
    return layer if rooms == layer.rooms else layer.model_copy(update={"rooms": rooms})


def _next_layer(request: _Request, current: FloorDocument, scale: _Scale) -> _Next:
    """Bước 7-8: nền (lớp hiện tại, đã đổi tỉ lệ nếu cần) rồi lớp mới của một trong ba đường."""
    base = current.layer if scale.factor is None else _rescaled_layer(current.layer, scale.factor)
    if request.merge is not None:
        outcome = request.merge(base, scale.value)
        _check_candidate(outcome.layer, level_id=request.level_id)
        return _Next(_with_areas(outcome.layer), outcome.id_map)
    if request.body.layer is not None:
        sent = request.body.layer if scale.factor is None else _rescaled_layer(request.body.layer, scale.factor)
        return _Next(_with_areas(sent), {})
    return _Next(_with_areas(base), {})


def _next_dimensions(
    request: _Request, current: FloorDocument, scale: _Scale, nxt: _Next
) -> tuple[tuple[Dimension, ...], tuple[Dimension, ...]]:
    """Bước 9: kích thước mới, và những mục vừa bị gỡ id (chúng sinh dòng nhật ký ở bước 13)."""
    sent = request.body.dimensions
    if sent is not None:
        dimensions = _sent_dimensions(sent, request.body.scale_mm_per_px, scale.value)
        dimensions = _remap_refs(dimensions, nxt.id_map) if nxt.id_map else dimensions
    elif scale.factor is None:
        dimensions = current.dimensions
    else:
        dimensions = _rescaled_dimensions(current.dimensions, scale.factor)
    return _drop_missing_refs(dimensions, entity_ids(nxt.layer))


def _sent_dimensions(
    dimensions: tuple[Dimension, ...], sent_scale: Decimal | None, target: Decimal | None
) -> tuple[Dimension, ...]:
    """Kích thước người gọi gửi, đưa từ hệ tỉ lệ của thân về hệ tỉ lệ đích."""
    if sent_scale is None or target is None or sent_scale == target:
        return dimensions
    return _rescaled_dimensions(dimensions, (float(sent_scale), float(target)))


def _remap_refs(dimensions: tuple[Dimension, ...], id_map: Mapping[str, str]) -> tuple[Dimension, ...]:
    """Đổi `referenceIds` theo bảng id của `merge`: mục AI bị bỏ trỏ sang mục được giữ."""
    return tuple(
        item.model_copy(update={"reference_ids": tuple(id_map.get(ref, ref) for ref in item.reference_ids)})
        for item in dimensions
    )


def _drop_missing_refs(
    dimensions: tuple[Dimension, ...], live: frozenset[str]
) -> tuple[tuple[Dimension, ...], tuple[Dimension, ...]]:
    """Gỡ khỏi `referenceIds` mọi id không còn trong lớp; trả `(kích thước mới, mục đã đổi)`."""
    kept: list[Dimension] = []
    touched: list[Dimension] = []
    for item in dimensions:
        refs = tuple(ref for ref in item.reference_ids if ref in live)
        if refs == item.reference_ids:
            kept.append(item)
            continue
        changed = item.model_copy(update={"reference_ids": refs})
        kept.append(changed)
        touched.append(changed)
    return tuple(kept), tuple(touched)


def _unchanged(current: FloorDocument, document: Mapping[str, object], scale: _Scale) -> bool:
    """Bước 10: jsonb, tỉ lệ, nguồn và trang đều như cũ → không `UPDATE`, không nhật ký, không đếm."""
    return (
        document == document_to_json(current.layer, (), current.dimensions)
        and scale.value == current.scale_mm_per_px
        and scale.source == current.scale_source
        and scale.page_key == current.scale_page_key
    )


async def _commit(
    db: AsyncSession,
    request: _Request,
    current: FloorDocument,
    *,
    expected: int,
    nxt: _Next,
    document: Mapping[str, object],
    scale: _Scale,
    touched: tuple[Dimension, ...],
) -> WriteResult | None:
    """Bước 11-15 trong một SAVEPOINT; `None` = `UPDATE` ăn 0 dòng, lượt này thua đua."""
    async with db.begin_nested() as savepoint:
        if not await _bump(db, request, expected=expected, document=document, scale=scale):
            await savepoint.rollback()
            return None
        await _claim(db, request, current=current, layer=nxt.layer)
        await _write_log(db, request, revision=expected + 1, old=current.layer, new=nxt.layer, touched=touched)
        counts = layer_counts(nxt.layer)
        await set_layer_counts(
            db,
            project_id=request.project_id,
            floor_level_id=request.level_id,
            walls_total=counts.walls_total,
            walls_reviewed=counts.walls_reviewed,
            area_m2=counts.area_m2,
        )
        await touch_project(db, project_id=request.project_id, clock=request.clock)
    return WriteResult(expected + 1, nxt.layer, applied=True)


async def _bump(
    db: AsyncSession, request: _Request, *, expected: int, document: Mapping[str, object], scale: _Scale
) -> bool:
    """Bước 11: `UPDATE … WHERE revision = :expected` (K07); `False` khi không ăn dòng nào.

    `last_base_revision` giữ bản ghi **gốc** người dùng cầm, không phải `expected`: C09b
    so đúng con số ấy để nhận ra lượt gửi lại của cùng một thân sau khi đã nhận diff rỗng.
    """
    result = await db.execute(
        update(FloorDocumentRow)
        .where(FloorDocumentRow.floor_pk == request.floor_pk, FloorDocumentRow.revision == expected)
        .values(
            revision=expected + 1,
            document=document,
            scale_mm_per_px=scale.value,
            scale_source=scale.source,
            scale_page_key=scale.page_key,
            last_writer_id=request.actor_id,
            last_body_sha256=body_sha256(request.body),
            last_base_revision=expected if request.merge is not None else request.base_revision,
            updated_at=request.clock.now(),
        )
        .returning(FloorDocumentRow.revision)
    )
    return result.scalar_one_or_none() is not None


async def _claim(db: AsyncSession, request: _Request, *, current: FloorDocument, layer: SpatialLayer) -> None:
    """Bước 12: nhận id mới, trả id vừa bỏ; id nào không nhận được → 422 kèm số id."""
    before, after = entity_ids(current.layer), entity_ids(layer)
    lost = await claim_entity_ids(
        db,
        project_id=request.project_id,
        floor_pk=request.floor_pk,
        removed=before - after,
        added=after - before,
        clock=request.clock,
    )
    if lost:
        raise LAYER_INTEGRITY_BROKEN.error(count=len(lost))


def _touch_marks(old: SpatialLayer, new: SpatialLayer) -> list[FieldChange]:
    """Dấu chạm: thực thể có ở cả hai lớp mà JSON khác nhau, một dòng ở trường đại diện.

    Chỉ dùng khi `diff_layers` rỗng mà hai lớp vẫn khác (đổi `reviewed`, `confidence`…):
    không có dòng nào thì người thứ hai sẽ thấy chẳng ai đổi gì và ghi đè việc duyệt.
    """
    before = {entity.id: entity for entity in old.entities()}
    marks: list[FieldChange] = []
    for entity in new.entities():
        previous = before.get(entity.id)
        if previous is None or previous == entity:
            continue
        entity_type = change_entity_type(entity)
        field = _TOUCH_FIELD[entity_type]
        marks.append(FieldChange(entity.id, entity_type, field, entity.model_dump(mode="json")[field]))
    return marks


async def _write_log(
    db: AsyncSession,
    request: _Request,
    *,
    revision: int,
    old: SpatialLayer,
    new: SpatialLayer,
    touched: tuple[Dimension, ...],
) -> None:
    """Bước 13: một lô `INSERT` vào `floor_change_log`; không có gì đổi thì không câu nào."""
    changes = diff_layers(old, new)
    if not changes and has_untracked_changes(old, new):
        changes = _touch_marks(old, new)
    changes += [FieldChange(item.id, "dimension", "reference_ids", list(item.reference_ids)) for item in touched]
    if not changes:
        return
    now = request.clock.now()
    await db.execute(
        insert(FloorChangeLogRow),
        [
            {
                "floor_pk": request.floor_pk,
                "revision": revision,
                "entity_type": change.entity_type,
                "entity_id": change.entity_id,
                "field": change.field,
                "value": None if change.value is MISSING else change.value,
                "removed": change.value is MISSING,
                "changed_at": now,
                "changed_by": request.actor_id,
                "changed_by_name": request.actor_name,
                "created_at": now,
                "updated_at": now,
            }
            for change in changes
        ],
    )
