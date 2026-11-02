"""Trạng thái `design_concepts` — nguồn duy nhất cho N48, worker `design.director.run`, lịch quét và `enqueue_auto`.

"Hàm worker nhập" (BE-00 §7): SQL thuần trên session, không `apps.api.core`, không `fastapi`.
Không hàm nào `commit`: người gọi commit (task gửi bằng `on_after_commit`, K17). Mỗi `UPDATE` lọc
trạng thái nguồn, nên tin nhắn lặp hay chuyển muộn là no-op và trả `None`/`False`.
"""

import hashlib
import importlib
from dataclasses import dataclass
from datetime import UTC, datetime, time
from typing import Any, Final

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.design_director.settings import DesignDirectorSettings, get_design_director_settings
from packages.core.clock import Clock, SystemClock
from packages.core.ids import new_id
from packages.db.hooks import on_after_commit
from packages.db.models.design_concept import DESIGN_STYLE_IDS
from packages.messaging import send_task
from packages.messaging.payloads.design_director import DESIGN_DIRECTOR_TASK, DesignConceptPayload

DESIGN_DIRECTOR_FAILED: Final = "DESIGN_DIRECTOR_FAILED"
DESIGN_DIRECTOR_OUTPUT_INVALID: Final = "DESIGN_DIRECTOR_OUTPUT_INVALID"
DESIGN_DIRECTOR_STALLED: Final = "DESIGN_DIRECTOR_STALLED"
FAILURE_PREFIX: Final = "DESIGN_DIRECTOR_"
"""`fail` nhận mọi mã `DESIGN_DIRECTOR_*` (worker có thể chuyển mã `GenAIError` thành mã riêng)."""

AUTO_KEY: Final = "auto"

CONCEPT_COLUMNS: Final = "id, style_id, suggested, status, failure_code, created_at, started_at, ended_at, result"
"""Cột một concept trên dây (N47/N48 đọc)."""

_CLAIM: Final = text(
    "UPDATE design_concepts SET status = 'running', started_at = :now, updated_at = :now "
    "WHERE id = :id AND status IN ('queued', 'running') RETURNING project_id, style_id, suggested, input_key"
)
_FINISH: Final = text(
    "UPDATE design_concepts SET status = 'done', style_id = :style, result = :result, usage = :usage, "
    "ended_at = :now, updated_at = :now WHERE id = :id AND status = 'running' RETURNING id"
).bindparams(bindparam("result", type_=JSONB), bindparam("usage", type_=JSONB))
_FAIL: Final = text(
    "UPDATE design_concepts SET status = 'failed', failure_code = :code, ended_at = :now, updated_at = :now "
    "WHERE id = :id AND status IN ('queued', 'running') RETURNING id"
)
_FLOORS: Final = text(
    "SELECT f.level_id, COALESCE(d.revision, -1) FROM floors f LEFT JOIN floor_documents d ON d.floor_pk = f.pk "
    "WHERE f.project_id = :p AND f.deleted_at IS NULL ORDER BY f.level_id"
)
_LIBRARY: Final = text(
    "SELECT count(*), max(published_at) FROM library_items WHERE published_at IS NOT NULL AND retired_at IS NULL"
)
_REUSABLE: Final = text(
    f"SELECT {CONCEPT_COLUMNS} FROM design_concepts WHERE project_id = :p AND input_key = :k "  # noqa: S608 — hằng
    "AND status IN ('queued', 'running', 'done') ORDER BY created_at DESC, id DESC LIMIT 1"
)
_USED_TODAY: Final = text(
    "SELECT count(*) FROM design_concepts c JOIN projects p ON p.id = c.project_id "
    "WHERE p.created_by = (SELECT created_by FROM projects WHERE id = :p) AND c.created_at >= :since"
)
_INSERT: Final = text(
    "INSERT INTO design_concepts (id, project_id, style_id, suggested, input_key, status, created_by, "
    "selected_at, created_at, updated_at) "
    "VALUES (:id, :p, :style, :suggested, :k, 'queued', :by, :selected, :now, :now) "
    "ON CONFLICT (project_id, input_key) WHERE status IN ('queued', 'running') DO NOTHING RETURNING id"
)
_SELECT: Final = text("UPDATE design_concepts SET selected_at = :now, updated_at = :now WHERE id = :id")
_ACTIVE_IS_USER_PICK: Final = text(
    "SELECT NOT suggested FROM design_concepts WHERE project_id = :p AND selected_at IS NOT NULL "
    "ORDER BY selected_at DESC, id DESC LIMIT 1"
)


@dataclass(frozen=True, slots=True)
class ConceptInput:
    """Điều worker cần sau `claim`: `style_id` `None` = lượt AI tự chọn kiểu."""

    project_id: str
    style_id: str | None
    suggested: bool
    input_key: str


def _clock(clock: Clock | None) -> Clock:
    """Đồng hồ mặc định là giờ hệ thống; test truyền `FakeClock`."""
    return clock if clock is not None else SystemClock()


async def claim(db: AsyncSession, concept_id: str, *, clock: Clock | None = None) -> ConceptInput | None:
    """`queued|running` → `running`, đặt lại `started_at`; `None` khi lượt đã kết thúc hoặc không có.

    Nhận cả `running` như `lighting_bake.state.claim`: Celery giao lại sau khi worker chết vẫn nhận được.
    """
    row = (await db.execute(_CLAIM, {"id": concept_id, "now": _clock(clock).now()})).first()
    if row is None:
        return None
    return ConceptInput(project_id=row[0], style_id=row[1], suggested=row[2], input_key=row[3])


