"""`readiness` của N16: tầng "chạy xong" khác tầng "dùng được" (FIX-P0-10, thiết kế H5 §2.2).

Tính **lúc đọc**, không lưu: luật nằm một chỗ ở `readiness_of` (hàm thuần), dữ kiện của lượt
lấy bằng **một** truy vấn ở `latest_run_facts`. Lý do cấp lượt (`criticalIssues`,
`fallback*Model`) tắt bằng chính `level_reviewed` của `Level.reviewed` — không thêm định nghĩa
"đã kiểm" thứ hai. `scaleUnresolved` chỉ tắt khi tỉ lệ thật sự là `human` (đã chấm hạng theo
trang, cùng nguồn với `scaleStatus`).

Module này nhập được trong ngữ cảnh worker: không `fastapi`, không `starlette`.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.spatial_read.assemble import level_reviewed, scale_status
from apps.api.spatial_read.documents import ScaleSource
from apps.api.spatial_read.wire import ReadinessOut, ReadinessReason
from packages.db.models.drawings import PipelineRunRow
from packages.db.models.pipeline_orchestrate import PipelineRunModelsRow
from packages.domain.spatial import SpatialLayer
from packages.ml_contracts.families import ModelFamily
from packages.ml_contracts.payloads import ModelRef

_FALLBACK_REASONS: Final[tuple[tuple[ModelFamily, ReadinessReason], ...]] = (
    ("wallSegmentation", "fallbackWallModel"),
    ("openingAndFurnitureDetection", "fallbackObjectModel"),
    ("dimensionReading", "fallbackTextModel"),
)
"""Họ model → lý do khi họ ấy chạy bằng ref cổ điển; thứ tự này là thứ tự trên dây."""


@dataclass(frozen=True, slots=True)
class RunFacts:
    """Dữ kiện của lượt `completed` mới nhất: `pinned` thô (JSONB) và tóm tắt quality (có thể `None`)."""

    pinned: Mapping[str, object]
    quality_summary: Mapping[str, object] | None


def _is_classic(value: object) -> bool:
    """Ref ghim là cổ điển (`pinned_name`, `weights_key` đều trống) — đọc qua `ModelRef` như `load_pins`."""
    return ModelRef.model_validate(value).is_classic


def readiness_of(
    *,
    run: RunFacts | None,
    scale_source: ScaleSource,
    layer: SpatialLayer,
) -> ReadinessOut:
    """Luật H5 §2.2: `notEvaluated` khi chưa có lượt; còn lý do → `needsReview`; hết → `ready`.

    `scaleUnresolved` là dữ kiện của tầng nên vẫn báo cả khi chưa có lượt. Tóm tắt `NULL` (lượt
    cũ, trước FIX-P0-08) không sinh `criticalIssues`; họ vắng trong `pinned` không sinh lý do.
    """
    reasons: list[ReadinessReason] = []
    if scale_status(scale_source) == "unresolved":
        reasons.append("scaleUnresolved")
    if run is not None and not level_reviewed(layer, scale_source):
        if run.quality_summary is not None and run.quality_summary.get("hasCritical") is True:
            reasons.append("criticalIssues")
        reasons.extend(
            reason for family, reason in _FALLBACK_REASONS if family in run.pinned and _is_classic(run.pinned[family])
        )
    if run is None:
        return ReadinessOut(state="notEvaluated", reasons=tuple(reasons))
    return ReadinessOut(state="needsReview" if reasons else "ready", reasons=tuple(reasons))


async def latest_run_facts(db: AsyncSession, floor_pk: int) -> RunFacts | None:
    """Lượt `completed` mới nhất chưa bị thay của tầng, join `pipeline_run_models`; chưa có → `None`.

    Join trái: lượt xong mà không có dòng ghim (dữ liệu trước B5-06a) vẫn là "đã có lượt", chỉ
    không có lý do cấp lượt nào.
    """
    stmt = (
        select(PipelineRunModelsRow.pinned, PipelineRunModelsRow.quality_summary)
        .select_from(PipelineRunRow)
        .outerjoin(PipelineRunModelsRow, PipelineRunModelsRow.run_id == PipelineRunRow.id)
        .where(
            PipelineRunRow.floor_pk == floor_pk,
            PipelineRunRow.status == "completed",
            PipelineRunRow.superseded_by.is_(None),
        )
        .order_by(PipelineRunRow.created_at.desc(), PipelineRunRow.id.desc())
        .limit(1)
    )
    row = (await db.execute(stmt)).one_or_none()
    if row is None:
        return None
    pinned, quality_summary = row
    return RunFacts(pinned=pinned or {}, quality_summary=quality_summary)
