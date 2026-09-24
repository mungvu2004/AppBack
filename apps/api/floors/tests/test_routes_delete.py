"""Test hợp đồng của #11 `floors_delete_floor` (B2-03 [2], [6], [7], [8]).

Route (`router.py`, `service.py`, `lookup.py`, `resolvers.py`) chưa hợp nhất trên nhánh này.
Ma trận case: G → C01 C06 C07 C08 C17 C18; `cases.toml` `waive = {C16 = "DELETE không có
thân, không có chuỗi người nhập"}`.
"""

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.access.kinds import ActivityKind
from apps.api.floors.tests._bodies import (
    FORBIDDEN_ROLE,
    floor_path,
    headers_of,
    live_floor_row,
    new_level_id,
    seed_project,
    summary_row,
)
from packages.testing.factories.auth import make_user
from packages.testing.factories.floors import make_floor
from packages.testing.fixtures.access import assert_one_activity

# ---------------------------------------------------------------------------
# G: C01 C06 C07 C08 C17 C18; waive C16
# ---------------------------------------------------------------------------


async def test_floors_delete_floor__C01(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Đúng: 200, thân là `Floor` dựng **trước** khi xoá; dòng `floors` được xoá mềm (K22)."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    floor = await make_floor(db_session, project=project, name="Sắp xoá", order=0)
    await db_session.commit()

    response = await api_client.delete(floor_path(floor.level_id), headers=headers_of(owner))
    assert response.status_code == 200
    assert response.json()["name"] == "Sắp xoá"

    row = await live_floor_row(db_sessionmaker, project_id=project.id, level_id=floor.level_id)
    assert row is None


async def test_floors_delete_floor__C06(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Admin hệ thống không phải thành viên, id tầng có thật → 404 `resource:"floor"` (K08)."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    floor = await make_floor(db_session, project=project, order=0)
    await db_session.commit()
    outsider = await make_user(db_session, role="admin")

    response = await api_client.delete(floor_path(floor.level_id), headers=headers_of(outsider))
    assert response.status_code == 404
    assert response.json()["resource"] == "floor"


async def test_floors_delete_floor__C07(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Vai mạnh nhất thiếu `layer.edit` (`viewer`) → 403."""
    owner = await make_user(db_session, role="engineer")
    viewer = await make_user(db_session, role=FORBIDDEN_ROLE)
    project = await seed_project(db_session, owner=owner, members=[viewer])
    floor = await make_floor(db_session, project=project, order=0)
    await db_session.commit()

    response = await api_client.delete(floor_path(floor.level_id), headers=headers_of(viewer))
    assert response.status_code == 403


async def test_floors_delete_floor__C08(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Tầng đã xoá mềm từ trước → 404."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    floor = await make_floor(db_session, project=project, order=0)
    await db_session.commit()
    first = await api_client.delete(floor_path(floor.level_id), headers=headers_of(owner))
    assert first.status_code == 200

    second = await api_client.delete(floor_path(floor.level_id), headers=headers_of(owner))
    assert second.status_code == 404


async def test_floors_delete_floor__C17(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """`areaM2` vắng khi bảng đếm chưa có diện tích."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    floor = await make_floor(db_session, project=project, order=0)
    await db_session.commit()

    response = await api_client.delete(floor_path(floor.level_id), headers=headers_of(owner))
    body = response.json()
    assert "areaM2" not in body
    assert None not in body.values()


async def test_floors_delete_floor__C18(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Đúng một dòng `activity_log`, `kind=FLOOR_DELETE`, `object_code` = id tầng."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    floor = await make_floor(db_session, project=project, name="Ghi rồi xoá", order=0)
    await db_session.commit()

    await api_client.delete(floor_path(floor.level_id), headers=headers_of(owner))
    row = await assert_one_activity(
        db_sessionmaker, actor_id=owner.id, kind=ActivityKind.FLOOR_DELETE, object_code=floor.level_id
    )
    assert row.object_label == "Ghi rồi xoá"


# ---------------------------------------------------------------------------
# Test đặt tên theo việc (B2-03 [8] "Cách dựng")
# ---------------------------------------------------------------------------


async def test_floors_delete_floor__path_id_wrong_pattern(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """`{floor_id}` sai mẫu (không có `L-`) → 404 `resource:"floor"`, không truy vấn DB."""
    owner = await make_user(db_session, role="engineer")
    await seed_project(db_session, owner=owner)
    response = await api_client.delete(floor_path("khong-phai-id"), headers=headers_of(owner))
    assert response.status_code == 404
    assert response.json()["resource"] == "floor"


async def test_floors_delete_floor__ambiguous_across_two_member_projects(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Người gọi là thành viên hai dự án cùng có `L-…` → 409 `FLOOR_ID_AMBIGUOUS`, không đổi gì."""
    owner = await make_user(db_session, role="engineer")
    project_a = await seed_project(db_session, owner=owner)
    project_b = await seed_project(db_session, owner=owner)
    level_id = new_level_id()
    floor_a = await make_floor(db_session, project=project_a, level_id=level_id, order=0)
    floor_b = await make_floor(db_session, project=project_b, level_id=level_id, order=0)
    await db_session.commit()

    response = await api_client.delete(floor_path(level_id), headers=headers_of(owner))
    assert response.status_code == 409
    assert response.json()["code"] == "FLOOR_ID_AMBIGUOUS"

    row_a = await live_floor_row(db_sessionmaker, project_id=project_a.id, level_id=level_id)
    row_b = await live_floor_row(db_sessionmaker, project_id=project_b.id, level_id=level_id)
    assert row_a is not None
    assert row_a.pk == floor_a.pk
    assert row_b is not None
    assert row_b.pk == floor_b.pk


async def test_floors_delete_floor__same_id_other_project_not_a_member_deletes_cleanly(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Cùng `L-…` ở dự án khác mà người gọi **không** là thành viên → không tính vào dò trùng, 200."""
    owner = await make_user(db_session, role="engineer")
    other_owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    other_project = await seed_project(db_session, owner=other_owner)
    level_id = new_level_id()
    floor = await make_floor(db_session, project=project, level_id=level_id, order=0)
    await make_floor(db_session, project=other_project, level_id=level_id, order=0)
    await db_session.commit()

    response = await api_client.delete(floor_path(level_id), headers=headers_of(owner))
    assert response.status_code == 200

    row = await live_floor_row(db_sessionmaker, project_id=project.id, level_id=level_id)
    assert row is None
    other_row = await live_floor_row(db_sessionmaker, project_id=other_project.id, level_id=level_id)
    assert other_row is not None  # tầng của dự án kia không bị đụng tới
    assert floor.pk != other_row.pk


async def test_floors_delete_floor__unregisters_but_keeps_summary_counts(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Xoá ẩn dòng đếm (`hidden=True`), **giữ số** để #10 khôi phục trả lại đúng (B2-03 [6])."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    floor = await make_floor(db_session, project=project, order=0)
    await db_session.commit()

    await api_client.delete(floor_path(floor.level_id), headers=headers_of(owner))
    summary = await summary_row(db_sessionmaker, project_id=project.id, floor_level_id=floor.level_id)
    assert summary is not None
    assert summary.hidden is True
