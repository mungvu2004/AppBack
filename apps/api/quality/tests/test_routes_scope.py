"""Phạm vi dự án của #30-#32 (B2-05b [7]): tầng của dự án khác qua đường dự án mình → 404 `floor`."""

from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.quality.tests._route_helpers import (
    corners_body,
    corners_path,
    make_stage,
    read_path,
    straighten_path,
)
from apps.api.quality.tests._route_helpers import (
    quality_env as quality_env,
)
from packages.storage.local import LocalDiskStorage

FULL_PAGE = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))


async def _call(client: httpx.AsyncClient, route: str, project: str, level: str, headers: dict[str, str]) -> Any:
    """Gọi #30, #31 hoặc #32 theo tên `route` trên `(project, level)`."""
    if route == "read":
        return await client.get(read_path(project, level), headers=headers)
    if route == "corners":
        return await client.post(corners_path(project, level), json=corners_body(FULL_PAGE), headers=headers)
    return await client.post(straighten_path(project, level), json={}, headers=headers)


@pytest.mark.parametrize("route", ["read", "corners", "straighten"])
async def test_floor_of_another_project_is_not_found_through_my_project(
    api_client: httpx.AsyncClient, db_session: AsyncSession, local_storage: LocalDiskStorage, route: str
) -> None:
    """Người dùng A gọi đường dự án của A với `level_id` của tầng thuộc dự án B → 404 `resource: floor`."""
    mine = await make_stage(db_session, local_storage)
    theirs = await make_stage(db_session, local_storage)

    response = await _call(api_client, route, mine.project.id, theirs.level(), mine.headers)

    assert response.status_code == 404, response.text
    assert response.json()["resource"] == "floor"
