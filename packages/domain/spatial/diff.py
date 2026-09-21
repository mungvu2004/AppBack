"""Diff theo trường giữa hai lớp một tầng, đúng bảng tên HOP-DONG-MOI §1.3 (B3-03 ghi nhật ký, F-08 đọc).

Khoá so là `(entity_type, entity_id, field)`; giá trị là `model_dump(mode="json")`
của trường, hoặc `MISSING` khi trường vắng. Chỉ trường trong bảng được theo dõi;
đổi trường ngoài bảng (`reviewed`, `confidence`…) thì `diff_layers` rỗng và
`has_untracked_changes` báo lại, để B3-03 không coi đó là "không có gì đổi".
Id trùng trong một lớp làm diff mất mục: B3-03 kiểm toàn vẹn trước khi diff.
"""

from dataclasses import dataclass
from typing import Final

from packages.core.errors import MISSING
from packages.domain.spatial.kinds import ChangeEntityType, change_entity_type, vertex_id
from packages.domain.spatial.model import Furniture, Opening, Room, SpatialLayer, Wall

DELETED: Final = "__deleted__"
"""`field` của mục xoá thực thể; mục đó không có `value` (trên dây: vắng khoá)."""

_TRACKED_FIELDS: Final[dict[type[Wall | Opening | Room | Furniture], tuple[str, ...]]] = {
    Wall: ("thickness_mm", "height_mm", "kind"),
    Opening: ("width_mm", "height_mm", "sill_height_mm", "offset_mm", "swing", "wall_id"),
    Room: ("name", "usage", "outline"),
    Furniture: ("kind", "centre", "rotation_deg", "room_id"),
}

_Snapshot = dict[tuple[ChangeEntityType, str], dict[str, object]]


@dataclass(frozen=True, slots=True)
class FieldChange:
    """Một dòng nhật ký: giá trị JSON mới của trường, hoặc `MISSING` khi trường bị gỡ hay thực thể bị xoá."""

    entity_id: str
    entity_type: ChangeEntityType
    field: str
    value: object


def _snapshot(layer: SpatialLayer) -> _Snapshot:
    """Trường theo dõi của mọi thực thể, theo thứ tự lớp; hai đầu tường là thực thể `vertex` ngay sau tường."""
    snapshot: _Snapshot = {}
    for entity in layer.entities():
        names = _TRACKED_FIELDS[type(entity)]
        dumped = entity.model_dump(mode="json", include=set(names))
        snapshot[(change_entity_type(entity), entity.id)] = {
            name: MISSING if dumped[name] is None else dumped[name] for name in names
        }
        if isinstance(entity, Wall):
            line = entity.centreline
            for key, point in ((vertex_id(entity.id, "start"), line.start), (vertex_id(entity.id, "end"), line.end)):
                snapshot[("vertex", key)] = {"x": point.x, "y": point.y}
    return snapshot


def diff_layers(old: SpatialLayer, new: SpatialLayer) -> list[FieldChange]:
    """Các trường đổi từ `old` sang `new`.

    Duyệt `new` theo thứ tự lớp: thực thể mới cho một mục mỗi trường có giá trị
    (tường thêm bốn mục đỉnh), thực thể cũ cho mục mỗi trường khác giá trị. Rồi
    thực thể có ở `old` mà không có ở `new` cho một mục `__deleted__`, theo thứ tự
    `old`. Ô mở đổi `door ↔ window` là xoá dưới loại cũ + tạo dưới loại mới.
    """
    before, after = _snapshot(old), _snapshot(new)
    changes: list[FieldChange] = []
    for (entity_type, entity_id), fields in after.items():
        previous = before.get((entity_type, entity_id), {})
        changes += [
            FieldChange(entity_id, entity_type, field, value)
            for field, value in fields.items()
            if value != previous.get(field, MISSING)
        ]
    changes += [
        FieldChange(entity_id, entity_type, DELETED, MISSING)
        for entity_type, entity_id in before
        if (entity_type, entity_id) not in after
    ]
    return changes


def has_untracked_changes(old: SpatialLayer, new: SpatialLayer) -> bool:
    """Hai lớp khác nhau mà `diff_layers` rỗng: chỉ đổi trường ngoài bảng (duyệt, tin cậy, hộp bao…) hay thứ tự."""
    return old != new and not diff_layers(old, new)
