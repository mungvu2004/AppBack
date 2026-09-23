"""Test hợp đồng của #12 `floors_list_floors` (B2-03 [2], [6], [8]).

Route (`router.py`, `service.py`, `lookup.py`) chưa hợp nhất trên nhánh này. Ma trận case:
Đ → C01 C06 C08 C15 C17. Cũng kiểm số truy vấn SQL không đổi theo số tầng (dựng lô, [6]
"Dựng `Floor`") và cổng `project.floors` mà #24 của B2-01 đọc lại đúng thứ tự.
"""

import httpx
import pytest
from apps.api.floors.settings import reset_floors_settings_cache
from packages.testing.factories.floors import make_floor
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.floors.tests._bodies import (
    FLOORS_MAX_TEST,
    floor_body,
    floors_path,
    headers_of,
    project_path,
    seed_project,
)
from apps.api.projects.tests.sql_count import count_sql
from packages.testing.factories.auth import make_user
from packages.testing.fixtures.clock import FakeClock

# ---------------------------------------------------------------------------
# Đ: C01 C06 C08 C15 C17
# ---------------------------------------------------------------------------


async def test_floors_list_floors__C01(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Đúng: thành viên thấy đúng các tầng chưa xoá của dự án, đủ khoá hợp đồng."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    floor = await make_floor(db_session, project=project, name="Tầng trệt", order=0)
    await db_session.commit()

    response = await api_client.get(floors_path(project.id), headers=headers_of(owner))
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert set(items[0]) >= {"id", "name", "order", "elevationMm", "heightMm", "drawings"}
    assert items[0]["id"] == floor.level_id


async def test_floors_list_floors__C06(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Admin hệ thống không phải thành viên → 404 `resource:"project"`."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    outsider = await make_user(db_session, role="admin")
    response = await api_client.get(floors_path(project.id), headers=headers_of(outsider))
    assert response.status_code == 404
    assert response.json()["resource"] == "project"


async def test_floors_list_floors__C08(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Dự án đã xoá mềm → 404."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner, deleted_at=fake_clock.now())
    response = await api_client.get(floors_path(project.id), headers=headers_of(owner))
    assert response.status_code == 404


@pytest.fixture
def _floors_max_test(monkeypatch: pytest.MonkeyPatch) -> None:
    """`FLOORS_MAX=3` cho C15 — trần tạo **và** trần danh sách (dinh-chinh.md #8)."""
    monkeypatch.setenv("FLOORS_MAX", str(FLOORS_MAX_TEST))
    reset_floors_settings_cache()
    yield
    reset_floors_settings_cache()


@pytest.mark.usefixtures("_floors_max_test")
async def test_floors_list_floors__C15(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Biên: 0, 1, `FLOORS_MAX` tầng — trả trọn, đúng thứ tự `floor_order`; tầng dư → 422."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)

    empty = await api_client.get(floors_path(project.id), headers=headers_of(owner))
    assert empty.json() == []

    solo = await api_client.post(floors_path(project.id), json=floor_body(order=0), headers=headers_of(owner))
    assert solo.status_code == 201
    one = await api_client.get(floors_path(project.id), headers=headers_of(owner))
    assert [item["order"] for item in one.json()] == [0]

    for order in range(1, FLOORS_MAX_TEST):
        created = await api_client.post(
            floors_path(project.id), json=floor_body(order=order), headers=headers_of(owner)
        )
        assert created.status_code == 201

    full = await api_client.get(floors_path(project.id), headers=headers_of(owner))
    ids = [item["order"] for item in full.json()]
    assert ids == list(range(FLOORS_MAX_TEST))

    over = await api_client.post(
        floors_path(project.id), json=floor_body(order=FLOORS_MAX_TEST), headers=headers_of(owner)
    )
    assert over.status_code == 422
    assert over.json()["code"] == "FLOOR_LIMIT_REACHED"


async def test_floors_list_floors__C17(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """`areaM2` vắng khi bảng đếm chưa có diện tích, không `null`."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    await make_floor(db_session, project=project, order=0)
    await db_session.commit()

    response = await api_client.get(floors_path(project.id), headers=headers_of(owner))
    item = response.json()[0]
    assert "areaM2" not in item
    assert None not in item.values()


# ---------------------------------------------------------------------------
# Test đặt tên theo việc
# ---------------------------------------------------------------------------


async def test_floors_list_floors_query_count_is_constant_across_floor_count(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Số câu SQL của #12 với 3 và 30 tầng bằng nhau — không N+1 ([6] "Dựng `Floor`")."""
    small_owner = await make_user(db_session, role="engineer")
    small_project = await seed_project(db_session, owner=small_owner)
    for order in range(3):
        await make_floor(db_session, project=small_project, order=order)
    await db_session.commit()
    with count_sql() as small:
        response = await api_client.get(floors_path(small_project.id), headers=headers_of(small_owner))
    assert response.status_code == 200

    big_owner = await make_user(db_session, role="engineer")
    big_project = await seed_project(db_session, owner=big_owner)
    for order in range(30):
        await make_floor(db_session, project=big_project, order=order)
    await db_session.commit()
    with count_sql() as big:
        response = await api_client.get(floors_path(big_project.id), headers=headers_of(big_owner))
    assert response.status_code == 200

    print(f"#12 sql_count: 3 tầng={small.count}, 30 tầng={big.count}")
    assert small.count == big.count


async def test_floors_list_floors_order_matches_project_read_floors(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Đọc lại qua #24 `projects_read_project` của B2-01: `Project.floors` cùng thứ tự với #12."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    for order in (2, 0, 1):
        await make_floor(db_session, project=project, order=order)
    await db_session.commit()

    listed = await api_client.get(floors_path(project.id), headers=headers_of(owner))
    read = await api_client.get(project_path(project.id), headers=headers_of(owner))
    assert [item["order"] for item in listed.json()] == [item["order"] for item in read.json()["floors"]]
    assert [item["order"] for item in listed.json()] == [0, 1, 2]
