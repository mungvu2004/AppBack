"""Factory concept nội thất cho test (AID-01), theo mẫu `packages/testing/factories/lighting_bake.py`.

Ghi thẳng `design_concepts`, không qua N48: test cần mọi trạng thái. `input_key` mặc định ngẫu nhiên
(không đụng unique partial); truyền khoá thật (`state.compute_input_key`) để thử dùng lại. Có `commit`.
"""

import secrets
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.clock import SystemClock
from packages.core.ids import new_id
from packages.db.models.design_concept import DesignConceptRow

_STARTED = frozenset({"running", "done", "failed"})
_FINISHED = frozenset({"done", "failed"})

# Kết quả hợp lệ theo schema FE (`DesignResultSchema`): mẫu response của test qua được H1.
RESULT: dict[str, Any] = {
    "nameVi": "Japandi",
    "summaryVi": "Gỗ sáng, tường kem.",
    "baseStyle": "go-am",
    "wall": {"interior": "scene:paint-cream"},
    "floor": {"wood": "scene:oak", "tile": "scene:tile-grey", "mosaic": "scene:tile-grey"},
    "models": {},
    "additions": [],
}


async def make_design_concept(
    db: AsyncSession,
    *,
    project_id: str,
    status: str = "queued",
    style_id: str | None = None,
    suggested: bool = False,
    input_key: str | None = None,
    result: dict[str, Any] | None = None,
    created_by: str | None = None,
    created_at: datetime | None = None,
    started_at: datetime | None = None,
    selected_at: datetime | None = None,
) -> DesignConceptRow:
    """Một dòng `design_concepts` đã `commit`.

    `running|done|failed` tự đặt `started_at = created_at`; `done|failed` tự đặt `ended_at`; `failed` có mã
    `DESIGN_DIRECTOR_FAILED`; `done` có `result` `RESULT` và `style_id` `japandi` khi không truyền.
    """
    clock = SystemClock()
    at = created_at if created_at is not None else clock.now()
    start = started_at if started_at is not None or status not in _STARTED else at
    done = status == "done"
    row = DesignConceptRow(
        id=new_id("dcn", clock),
        project_id=project_id,
        style_id=style_id if style_id is not None or not done else "japandi",
        suggested=suggested,
        input_key=input_key if input_key is not None else secrets.token_hex(32),
        status=status,
        failure_code="DESIGN_DIRECTOR_FAILED" if status == "failed" else None,
        result=result if result is not None or not done else RESULT,
        usage={} if done else None,
        created_by=created_by,
        started_at=start,
        ended_at=(start or at) if status in _FINISHED else None,
        selected_at=selected_at,
        created_at=at,
        updated_at=at,
    )
    db.add(row)
    await db.commit()
    return row
