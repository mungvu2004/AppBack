"""Nghiệp vụ N47-N48 trên bảng `design_concepts`; luật trạng thái và khoá đầu vào ở `state.py`.

N48 theo thứ tự: tắt → 503; tính `input_key`; có concept cùng khoá (`queued|running|done`) → đặt
`selected_at`, trả nó, không gọi AI; hết hạn mức của chủ dự án → 429; còn lại chèn lượt `queued`
(đã chọn) và gửi task sau commit. Hai lượt song song cùng khoá: `ON CONFLICT DO NOTHING` trên unique
partial `uq_design_concepts_active` — lượt thua đọc lại lượt thắng và chọn nó (C14), không 409.
"""

from typing import Any, Final

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.design_director import state
from apps.api.design_director.errors import DESIGN_DIRECTOR_DISABLED, DESIGN_DIRECTOR_QUOTA, RETRY_AFTER_S
from apps.api.design_director.schemas import DesignConcept, DesignConceptState
from apps.api.design_director.settings import DesignDirectorSettings
from packages.core.clock import Clock

_ACTIVE: Final = text(
    f"SELECT {state.CONCEPT_COLUMNS} FROM design_concepts WHERE project_id = :p "  # noqa: S608 — hằng
    "AND selected_at IS NOT NULL ORDER BY selected_at DESC, id DESC LIMIT 1"
)
_SUGGESTED: Final = text(
    "SELECT style_id FROM design_concepts WHERE project_id = :p AND suggested AND status = 'done' "
    "ORDER BY ended_at DESC, id DESC LIMIT 1"
)


def _wire(row: dict[str, Any]) -> DesignConcept:
    """Một dòng (cột `state.CONCEPT_COLUMNS`) → `DesignConcept`; `None` thành trường vắng (W2)."""
    return DesignConcept.model_validate(row)


async def read_state(db: AsyncSession, *, project_id: str, settings: DesignDirectorSettings) -> DesignConceptState:
    """N47 — `active` = concept `selected_at` mới nhất; `suggestedStyleId` = kiểu lượt đề xuất `done` mới nhất."""
    active = (await db.execute(_ACTIVE, {"p": project_id})).mappings().first()
    suggested = (await db.execute(_SUGGESTED, {"p": project_id})).scalar_one_or_none()
    return DesignConceptState(
        enabled=settings.available,
        suggested_style_id=suggested,
        active=_wire(dict(active)) if active is not None else None,
    )


async def select_concept(
    db: AsyncSession,
    *,
    project_id: str,
    style_id: str | None,
    user_id: str,
    clock: Clock,
    settings: DesignDirectorSettings,
) -> DesignConcept:
    """N48 — chọn (hoặc mở) concept cho `style_id`; `None` = đề xuất AI. Tự `commit`."""
    if not settings.available:
        raise DESIGN_DIRECTOR_DISABLED.error(retry_after=RETRY_AFTER_S)
    key = await state.compute_input_key(db, project_id, style_id)
    now = clock.now()
    found = await state.find_reusable(db, project_id, key)
    if found is None:
        if await state.used_today(db, project_id, now) >= settings.design_director_daily_quota:
            raise DESIGN_DIRECTOR_QUOTA.error(retry_after=RETRY_AFTER_S)
        concept_id = await state.insert_concept(
            db,
            project_id=project_id,
            style_id=style_id,
            suggested=style_id is None,
            input_key=key,
            created_by=user_id,
            selected=True,
            clock=clock,
        )
        if concept_id is not None:
            await db.commit()
            return DesignConcept(
                id=concept_id, style_id=style_id, suggested=style_id is None, status="queued", created_at=now
            )
        found = await state.find_reusable(db, project_id, key)
        if found is None:  # lượt thắng đã kết thúc `failed` ngay giữa hai câu lệnh — hiếm, coi như dùng lại không được
            raise DESIGN_DIRECTOR_DISABLED.error(retry_after=RETRY_AFTER_S)
    await state.mark_selected(db, found["id"], now)
    await db.commit()
    return _wire(found)
