"""Factory lượt bake ánh sáng cho test (LB-01), theo mẫu `packages/testing/factories/admin_ml_jobs.py`.

Ghi thẳng `lighting_bakes`, không qua N42: test cần mọi trạng thái (`running` có `started_at`,
`failed` có `failure_code`, `done` có `ended_at`) mà một lượt API thật không dựng được.
Mỗi dự án chỉ một lượt `queued|running` (`uq_lighting_bakes_active`) — factory không né luật đó.

Có `commit`: route/worker đọc bằng session khác. `created_at`/`updated_at` đặt tường minh để
test "lượt mới nhất" và quét lượt treo xếp được thứ tự.
"""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.clock import SystemClock
from packages.core.errors import SYSTEM_PIPELINE
from packages.core.ids import new_id
from packages.db.models.lighting_bake import LightingBakeRow

_STARTED_STATUSES = frozenset({"running", "done", "failed"})
_FINISHED_STATUSES = frozenset({"done", "failed"})


async def make_lighting_bake(
    db: AsyncSession,
    *,
    project_id: str,
    status: str = "queued",
    failure_code: str | None = None,
    created_by: str | None = None,
    created_at: datetime | None = None,
    started_at: datetime | None = None,
    ended_at: datetime | None = None,
) -> LightingBakeRow:
    """Một dòng `lighting_bakes` đã `commit`.

    `running|done|failed` tự đặt `started_at = created_at` nếu không truyền; `done|failed` tự đặt
    `ended_at`; `failed` tự điền `failure_code` `LIGHTING_BAKE_FAILED`.
    """
    clock = SystemClock()
    at = created_at if created_at is not None else clock.now()
    start = started_at if started_at is not None or status not in _STARTED_STATUSES else at
    end = ended_at if ended_at is not None or status not in _FINISHED_STATUSES else (start or at)
    code = failure_code if failure_code is not None or status != "failed" else "LIGHTING_BAKE_FAILED"
    row = LightingBakeRow(
        id=new_id("bak", clock),
        project_id=project_id,
        created_by=created_by if created_by is not None else SYSTEM_PIPELINE,
        status=status,
        failure_code=code,
        started_at=start,
        ended_at=end,
        created_at=at,
        updated_at=at,
    )
    db.add(row)
    await db.commit()
    return row
