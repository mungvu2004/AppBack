"""Ba hàm chuyển trạng thái `lighting_bakes` — nguồn duy nhất cho worker `bake` và lịch quét.

"Hàm worker nhập" (BE-00 §7): SQL thuần trên session, không `apps.api.core`, không `fastapi`.
Không hàm nào `commit`: người gọi commit. Mỗi `UPDATE` lọc trạng thái nguồn, nên tin nhắn lặp
hay chuyển muộn (lượt đã `done|failed`) tự nhiên là no-op và trả `None`/`False`.
"""

from typing import Final

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.clock import Clock

LIGHTING_BAKE_FAILED: Final = "LIGHTING_BAKE_FAILED"
LIGHTING_BAKE_TIMEOUT: Final = "LIGHTING_BAKE_TIMEOUT"
LIGHTING_BAKE_OUTPUT_INVALID: Final = "LIGHTING_BAKE_OUTPUT_INVALID"
LIGHTING_BAKE_STALLED: Final = "LIGHTING_BAKE_STALLED"
FAILURE_CODES: Final = frozenset(
    (LIGHTING_BAKE_FAILED, LIGHTING_BAKE_TIMEOUT, LIGHTING_BAKE_OUTPUT_INVALID, LIGHTING_BAKE_STALLED)
)

_CLAIM: Final = text(
    "UPDATE lighting_bakes SET status = 'running', started_at = COALESCE(started_at, :now), updated_at = :now "
    "WHERE id = :id AND status IN ('queued', 'running') RETURNING project_id"
)
_FINISH: Final = text(
    "UPDATE lighting_bakes SET status = 'done', ended_at = :now, updated_at = :now "
    "WHERE id = :id AND status = 'running' RETURNING id"
)
_FAIL: Final = text(
    "UPDATE lighting_bakes SET status = 'failed', failure_code = :code, ended_at = :now, updated_at = :now "
    "WHERE id = :id AND status IN ('queued', 'running') RETURNING id"
)


async def claim(db: AsyncSession, bake_id: str, clock: Clock) -> str | None:
    """`queued|running` → `running`; trả `project_id`, hoặc `None` khi lượt không còn chạy được.

    Nhận cả `running`: worker chết giữa chừng và Celery giao lại thì lượt sau vẫn nhận được;
    `started_at` giữ mốc của lần nhận đầu để lịch quét đo trần 70 phút từ đó.
    """
    found = await db.execute(_CLAIM, {"id": bake_id, "now": clock.now()})
    project_id: str | None = found.scalar_one_or_none()
    return project_id


async def finish(db: AsyncSession, bake_id: str, clock: Clock) -> bool:
    """`running` → `done`; `False` khi lượt không còn `running` (đã hỏng, đã bị lịch quét chốt)."""
    found = await db.execute(_FINISH, {"id": bake_id, "now": clock.now()})
    return found.scalar_one_or_none() is not None


async def fail(db: AsyncSession, bake_id: str, code: str, clock: Clock) -> bool:
    """`queued|running` → `failed` với `code` ∈ `FAILURE_CODES`; `False` khi lượt đã kết thúc."""
    if code not in FAILURE_CODES:
        raise ValueError(f"mã hỏng lạ: {code!r}")
    found = await db.execute(_FAIL, {"id": bake_id, "code": code, "now": clock.now()})
    return found.scalar_one_or_none() is not None
