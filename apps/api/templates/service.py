"""Nghiệp vụ #28-#29 (B2-07 [6]).

#29 mở giao dịch bằng khoá `templates:<project_id>`, rồi mới kiểm trần. Không khử trùng: hai
lượt bấm là hai khuôn.
"""

from typing import Final

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.auth import Principal
from apps.api.projects.summaries import touch_project
from apps.api.templates.errors import TEMPLATE_LIMIT_REACHED
from apps.api.templates.schemas import TEMPLATE_ADAPTER, PropertyTemplate, PropertyTemplateDraft
from apps.api.templates.settings import get_templates_settings
from packages.core.clock import Clock
from packages.core.ids import new_id
from packages.db.locks import lock_project_scope
from packages.db.models.templates import PropertyTemplateRow

LOCK_SCOPE: Final = "templates"


def to_template(row: PropertyTemplateRow) -> PropertyTemplate:
    """Dòng đã lưu → nhánh ra đúng `objectKind`; `fields` vắng khoá nào vẫn vắng."""
    return TEMPLATE_ADAPTER.validate_python(
        {
            "id": row.id,
            "name": row.name,
            "projectId": row.project_id,
            "createdAt": row.created_at,
            "objectKind": row.object_kind,
            "fields": row.fields,
        }
    )


async def list_templates(db: AsyncSession, project_id: str) -> list[PropertyTemplate]:
    """#28: `created_at ASC, id ASC`, tối đa `TEMPLATES_MAX`."""
    stmt = (
        select(PropertyTemplateRow)
        .where(PropertyTemplateRow.project_id == project_id)
        .order_by(PropertyTemplateRow.created_at, PropertyTemplateRow.id)
        .limit(get_templates_settings().templates_max)
    )
    return [to_template(row) for row in (await db.execute(stmt)).scalars()]


async def create_template(
    db: AsyncSession, project_id: str, body: PropertyTemplateDraft, principal: Principal, clock: Clock
) -> PropertyTemplate:
    """#29: khoá → trần → chèn → `touch_project`; `created_by` từ token (K05)."""
    await lock_project_scope(db, LOCK_SCOPE, project_id)
    count = (
        await db.execute(
            select(func.count()).select_from(PropertyTemplateRow).where(PropertyTemplateRow.project_id == project_id)
        )
    ).scalar_one()
    if count >= get_templates_settings().templates_max:
        raise TEMPLATE_LIMIT_REACHED.error()
    row = PropertyTemplateRow(
        id=new_id("tpl", clock),
        project_id=project_id,
        name=body.name,
        object_kind=body.object_kind,
        fields=body.fields.model_dump(by_alias=True, exclude_none=True),
        created_by=principal.user_id,
        created_at=clock.now(),
    )
    db.add(row)
    await db.flush()
    await touch_project(db, project_id=project_id, clock=clock)
    return to_template(row)
