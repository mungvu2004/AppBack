"""Helper dùng chung cho test của `apps/api/documents`: sân khấu đã commit, đường và thân N39."""

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.projects.tests.test_routes_common import headers_of
from packages.db.models.auth import User
from packages.db.models.projects import Project
from packages.testing.factories.auth import make_user
from packages.testing.factories.projects import make_project


@dataclass(frozen=True, slots=True)
class Stage:
    """Chủ dự án + dự án **không tầng** đã commit, kèm header của chủ (K22)."""

    user: User
    project: Project
    headers: dict[str, str]


async def make_stage(db: AsyncSession) -> Stage:
    """Một dự án 0 tầng: N39 không được đòi tầng."""
    user = await make_user(db)
    project = await make_project(db, owner=user)
    await db.commit()
    return Stage(user=user, project=project, headers=headers_of(user))


def init_path(project_id: str) -> str:
    """Đường N39."""
    return f"/api/projects/{project_id}/documents/uploads"


def init_body(*, size_bytes: int = 1000, file_name: str = "ban-ve.pdf", **overrides: Any) -> dict[str, Any]:
    """Thân N39 đầy đủ; `overrides` đổi hay thêm khoá bất kỳ."""
    return {"fileName": file_name, "mimeType": "application/pdf", "sizeBytes": size_bytes} | overrides
