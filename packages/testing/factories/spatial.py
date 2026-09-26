"""Factory dữ liệu không gian cho test (B3-02 [10]), theo mẫu `packages/testing/factories/floors.py`.

Dựng **từ** bộ mẫu A14 (`sample_layer`, `sample_building`) rồi đổi tên id, không chép lại
toạ độ: một bộ dữ liệu duy nhất cho FE, seed và test, nên số đo của test luôn là số đo thật.

`id_suffix` giải bài "hai tầng cùng một dự án": id thực thể là duy nhất **toàn dự án**
(W4), mà mẫu A14 dùng cùng bộ id cho mọi tầng. Hậu tố nối vào **thân** id và vào **mọi
tham chiếu** (`wallId`, `roomId`, `openingIds`, `wallIds`, `referenceIds`), nên lớp sau
khi đổi vẫn tự nhất quán.

Ghi thẳng bảng, chỉ `flush` như `make_floor`: test còn ghi tiếp trong cùng giao dịch.
"""

import re
from collections.abc import Sequence
from decimal import Decimal
from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.spatial_read.codec import document_to_json, entity_ids
from packages.core.clock import Clock
from packages.core.errors import MISSING
from packages.db.models.floors import FloorRow
from packages.db.models.spatial import FloorChangeLogRow, FloorDocumentRow, FloorEntityIdRow
from packages.domain.spatial import Dimension, FieldChange, SpatialLayer, sample_building, sample_layer

MAX_ID_BODY: Final = 64
"""Thân id W4 tối đa 64 ký tự (`packages.core.ids.is_spatial_id`)."""

_SUFFIX_RE: Final = re.compile(r"[0-9A-Z]*")
_ID_KEYS: Final = ("id", "wallId", "roomId")
_ID_LIST_KEYS: Final = ("openingIds", "wallIds", "referenceIds")
_HUMAN: Final[dict[str, Any]] = {"source": "human", "reviewed": True}


def _suffixed(entity_id: str, suffix: str) -> str:
    """`W-WALL0000000` + `Z` → `W-WALL0000000Z`; thân vượt 64 ký tự → `ValueError`."""
    prefix, _, body = entity_id.partition("-")
    if len(body) + len(suffix) > MAX_ID_BODY:
        raise ValueError(f"thân id {body + suffix!r} dài quá {MAX_ID_BODY} ký tự")
    return f"{prefix}-{body}{suffix}"


def _check_suffix(suffix: str) -> str:
    """Hậu tố phải là `[0-9A-Z]*` — ký tự khác sẽ dựng ra id không qua nổi mẫu W4."""
    if _SUFFIX_RE.fullmatch(suffix) is None:
        raise ValueError(f"id_suffix phải là [0-9A-Z]*: {suffix!r}")
    return suffix


def _remap(item: dict[str, Any], *, level_id: str, suffix: str, reviewed: bool) -> dict[str, Any]:
    """Đổi id và tham chiếu của **một** mục dạng dây; `levelId` thay hẳn bằng tầng đích."""
    out = dict(item)
    for key in _ID_KEYS:
        if key in out:
            out[key] = _suffixed(out[key], suffix)
    for key in _ID_LIST_KEYS:
        if key in out:
            out[key] = [_suffixed(value, suffix) for value in out[key]]
    if "levelId" in out:
        out["levelId"] = level_id
    return out | _HUMAN if reviewed else out


def sample_floor_layer(level_index: int, *, level_id: str, reviewed: bool = False, id_suffix: str = "") -> SpatialLayer:
    """Lớp của tầng mẫu `level_index` (0..3), gắn vào `level_id` thật; `reviewed=True` → mọi mục do người duyệt."""
    suffix = _check_suffix(id_suffix)
    raw = sample_layer(level_index).model_dump(mode="json", by_alias=True, exclude_none=True)
    return SpatialLayer.model_validate(
        {
            name: [_remap(item, level_id=level_id, suffix=suffix, reviewed=reviewed) for item in items]
            for name, items in raw.items()
        }
    )


def sample_floor_dimensions(level_index: int, *, level_id: str, id_suffix: str = "") -> tuple[Dimension, ...]:
    """Kích thước của tầng mẫu `level_index` (mẫu A14 rải 34 chuỗi đều cho 4 tầng)."""
    suffix = _check_suffix(id_suffix)
    source_level = sample_building().levels[level_index].id
    return tuple(
        Dimension.model_validate(
            _remap(
                dimension.model_dump(mode="json", by_alias=True, exclude_none=True),
                level_id=level_id,
                suffix=suffix,
                reviewed=False,
            )
        )
        for dimension in sample_building().dimensions
        if dimension.level_id == source_level
    )


async def make_floor_document(
    db: AsyncSession,
    *,
    floor_pk: int,
    layer: SpatialLayer | None = None,
    dimensions: Sequence[Dimension] = (),
    revision: int = 0,
    scale: Decimal | None = None,
    scale_source: str = "none",
    scale_page_key: str | None = None,
    clock: Clock,
) -> FloorDocumentRow:
    """Một dòng `floor_documents` đã `flush`, kèm đủ dòng `floor_entity_ids` của lớp.

    Ghi qua `codec.document_to_json` chứ không dựng dict tay: test do đó không thể tạo ra
    một tài liệu mà đường đọc thật từ chối (trừ khi test cố ý ghi bằng SQL trần).
    """
    content = layer if layer is not None else SpatialLayer(walls=(), openings=(), rooms=(), furniture=())
    now = clock.now()
    row = FloorDocumentRow(
        floor_pk=floor_pk,
        revision=revision,
        schema_version=1,
        document=document_to_json(content, (), dimensions),
        scale_mm_per_px=scale,
        scale_source=scale_source,
        scale_page_key=scale_page_key,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    project_id = (await db.execute(select(FloorRow.project_id).where(FloorRow.pk == floor_pk))).scalar_one()
    db.add_all(
        FloorEntityIdRow(project_id=project_id, entity_id=entity_id, floor_pk=floor_pk, created_at=now, updated_at=now)
        for entity_id in sorted(entity_ids(content))
    )
    await db.flush()
    return row


async def make_change_rows(
    db: AsyncSession,
    *,
    floor_pk: int,
    revision: int,
    changes: Sequence[FieldChange],
    changed_by: str,
    changed_by_name: str,
    clock: Clock,
) -> list[FloorChangeLogRow]:
    """Nhật ký của một lượt ghi giả (B3-03 mới là người ghi thật); `value is MISSING` → dòng `removed`."""
    now = clock.now()
    rows = [
        FloorChangeLogRow(
            floor_pk=floor_pk,
            revision=revision,
            entity_type=change.entity_type,
            entity_id=change.entity_id,
            field=change.field,
            value=None if change.value is MISSING else change.value,
            removed=change.value is MISSING,
            changed_at=now,
            changed_by=changed_by,
            changed_by_name=changed_by_name,
            created_at=now,
            updated_at=now,
        )
        for change in changes
    ]
    db.add_all(rows)
    await db.flush()
    return rows
