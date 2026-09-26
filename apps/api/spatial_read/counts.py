"""Đếm tường và diện tích của một tầng, và đối chiếu lại bảng đếm (B3-02 [6]).

`layer_counts` là hàm thuần và là **nguồn duy nhất** của ba con số: B3-03 gọi khi ghi,
seed gọi khi dựng, lịch đối chiếu gọi khi dò lệch. Bảng `project_floor_summaries` chỉ ghi
qua `summaries.set_layer_counts` (K của [9]) — module này không bao giờ `UPDATE` thẳng.

`recount_floor` khoá `floors FOR SHARE` rồi `floor_documents FOR SHARE`, đúng thứ tự
tầng → tài liệu của BE-00 §7: khoá chia sẻ đủ để chặn người ghi đổi tài liệu giữa lúc
đếm mà vẫn để nhiều lượt đối chiếu chạy song song. Không `touch_project`: đối chiếu là
việc sửa sổ sách trong nhà, không phải một thay đổi người dùng thấy.
"""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.projects.summaries import set_layer_counts
from apps.api.spatial_read.documents import document_from_row
from packages.core.clock import Clock
from packages.db.models.floors import FloorRow
from packages.db.models.projects import ProjectFloorSummary
from packages.db.models.spatial import FloorDocumentRow
from packages.domain.spatial import SpatialLayer, total_area_m2


@dataclass(frozen=True)
class LayerCounts:
    """Ba con số của một tầng; `area_m2=None` là "tầng chưa có phòng nào", khác với 0 m²."""

    walls_total: int
    walls_reviewed: int
    area_m2: Decimal | None


_EMPTY_COUNTS = LayerCounts(walls_total=0, walls_reviewed=0, area_m2=None)
"""Tầng chưa có tài liệu — cùng con số với một tài liệu có lớp rỗng."""


def layer_counts(layer: SpatialLayer) -> LayerCounts:
    """Số tường, số tường đã duyệt và tổng diện tích các phòng (cộng mm² rồi làm tròn một lần)."""
    return LayerCounts(
        walls_total=len(layer.walls),
        walls_reviewed=sum(1 for wall in layer.walls if wall.reviewed),
        area_m2=total_area_m2([room.outline for room in layer.rooms]) if layer.rooms else None,
    )


async def recount_floor(db: AsyncSession, *, floor_pk: int, clock: Clock) -> bool:
    """Đếm lại một tầng và ghi bảng đếm khi lệch; `True` = đã ghi.

    Tầng đã xoá mềm (hay không còn) → `False`, không đụng dòng đếm: `unregister_floor` đã
    ẩn nó và giữ số cho lượt khôi phục. Tầng chưa có tài liệu đếm ra `(0, 0, None)` chứ
    không bị bỏ qua — bảng đếm còn số cũ của một tài liệu đã bị xoá thì vẫn phải về 0.
    """
    floor = (
        await db.execute(
            select(FloorRow).where(FloorRow.pk == floor_pk, FloorRow.deleted_at.is_(None)).with_for_update(read=True)
        )
    ).scalar_one_or_none()
    if floor is None:
        return False
    row = (
        await db.execute(
            select(FloorDocumentRow).where(FloorDocumentRow.floor_pk == floor_pk).with_for_update(read=True)
        )
    ).scalar_one_or_none()
    counts = _EMPTY_COUNTS if row is None else layer_counts(document_from_row(row).layer)

    # `Row` là tuple nên so thẳng với bộ ba mới: dòng chưa có (`None`) không bao giờ bằng,
    # và `Decimal("238.00") == Decimal("238.00")` bất kể cách viết (cột là `numeric(12,2)`).
    current = (
        await db.execute(
            select(
                ProjectFloorSummary.walls_total,
                ProjectFloorSummary.walls_reviewed,
                ProjectFloorSummary.area_m2,
            ).where(
                ProjectFloorSummary.project_id == floor.project_id,
                ProjectFloorSummary.floor_level_id == floor.level_id,
            )
        )
    ).first()
    if current == (counts.walls_total, counts.walls_reviewed, counts.area_m2):
        return False
    await set_layer_counts(
        db,
        project_id=floor.project_id,
        floor_level_id=floor.level_id,
        walls_total=counts.walls_total,
        walls_reviewed=counts.walls_reviewed,
        area_m2=counts.area_m2,
    )
    return True
