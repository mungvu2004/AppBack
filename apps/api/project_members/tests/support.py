"""Tiện ích dùng chung của test `apps/api/project_members` (không phải file test)."""

from collections.abc import Sequence
from typing import Any, Final, cast

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.auth import Principal
from packages.db.models.auth import User
from packages.db.models.projects import Project, ProjectMembership
from packages.domain.permissions import Role
from packages.testing.factories.projects import make_project
from packages.testing.fixtures.api import auth_headers

SINKS_SUBMODULE: Final = "invite_sinks"


def headers_of(user: User) -> dict[str, str]:
    """Header `Authorization` của `FakeTokenVerifier`; vai lấy từ cột `role` của người dùng."""
    principal = Principal(user_id=user.id, session_id=f"sid-{user.id[-8:]}", role=cast("Role", user.role))
    return auth_headers(principal)


def members_path(project_id: str, user_id: str | None = None) -> str:
    """`/api/projects/{id}/members[/{user_id}]`."""
    base = f"/api/projects/{project_id}/members"
    return base if user_id is None else f"{base}/{user_id}"


async def seed_project(db: AsyncSession, *, owner: User, members: Sequence[User] = (), **overrides: Any) -> Project:
    """`make_project` rồi `commit`: route chạy trên session khác nên phải thấy dữ liệu này."""
    project = await make_project(db, owner=owner, members=members, **overrides)
    await db.commit()
    return project


async def add(client: httpx.AsyncClient, actor: User, project: Project, email: str, **kwargs: Any) -> httpx.Response:
    """N3 với tư cách `actor`; `kwargs` là `headers=` thêm (vd `Idempotency-Key`)."""
    extra = kwargs.pop("headers", {})
    return await client.post(
        members_path(project.id), json={"email": email}, headers={**headers_of(actor), **extra}, **kwargs
    )


async def remove(client: httpx.AsyncClient, actor: User, project_id: str, user_id: str) -> httpx.Response:
    """N4 với tư cách `actor`."""
    return await client.delete(members_path(project_id, user_id), headers=headers_of(actor))


async def member_ids(db: AsyncSession, project_id: str) -> list[str]:
    """Id thành viên của dự án, đọc lại từ DB (session mới của `db`, không cache đối tượng)."""
    stmt = select(ProjectMembership.user_id).where(ProjectMembership.project_id == project_id)
    return sorted((await db.execute(stmt)).scalars().all())


async def count_editors(db: AsyncSession, project_id: str) -> int:
    """Số thành viên còn `project.settings.edit` (vai `admin|engineer`, `active`)."""
    stmt = (
        select(func.count())
        .select_from(ProjectMembership)
        .join(User, User.id == ProjectMembership.user_id)
        .where(
            ProjectMembership.project_id == project_id,
            User.role.in_(("admin", "engineer")),
            User.status == "active",
        )
    )
    return (await db.execute(stmt)).scalar_one()


async def updated_at(db: AsyncSession, project_id: str) -> object:
    """`projects.updated_at` đọc lại từ DB (bỏ bản đã nạp trong session của test)."""
    stmt = select(Project.updated_at).where(Project.id == project_id)
    return (await db.execute(stmt.execution_options(populate_existing=True))).scalar_one()


class RecordingSink:
    """Sink giả: đếm lượt gọi; `fail=True` thì ném sau khi ghi (kiểm rollback cả lượt)."""

    def __init__(self, *, fail: bool = False) -> None:
        """`fail` quyết định `on_member_added` có ném `RuntimeError` hay không."""
        self.calls: list[dict[str, str]] = []
        self.fail = fail

    async def on_member_added(
        self, db: object, *, project_id: str, project_name: str, user_id: str, actor_id: str, clock: object
    ) -> None:
        """Ghi lượt gọi, rồi ném nếu được dặn."""
        self.calls.append(
            {"project_id": project_id, "project_name": project_name, "user_id": user_id, "actor_id": actor_id}
        )
        if self.fail:
            raise RuntimeError("sink hỏng")
