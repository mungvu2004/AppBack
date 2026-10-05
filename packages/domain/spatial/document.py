"""Ba hàm thuần quanh một tầng, dùng chung cho API và seed (NO-220, R-07).

`document_to_json` là dạng dây của cột `floor_documents.document`, `layer_counts` là ba con số
của bảng đếm `project_floor_summaries`, `entity_ids` là tập id `floor_entity_ids` giữ cho tầng.
Chúng nằm ở miền thuần vì `packages.db` (seed) không được nhập `apps.api` (`.importlinter`
`db-isolated`); `apps.api.spatial_read.codec`/`counts` chỉ chuyển tiếp lại.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from packages.domain.spatial.area import total_area_m2
from packages.domain.spatial.model import Axis, Dimension, SpatialLayer


@dataclass(frozen=True)
class LayerCounts:
    """Ba con số của một tầng; `area_m2=None` là "tầng chưa có phòng nào", khác với 0 m²."""

    walls_total: int
    walls_reviewed: int
    area_m2: Decimal | None


def document_to_json(layer: SpatialLayer, axes: Sequence[Axis], dimensions: Sequence[Dimension]) -> dict[str, object]:
    """Dạng dây của một tài liệu. `axes` được nhận để chữ ký ổn định nhưng v1 luôn ghi `[]`."""
    return {
        "layer": layer.model_dump(mode="json", by_alias=True, exclude_none=True),
        "axes": [],
        "dimensions": [dimension.model_dump(mode="json", by_alias=True, exclude_none=True) for dimension in dimensions],
    }


def entity_ids(layer: SpatialLayer) -> frozenset[str]:
    """Id của mọi tường, ô mở, phòng, đồ đạc — đúng tập `floor_entity_ids` giữ cho tầng ấy (W4).

    **Không** gồm kích thước: `Dimension` là chú thích đo vẽ, B3-03 thêm bớt tự do và
    không tranh id với tầng khác. Toà mẫu A14 vì thế ra 48 + 16 + 21 + 14 = 99 id.
    """
    return frozenset(entity.id for entity in layer.entities())


def layer_counts(layer: SpatialLayer) -> LayerCounts:
    """Số tường, số tường đã duyệt và tổng diện tích các phòng (cộng mm² rồi làm tròn một lần)."""
    return LayerCounts(
        walls_total=len(layer.walls),
        walls_reviewed=sum(1 for wall in layer.walls if wall.reviewed),
        area_m2=total_area_m2([room.outline for room in layer.rooms]) if layer.rooms else None,
    )
