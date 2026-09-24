"""Test hai cổng mở rộng B2-03 cắm vào B2-01: `project.floors`, `project.create_floors`
(B2-03 [2], [6] "Hook `project.create_floors`", "Dựng `Floor`").

`api_client`/`api_app` (`packages/testing/fixtures/api.py`) tự dò mọi `apps/api/*/router.py`
và `apps/api/*/view_parts.py`: #25 thật của B2-01 ở đây đã chạy **cùng** `view_parts.py`
thật của module này, không phải bản giả như `apps/api/projects/tests/test_routes_write.py`.
"""

from typing import cast

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.core.auth import Principal
from apps.api.floors.settings import get_floors_settings, reset_floors_settings_cache
from apps.api.floors.view_parts import create_project_floors, load_project_floors
from apps.api.projects.tests.sql_count import count_sql
from packages.core.ids import is_spatial_id
from packages.db.models.auth import User
from packages.db.models.floors import FloorRow
from packages.db.models.projects import Project
from packages.domain.permissions import Role
from packages.testing.factories.auth import make_user
from packages.testing.factories.floors import make_floor
from packages.testing.factories.projects import make_project
from packages.testing.fixtures.api import auth_headers
from packages.testing.fixtures.clock import FakeClock

PROJECTS_PATH = "/api/projects"


def _headers(user: User) -> dict[str, str]:
    """Header `Authorization` cho một dòng `users` đã mồi."""
    return auth_headers(Principal(user_id=user.id, session_id="sid-test", role=cast("Role", user.role)))


def _floor_draft(i: int, **overrides: object) -> dict[str, object]:
    """Một tầng nháp như `CreateProjectModal.container.tsx:57-75` gửi (không có `id`)."""
    return {"name": f"Tầng {i}", "order": i, "elevationMm": i * 3000, "heightMm": 3000} | overrides


async def test_create_project_hook_creates_four_floors_with_ulid_ids_and_order(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """#25 thật + hook thật: 4 tầng `L-`+ULID, `order` 0-3, thấy lại qua session mới và #24."""
    creator = await make_user(db_session, role="engineer")
    body = {"name": "Nhà bốn tầng", "floors": [_floor_draft(i) for i in range(4)]}

    response = await api_client.post(PROJECTS_PATH, json=body, headers=_headers(creator))

    assert response.status_code == 201
    created = response.json()
    floors = created["floors"]
    assert len(floors) == 4
    assert [floor["order"] for floor in floors] == [0, 1, 2, 3]
    assert all(is_spatial_id("level", floor["id"]) for floor in floors)

    async with db_sessionmaker() as fresh:
        stored = (
            (
                await fresh.execute(
                    select(FloorRow).where(FloorRow.project_id == created["id"]).order_by(FloorRow.floor_order)
                )
            )
            .scalars()
            .all()
        )
        assert [row.level_id for row in stored] == [floor["id"] for floor in floors]

    read_back = await api_client.get(f"{PROJECTS_PATH}/{created['id']}", headers=_headers(creator))
    assert [floor["id"] for floor in read_back.json()["floors"]] == [floor["id"] for floor in floors]


async def test_create_project_hook_rejects_invalid_floor_and_creates_nothing(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Một tầng `heightMm: 1500` → 422 `field:"floors.1.heightMm"`, không dự án hay tầng nào còn lại."""
    creator = await make_user(db_session, role="engineer")
    body = {
        "name": "Sẽ rollback",
        "floors": [_floor_draft(0), _floor_draft(1, heightMm=1500)],
    }

    response = await api_client.post(PROJECTS_PATH, json=body, headers=_headers(creator))

    assert response.status_code == 422
    body = response.json()
    assert (body["code"], body["field"]) == ("VALIDATION", "floors.1.heightMm")
    remaining_project = await db_session.execute(select(Project).where(Project.name == "Sẽ rollback"))
    assert remaining_project.scalar_one_or_none() is None
    remaining_floor = await db_session.execute(select(FloorRow))
    assert remaining_floor.first() is None


async def test_create_project_hook_rejects_too_many_floors(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Quá `FLOORS_MAX` phần tử → 422 `field:"floors"` (không kiểm từng tầng nữa)."""
    creator = await make_user(db_session, role="engineer")
    body = {"name": "Quá trần", "floors": [_floor_draft(i) for i in range(get_floors_settings().floors_max + 1)]}

    response = await api_client.post(PROJECTS_PATH, json=body, headers=_headers(creator))

    assert response.status_code == 422
    body = response.json()
    assert (body["code"], body["field"]) == ("VALIDATION", "floors")


async def test_create_project_hook_respects_floors_max_env_override(
    api_client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`FLOORS_MAX` đổi qua biến môi trường có hiệu lực ngay ở hook (C15)."""
    monkeypatch.setenv("FLOORS_MAX", "3")
    reset_floors_settings_cache()
    try:
        creator = await make_user(db_session, role="engineer")
        body = {"name": "Trần nhỏ", "floors": [_floor_draft(i) for i in range(4)]}
        response = await api_client.post(PROJECTS_PATH, json=body, headers=_headers(creator))
        assert response.status_code == 422
        assert response.json()["field"] == "floors"
    finally:
        reset_floors_settings_cache()


async def test_create_project_floors_with_empty_drafts_creates_nothing(
    db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """`floors=()` (thân #25 không có `floors`) — hook không tạo gì, không ném."""
    user = await make_user(db_session)
    project = await make_project(db_session, owner=user)
    await db_session.commit()
    principal = Principal(user_id=user.id, session_id="sid-test", role=cast("Role", user.role))

    await create_project_floors(db_session, project.id, (), principal, fake_clock)

    remaining = await db_session.execute(select(FloorRow).where(FloorRow.project_id == project.id))
    assert remaining.first() is None


async def test_load_project_floors_returns_empty_list_for_project_without_floors(db_session: AsyncSession) -> None:
    """`load_project_floors` trả `[]` cho dự án không có tầng nào, không phải khoá vắng mặt."""
    user = await make_user(db_session)
    project = await make_project(db_session, owner=user)
    await db_session.commit()

    result = await load_project_floors(db_session, [project.id])

    assert result[project.id] == []


async def test_load_project_floors_query_count_is_constant_for_3_and_30_floors(db_session: AsyncSession) -> None:
    """Số câu SQL của `load_project_floors` không đổi theo số tầng (B2-03 [6])."""
    user = await make_user(db_session)
    small_project = await make_project(db_session, owner=user)
    for i in range(3):
        await make_floor(db_session, project=small_project, order=i)
    big_project = await make_project(db_session, owner=user)
    for i in range(30):
        await make_floor(db_session, project=big_project, order=i)
    await db_session.commit()

    with count_sql() as small_counter:
        await load_project_floors(db_session, [small_project.id])
    with count_sql() as big_counter:
        await load_project_floors(db_session, [big_project.id])

    assert small_counter.count == big_counter.count
