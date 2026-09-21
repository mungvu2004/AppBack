"""Đổi tỉ lệ cho mục chưa duyệt khi người hiệu chỉnh tỉ lệ tầng (#35) hay khôi phục phiên bản (N19).

`k = new / old`; mọi độ dài **trên mặt bằng** của thực thể `reviewed=False` (của AI
lẫn do người vẽ) thành `js_round(v x k)`: toạ độ đường tim, đường bao, tâm, hộp
bao, `line`; bề dày; `offsetMm`, `widthMm`. Chiều cao, góc, tin cậy giữ nguyên.
Thực thể đã duyệt giữ nguyên từng trường (K21); gói này không bao giờ đặt
`reviewed=True`. Kết quả vi phạm mô hình → `RescaleError`, không kẹp giá trị.
"""

import math
from collections.abc import Callable, Mapping, Sequence

from packages.domain.spatial.area import js_round, polygon_area_m2
from packages.domain.spatial.model import Dimension, Furniture, Opening, Point, Room, Segment, SpatialLayer, Wall


class RescaleError(ValueError):
    """Đổi tỉ lệ làm một thực thể sai mô hình (tường dài 0, bề dày 0, `line` trùng điểm…)."""

    def __init__(self, entity_id: str) -> None:
        """`entity_id` là id thực thể hỏng; B3-03, B3-04 đọc nó để dựng lỗi trả người gọi."""
        super().__init__(f"đổi tỉ lệ làm hỏng thực thể {entity_id}")
        self.entity_id = entity_id


def _factor(old: float, new: float) -> float:
    """Tỉ số `new / old`; hai tỉ lệ và cả tỉ số phải hữu hạn và > 0, không thì `ValueError`.

    Kiểm cả tỉ số: hai tỉ lệ hợp lệ vẫn có thể cho thương tràn vô cực hay chìm về 0,
    và đó là lỗi của tham số, không phải của thực thể đầu tiên bị đổi.
    """
    if not all(math.isfinite(scale) and scale > 0 for scale in (old, new)):
        raise ValueError(f"tỉ lệ phải hữu hạn và > 0: old={old}, new={new}")
    k = new / old
    if not (math.isfinite(k) and k > 0):
        raise ValueError(f"tỉ số tỉ lệ new/old tràn hoặc bằng 0: old={old}, new={new}")
    return k


def _mm(value: int, k: float) -> int:
    """Một độ dài sau khi đổi tỉ lệ."""
    return js_round(value * k)


def _point(point: Point, k: float) -> Point:
    """Điểm sau khi đổi tỉ lệ."""
    return Point(x=_mm(point.x, k), y=_mm(point.y, k))


def _segment(segment: Segment, k: float) -> Segment:
    """Đoạn thẳng sau khi đổi tỉ lệ; về một điểm thì mô hình ném."""
    return Segment(start=_point(segment.start, k), end=_point(segment.end, k))


def _wall(wall: Wall, k: float) -> Mapping[str, object]:
    """Đường tim và bề dày; `heightMm` là chiều đứng nên giữ."""
    return {"centreline": _segment(wall.centreline, k), "thickness_mm": _mm(wall.thickness_mm, k)}


def _opening(opening: Opening, k: float) -> Mapping[str, object]:
    """Vị trí và bề rộng dọc tường; chiều cao, cao bậu giữ."""
    return {"offset_mm": _mm(opening.offset_mm, k), "width_mm": _mm(opening.width_mm, k)}


def _room(room: Room, k: float) -> Mapping[str, object]:
    """Đường bao, và `areaM2` tính lại từ đường bao mới."""
    outline = tuple(_point(point, k) for point in room.outline)
    return {"outline": outline, "area_m2": float(polygon_area_m2(outline))}


def _furniture(item: Furniture, k: float) -> Mapping[str, object]:
    """Tâm và hộp bao; góc xoay giữ."""
    box = item.bounding_box
    return {"centre": _point(item.centre, k), "bounding_box": {"min": _point(box.min, k), "max": _point(box.max, k)}}


def _dimension(dimension: Dimension, k: float) -> Mapping[str, object]:
    """Chỉ `line`; `valueMm`, `overrideValueMm`, `referenceIds` là số đọc được, giữ."""
    return {"line": _segment(dimension.line, k)}


def _rescaled[E: (Wall, Opening, Room, Furniture, Dimension)](
    entity: E, k: float, updates: Callable[[E, float], Mapping[str, object]]
) -> E:
    """Thực thể chưa duyệt sau khi đổi tỉ lệ, kiểm lại trọn mô hình; đã duyệt thì trả nguyên."""
    if entity.reviewed:
        return entity
    try:
        return type(entity).model_validate({**dict(entity), **updates(entity, k)})
    except ValueError as exc:
        raise RescaleError(entity.id) from exc


def rescale_unreviewed(layer: SpatialLayer, old: float, new: float) -> SpatialLayer:
    """Lớp sau khi đổi tỉ lệ `old → new` (mm/px); `old == new` trả nguyên lớp."""
    k = _factor(old, new)
    if old == new:
        return layer
    return SpatialLayer(
        walls=tuple(_rescaled(wall, k, _wall) for wall in layer.walls),
        openings=tuple(_rescaled(opening, k, _opening) for opening in layer.openings),
        rooms=tuple(_rescaled(room, k, _room) for room in layer.rooms),
        furniture=tuple(_rescaled(item, k, _furniture) for item in layer.furniture),
    )


def rescale_dimensions(dimensions: Sequence[Dimension], old: float, new: float) -> tuple[Dimension, ...]:
    """Kích thước sau khi đổi tỉ lệ, cùng luật với `rescale_unreviewed`; không có bản cho `Axis` (v1 luôn rỗng)."""
    k = _factor(old, new)
    return tuple(dimensions) if old == new else tuple(_rescaled(item, k, _dimension) for item in dimensions)
