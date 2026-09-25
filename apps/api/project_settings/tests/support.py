"""Tiện ích dùng chung của test `apps/api/project_settings` (không phải file test, pytest không thu thập).

Chỉ mồi dữ liệu qua factory và dựng header/thân; không nhập `router` hay `service`.
"""

from collections.abc import Sequence
from typing import Any, Final, cast

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.auth import Principal
from packages.db.models.auth import User
from packages.db.models.projects import Project
from packages.domain.permissions import Role
from packages.testing.factories.auth import make_user
from packages.testing.factories.projects import make_project
from packages.testing.fixtures.api import auth_headers

GOOD_BODY: Final[dict[str, Any]] = {
    "buildingType": "commercial",
    "lengthUnit": "m",
    "snapToleranceMm": 40,
    "confidenceThreshold": 0.5,
    "defaultScaleMmPerPx": 2.5,
}
"""Một thân N6 hợp lệ, không có `notes`."""


def settings_path(project_id: str) -> str:
    """`/api/projects/{project_id}/settings`."""
    return f"/api/projects/{project_id}/settings"


def headers_of(user: User) -> dict[str, str]:
    """Header `Authorization` của `FakeTokenVerifier` cho một dòng `users` đã mồi (vai lấy từ `user.role`)."""
    return auth_headers(Principal(user_id=user.id, session_id=f"sid-{user.id[-8:]}", role=cast("Role", user.role)))


async def seed_project(db: AsyncSession, *, owner: User, members: Sequence[User] = (), **overrides: Any) -> Project:
    """`make_project` rồi `commit`: route chạy trên session khác nên phải thấy dữ liệu này."""
    project = await make_project(db, owner=owner, members=members, **overrides)
    await db.commit()
    return project


async def seed_engineer_project(db: AsyncSession) -> tuple[User, Project]:
    """Một kỹ sư sở hữu một dự án mới — nền của hầu hết test."""
    owner = await make_user(db, role="engineer")
    return owner, await seed_project(db, owner=owner)


def replace_body(base: int, **overrides: Any) -> dict[str, Any]:
    """Thân `{baseVersion, body}` của N6; `overrides` ghi đè trường của `GOOD_BODY` (giá trị `None` = bỏ khoá)."""
    body = {**GOOD_BODY, **overrides}
    return {"baseVersion": base, "body": {key: value for key, value in body.items() if value is not None}}


async def put_settings(
    client: httpx.AsyncClient, project_id: str, user: User, payload: dict[str, Any]
) -> httpx.Response:
    """`PUT` N6 với người `user`."""
    return await client.put(settings_path(project_id), json=payload, headers=headers_of(user))
