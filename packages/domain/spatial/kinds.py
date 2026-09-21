"""Loại thực thể, `entityType` của nhật ký thay đổi (HOP-DONG-MOI §1.3) và phát hiện A5 (W5).

Bảng tiền tố và danh sách `entityType` là của lõi (`packages.core.ids`,
`packages.core.errors`); ở đây chỉ xuất lại, không khai bảng thứ hai.
"""

from collections.abc import Iterator
from typing import Final, Literal, overload

from packages.core.errors import VersionEntityType as ChangeEntityType
from packages.core.ids import SPATIAL_PREFIX as ID_PREFIX_BY_KIND
from packages.core.ids import SpatialKind as EntityKind
from packages.domain.spatial.model import (
    Dimension,
    Furniture,
    Opening,
    Reviewed,
    Room,
    SpatialGraph,
    SpatialLayer,
    Wall,
)

__all__ = [
    "BUILDING_ID",
    "ID_PREFIX_BY_KIND",
    "ChangeEntityType",
    "EntityKind",
    "ai_reviewed_ids",
    "change_entity_type",
    "vertex_id",
]

BUILDING_ID: Final = "building"
"""Id giả của `Building` (không có id trên dây) khi cần nêu tên nó trong kết quả."""

_CHANGE_TYPE_BY_MODEL: Final[dict[type[object], ChangeEntityType]] = {
    Wall: "wall",
    Furniture: "furniture",
    Room: "room",
    Dimension: "dimension",
}


@overload
def change_entity_type(entity: Wall | Opening | Room | Furniture | Dimension) -> ChangeEntityType: ...
@overload
def change_entity_type(entity: object) -> ChangeEntityType | None: ...
def change_entity_type(entity: object) -> ChangeEntityType | None:
    """`entityType` của nhật ký thay đổi; ô mở theo đúng `kind` (`door`/`window`).

    `Level`, `Axis`, `Note`, `Building` không có dòng nhật ký nên trả `None`.
    """
    if isinstance(entity, Opening):
        return entity.kind
    return _CHANGE_TYPE_BY_MODEL.get(type(entity))


def vertex_id(wall_id: str, end: Literal["start", "end"]) -> str:
    """Id của một đầu tường trong nhật ký (`V-<wallId>-start`), không phải id W4."""
    return f"V-{wall_id}-{end}"


def _entities(obj: SpatialLayer | SpatialGraph) -> Iterator[Reviewed]:
    """Mọi thực thể theo thứ tự khai trường của mô hình, rồi thứ tự trong từng danh sách."""
    for name in type(obj).model_fields:
        value = getattr(obj, name)
        yield from value if isinstance(value, tuple) else (value,)


def ai_reviewed_ids(obj: SpatialLayer | SpatialGraph) -> tuple[str, ...]:
    """Id (theo thứ tự xuất hiện) của mọi thực thể vi phạm A5: `source="ai"` kèm `reviewed=True`.

    Gói này chỉ phát hiện; B3-03 đổi kết quả khác rỗng thành 422 `REVIEW_BY_AI_FORBIDDEN`.
    """
    return tuple(
        str(getattr(entity, "id", BUILDING_ID))
        for entity in _entities(obj)
        if entity.source == "ai" and entity.reviewed
    )
