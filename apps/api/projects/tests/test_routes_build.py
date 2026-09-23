"""Test dựng lô của #23/N1 (SQL, N+1) và cổng mở rộng ở mức route (B2-01 [8] "Dựng lô", "Cổng").

Route chưa hợp nhất trên nhánh này (việc M) — mỗi hàm chỉ mồi qua factory/model của N và
gọi HTTP; đếm SQL bằng `sql_count.py` chung của module (không viết bộ đếm riêng, ghi chú
khảo sát mục 4). Không nhập `router`, `service`, `memberships`, `summaries`, `access`, `jobs`.
"""

from collections.abc import Mapping, Sequence
from typing import Final

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core import extensions
from apps.api.core.wire import WireModel
from apps.api.projects.parts import PROJECT_FLOORS, SUBMODULE, ViewPart
from apps.api.projects.tests.sql_count import count_sql
from apps.api.projects.tests.test_routes_common import PROJECTS_PATH, SUMMARIES_PATH, headers_of, seed_project
from apps.api.projects.wire import FloorOut
from packages.db.models.auth import User
from packages.testing.factories.auth import make_user
from packages.testing.fixtures.clock import FakeClock

BATCH_SIZE: Final = 20
_FORBIDDEN_KEYS: Final = frozenset({"currentVersion", "progress", "deletedAt"})


def _assert_no_forbidden_keys_or_nulls(value: object) -> None:
    """Không khoá nào trong `_FORBIDDEN_KEYS` ở bất kỳ tầng nào, và không `None` nào lọt qua (W2, K02)."""
    if isinstance(value, dict):
        assert not (set(value) & _FORBIDDEN_KEYS)
        for item in value.values():
            _assert_no_forbidden_keys_or_nulls(item)
    elif isinstance(value, list):
        for item in value:
            _assert_no_forbidden_keys_or_nulls(item)
    else:
        assert value is not None


async def test_projects_list_projects_query_count_is_constant_across_batch_size(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """#23: 1 dự án và 20 dự án cùng số câu SQL — không N+1 (B2-01 [9])."""
    small_owner = await make_user(db_session)
    await seed_project(db_session, owner=small_owner)
    with count_sql() as small:
        response = await api_client.get(PROJECTS_PATH, headers=headers_of(small_owner))
    assert response.status_code == 200

    big_owner = await make_user(db_session)
    for _ in range(BATCH_SIZE):
        await seed_project(db_session, owner=big_owner)
    with count_sql() as big:
        response = await api_client.get(PROJECTS_PATH, headers=headers_of(big_owner))
    assert response.status_code == 200

    assert big.count == small.count, (
        f"#23 N+1: 1 dự án = {small.count} câu SQL, 20 dự án = {big.count} câu; 20 dự án: {big.statements}"
    )


async def test_projects_list_summaries_query_count_is_constant_across_batch_size(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """N1: 1 dự án và 20 dự án cùng số câu SQL trên một trang (B2-01 [9])."""
    small_owner = await make_user(db_session)
    await seed_project(db_session, owner=small_owner)
    with count_sql() as small:
        response = await api_client.get(SUMMARIES_PATH, params={"limit": 50}, headers=headers_of(small_owner))
    assert response.status_code == 200

    big_owner = await make_user(db_session)
    for _ in range(BATCH_SIZE):
        await seed_project(db_session, owner=big_owner)
    with count_sql() as big:
        response = await api_client.get(SUMMARIES_PATH, params={"limit": 50}, headers=headers_of(big_owner))
    assert response.status_code == 200

    assert big.count == small.count, (
        f"N1 N+1: 1 dự án = {small.count} câu SQL, 20 dự án = {big.count} câu; 20 dự án: {big.statements}"
    )


async def test_projects_list_projects_excludes_soft_deleted_members_and_sorts_by_user_id(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """`members` bỏ người xoá mềm, sắp `user_id ASC`, không `avatarUrl` (B1-04 chưa cắm)."""
    owner = await make_user(db_session)
    alive = await make_user(db_session)
    gone = await make_user(db_session)
    project = await seed_project(db_session, owner=owner, members=[alive, gone])
    await db_session.execute(update(User).where(User.id == gone.id).values(deleted_at=fake_clock.now()))
    await db_session.commit()

    response = await api_client.get(PROJECTS_PATH, headers=headers_of(owner))
    item = next(row for row in response.json() if row["id"] == project.id)
    member_ids = [member["id"] for member in item["members"]]
    assert gone.id not in member_ids
    assert member_ids == sorted(member_ids)
    assert all("avatarUrl" not in member for member in item["members"])


async def test_project_out_never_leaks_forbidden_keys_or_nulls(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Không `currentVersion`, `progress`, `deletedAt`; không `null` ở bất kỳ tầng nào (K01, K02)."""
    owner = await make_user(db_session)
    await seed_project(db_session, owner=owner)
    response = await api_client.get(PROJECTS_PATH, headers=headers_of(owner))
    for item in response.json():
        _assert_no_forbidden_keys_or_nulls(item)


async def test_project_read_without_floor_part_returns_empty_list(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Chưa module nào cắm `project.floors` (mặc định `discover` toàn cục) → `floors: []`."""
    owner = await make_user(db_session)
    project = await seed_project(db_session, owner=owner)
    response = await api_client.get(f"{PROJECTS_PATH}/{project.id}", headers=headers_of(owner))
    assert response.json()["floors"] == []


async def test_project_read_with_floor_part_override_returns_floors(
    api_client: httpx.AsyncClient, api_app: FastAPI, db_session: AsyncSession
) -> None:
    """Phần giả `project.floors` qua `extensions.override` → `floors` có mặt trong response."""

    async def _floors(db: AsyncSession, ids: Sequence[str]) -> Mapping[str, Sequence[WireModel]]:
        """Mỗi dự án được hỏi có đúng một tầng giả, để phân biệt với `floors: []` mặc định."""
        return {
            project_id: [FloorOut(id="L-FAKE", name="Tầng giả", order=0, elevation_mm=0, height_mm=3000, drawings=[])]
            for project_id in ids
        }

    extensions.override(api_app, SUBMODULE, [("test_floor_view", [ViewPart(kind=PROJECT_FLOORS, load=_floors)])])
    owner = await make_user(db_session)
    project = await seed_project(db_session, owner=owner)
    response = await api_client.get(f"{PROJECTS_PATH}/{project.id}", headers=headers_of(owner))
    floors = response.json()["floors"]
    assert len(floors) == 1
    assert floors[0]["id"] == "L-FAKE"


@pytest.mark.parametrize("path", [PROJECTS_PATH, SUMMARIES_PATH])
async def test_empty_page_runs_only_the_project_query(
    api_client: httpx.AsyncClient, db_session: AsyncSession, path: str
) -> None:
    """PERF-02: người chưa có dự án nào → đúng **một** câu SQL, không hai câu `IN ()` thừa."""
    owner = await make_user(db_session)
    await db_session.commit()
    with count_sql() as counter:
        response = await api_client.get(path, headers=headers_of(owner))
    assert response.status_code == 200
    assert counter.count == 1, counter.statements