async def finish(
    db: AsyncSession,
    concept_id: str,
    *,
    result: dict[str, Any],
    usage: dict[str, Any],
    style_id: str,
    clock: Clock | None = None,
) -> bool:
    """`running` → `done` với `result`/`usage`/`style_id` (kiểu AI đã chọn); `False` khi lượt không còn `running`."""
    if style_id not in DESIGN_STYLE_IDS:
        raise ValueError(f"mã phong cách lạ: {style_id!r}")
    params = {"id": concept_id, "style": style_id, "result": result, "usage": usage, "now": _clock(clock).now()}
    return (await db.execute(_FINISH, params)).scalar_one_or_none() is not None


async def fail(db: AsyncSession, concept_id: str, code: str, *, clock: Clock | None = None) -> bool:
    """`queued|running` → `failed` với `code` (`DESIGN_DIRECTOR_*`); `False` khi lượt đã kết thúc."""
    if not code.startswith(FAILURE_PREFIX):
        raise ValueError(f"mã hỏng lạ: {code!r}")
    found = await db.execute(_FAIL, {"id": concept_id, "code": code, "now": _clock(clock).now()})
    return found.scalar_one_or_none() is not None


def _versions() -> tuple[str, str]:
    """`(PROMPT_VERSION, MATERIALS_VERSION)` của `packages.domain.design_director.prompts` (agent D), nhập trễ."""
    # ponytail: dự phòng "0" chỉ để nhánh chạy trước khi gói của agent D vào; gộp xong thì nhập thẳng.
    try:
        prompts = importlib.import_module("packages.domain.design_director.prompts")
    except ModuleNotFoundError:
        return "0", "0"
    return str(getattr(prompts, "PROMPT_VERSION", "0")), str(getattr(prompts, "MATERIALS_VERSION", "0"))


async def compute_input_key(db: AsyncSession, project_id: str, style_id: str | None) -> str:
    """sha256 của: kiểu (hoặc `auto`), revision mọi tầng còn sống, phiên bản thư viện, vật liệu, prompt.

    Tầng chưa có tài liệu tính revision `-1`. Phiên bản thư viện = số mẫu đã công bố chưa gỡ + `max(published_at)`.
    """
    floors = [f"{level}:{revision}" for level, revision in (await db.execute(_FLOORS, {"p": project_id})).tuples()]
    count, latest = (await db.execute(_LIBRARY)).one()
    prompt_version, materials_version = _versions()
    library = f"{count}:{latest.isoformat() if latest is not None else '-'}"
    parts = [style_id or AUTO_KEY, ",".join(floors), library, materials_version, prompt_version]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


async def find_reusable(db: AsyncSession, project_id: str, input_key: str) -> dict[str, Any] | None:
    """Concept mới nhất cùng khoá còn dùng được (`queued|running|done`), dạng dict cột → giá trị."""
    row = (await db.execute(_REUSABLE, {"p": project_id, "k": input_key})).mappings().first()
    return dict(row) if row is not None else None


async def used_today(db: AsyncSession, project_id: str, now: datetime) -> int:
    """Số lượt của mọi dự án cùng chủ (`projects.created_by`) đã mở từ 0 giờ UTC hôm nay."""
    since = datetime.combine(now.astimezone(UTC).date(), time(), tzinfo=UTC)
    return int((await db.execute(_USED_TODAY, {"p": project_id, "since": since})).scalar_one())


async def insert_concept(
    db: AsyncSession,
    *,
    project_id: str,
    style_id: str | None,
    suggested: bool,
    input_key: str,
    created_by: str | None,
    selected: bool,
    clock: Clock,
) -> str | None:
    """Chèn lượt `queued`, đăng ký gửi task sau commit; `None` khi lượt cùng khoá đang mở (thua đua, C14)."""
    concept_id = new_id("dcn", clock)
    now = clock.now()
    params = {
        "id": concept_id,
        "p": project_id,
        "style": style_id,
        "suggested": suggested,
        "k": input_key,
        "by": created_by,
        "selected": now if selected else None,
        "now": now,
    }
    if (await db.execute(_INSERT, params)).scalar_one_or_none() is None:
        return None
    on_after_commit(db, lambda: send_task(DESIGN_DIRECTOR_TASK, DesignConceptPayload(concept_id=concept_id)))
    return concept_id


async def mark_selected(db: AsyncSession, concept_id: str, now: datetime) -> None:
    """Đặt `selected_at = now`: concept thành `active` của N47."""
    await db.execute(_SELECT, {"id": concept_id, "now": now})


async def enqueue_auto(
    db: AsyncSession,
    project_id: str,
    *,
    clock: Clock | None = None,
    settings: DesignDirectorSettings | None = None,
) -> str | None:
    """Xếp lượt "AI tự chọn kiểu" cho dự án; trả id lượt mới hoặc `None` khi bỏ qua. Không commit.

    Bỏ qua khi tắt/thiếu khoá, đã có lượt cùng khoá (`queued|running|done`), hay chủ dự án hết hạn mức.
    Lượt mới thành `active` chỉ khi người dùng chưa tự chọn kiểu (người chọn thắng AI).
    """
    settings = settings if settings is not None else get_design_director_settings()
    if not settings.available:
        return None
    clock = _clock(clock)
    key = await compute_input_key(db, project_id, None)
    if await find_reusable(db, project_id, key) is not None:
        return None
    if await used_today(db, project_id, clock.now()) >= settings.design_director_daily_quota:
        return None
    user_pick = (await db.execute(_ACTIVE_IS_USER_PICK, {"p": project_id})).scalar_one_or_none()
    return await insert_concept(
        db,
        project_id=project_id,
        style_id=None,
        suggested=True,
        input_key=key,
        created_by=None,
        selected=not user_pick,
        clock=clock,
    )
