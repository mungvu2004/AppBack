"""Hạ tầng dùng chung cho `test_routes_*.py` (B2-01 việc T).

Không phải file test (không hàm `test_*`): gom những gì `test_routes_read.py`,
`test_routes_write.py`, `test_routes_build.py` đều cần, để mỗi file kia chỉ còn thân case.
Route (`router.py`, `service.py`) chưa tồn tại trên nhánh này — mọi hàm ở đây chỉ mồi dữ
liệu qua factory/model và dựng header, không nhập gì của M.
"""

import secrets
from collections.abc import Sequence
from decimal import Decimal
from typing import Any, Final, cast

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.auth import Principal
from packages.db.models.auth import User
from packages.db.models.projects import Project, ProjectFloorSummary
from packages.domain.permissions import Role
from packages.testing.factories.projects import make_project
from packages.testing.fixtures.api import auth_headers

PROJECTS_PATH: Final = "/api/projects"
SUMMARIES_PATH: Final = "/api/project-summaries"

FORBIDDEN_ROLE: Final = "viewer"
"""Vai mạnh nhất vẫn không có `project.create`/`project.settings.edit` (C07, ma trận quyền)."""


def principal_of(user: User, *, role: str | None = None) -> Principal:
    """`Principal` khớp một dòng `users` đã mồi; `role` ghi đè khi test cần vai khác cột DB."""
    return Principal(user_id=user.id, session_id=f"sid-{user.id[-8:]}", role=cast("Role", role or user.role))


def headers_of(user: User, *, role: str | None = None) -> dict[str, str]:
    """Header `Authorization` cho một dòng `users` đã mồi (bọc `auth_headers`)."""
    return auth_headers(principal_of(user, role=role))


def project_path(project_id: str) -> str:
    """`/api/projects/{project_id}` — tên hàm tránh f-string rải rác ở mọi test."""
    return f"{PROJECTS_PATH}/{project_id}"


async def seed_project(db: AsyncSession, *, owner: User, members: Sequence[User] = (), **overrides: Any) -> Project:
    """`make_project` rồi `commit`: route gọi qua session khác (HTTP) phải thấy dữ liệu này."""
    project = await make_project(db, owner=owner, members=members, **overrides)
    await db.commit()
    return project


async def seed_floor(
    db: AsyncSession,
    project: Project,
    *,
    floor_level_id: str | None = None,
    floor_order: int = 0,
    walls_total: int = 0,
    walls_reviewed: int = 0,
    has_upload: bool = False,
    pipeline_state: str = "none",
    area_m2: Decimal | None = None,
    hidden: bool = False,
) -> ProjectFloorSummary:
    """Một dòng `project_floor_summaries` mồi thẳng (không qua B2-03, chưa tồn tại)."""
    row = ProjectFloorSummary(
        project_id=project.id,
        floor_level_id=floor_level_id or f"L-{secrets.token_hex(6).upper()}",
        floor_order=floor_order,
        walls_total=walls_total,
        walls_reviewed=walls_reviewed,
        has_upload=has_upload,
        pipeline_state=pipeline_state,
        area_m2=area_m2,
        hidden=hidden,
    )
    db.add(row)
    await db.flush()
    return row
