"""Thân FE thật và đường của test khuôn thuộc tính (B2-07); phần còn lại nhập lại từ test phép đo (R-07)."""

from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.measurements.tests._helpers import (
    FORBIDDEN_ROLE,
    LIMIT_TEST,
    headers_of,
    project_updated_at,
    seed_project,
    with_env,
)
from apps.api.projects.tests.test_routes_common import project_path
from packages.db.models.templates import PropertyTemplateRow

__all__ = [
    "FE_BODIES",
    "FORBIDDEN_ROLE",
    "LIMIT_TEST",
    "headers_of",
    "project_updated_at",
    "seed_project",
    "template_body",
    "template_rows",
    "templates_path",
    "with_env",
]

FE_BODIES: Final[dict[str, dict[str, Any]]] = {
    "wall": {"heightMm": 2800, "kind": "partition", "thicknessMm": 100},
    "opening": {"heightMm": 2100, "sillHeightMm": 0, "swing": "left", "widthMm": 900},
    "room": {"usage": "bedroom"},
    "furniture": {"kind": "wardrobe", "rotationDeg": 90},
}
"""`fields` đủ khoá của từng nhánh, như `propertyTemplateDraftOf` của FE."""


def templates_path(project_id: str) -> str:
    """`/api/projects/{project_id}/property-templates` — đường #28, #29."""
    return f"{project_path(project_id)}/property-templates"


def template_body(
    kind: str = "wall", *, name: str = "Tường ngăn 100", fields: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Thân FE thật của #29: `{objectKind, name, fields}`; `fields` mặc định là đủ khoá của nhánh."""
    return {"objectKind": kind, "name": name, "fields": FE_BODIES.get(kind, {}) if fields is None else fields}


async def template_rows(sessionmaker: async_sessionmaker[AsyncSession], project_id: str) -> list[PropertyTemplateRow]:
    """Mọi dòng `property_templates` của dự án, đọc qua **session mới** (K22)."""
    async with sessionmaker() as session:
        stmt = select(PropertyTemplateRow).where(PropertyTemplateRow.project_id == project_id)
        return list(
            (await session.execute(stmt.order_by(PropertyTemplateRow.created_at, PropertyTemplateRow.id))).scalars()
        )
