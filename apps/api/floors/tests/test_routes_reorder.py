"""Test hợp đồng của #13 `floors_reorder_floors` (B2-03 [2], [6], [7], [8]).

Route (`router.py`, `service.py`, `lookup.py`, `resolvers.py`) chưa hợp nhất trên nhánh này.
Ma trận case: G → C01 C02 C03 C06 C07 C08 C17 C18; `cases.toml` `extra = ["C14"]`,
`waive = {C16 = "thân chỉ có id tầng, không có chuỗi người nhập"}`.
"""

import asyncio
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.access.kinds import ActivityKind
from apps.api.floors.tests._bodies import (
    FORBIDDEN_ROLE,
    REORDER_PATH,
    floor_path,
    headers_of,
    live_floor_row,
    new_level_id,
    seed_project,
)
from packages.testing.factories.auth import make_user
from packages.testing.factories.floors import make_floor
from packages.testing.fixtures.access import activity_rows, assert_one_activity
from packages.testing.fixtures.api import make_api_client
from packages.testing.fixtures.clock import FakeClock


async def _reorder(client: httpx.AsyncClient, floor_ids: list[str], headers: dict[str, str]) -> httpx.Response:
    """Un lượt `PATCH /api/floors/reorder` — tên hàm ngắn vì mọi test của file này gọi nó."""
    return await client.patch(REORDER_PATH, json={"floorIds": floor_ids}, headers=headers)


# ---------------------------------------------------------------------------
# G: C01 C02 C03 C06 C07 C08 C17 C18; extra C14; waive C16
# ---------------------------------------------------------------------------


async def test_floors_reorder_floors__C01(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Đúng: 200, thứ tự mảng thành `floor_order` mới, đủ tầng của dự án (K22)."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    a = await make_floor(db_session, project=project, order=0)
    b = await make_floor(db_session, project=project, order=1)
    c = await make_floor(db_session, project=project, order=2)
    await db_session.commit()

    response = await _reorder(api_client, [c.level_id, b.level_id, a.level_id], headers_of(owner))
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [c.level_id, b.level_id, a.level_id]

    row_c = await live_floor_row(db_sessionmaker, project_id=project.id, level_id=c.level_id)
    assert row_c is not None
    assert row_c.floor_order == 0


@pytest.mark.parametrize("bad_body", [{"floorIds": "not-a-list"}, {"floorIds": [123]}])
async def test_floors_reorder_floors__C02(
    api_client: httpx.AsyncClient, db_session: AsyncSession, bad_body: dict[str, Any]
) -> None:
    """`floorIds` sai kiểu (không phải mảng, phần tử không phải chuỗi) → 422 `field:"floorIds"`."""
    owner = await make_user(db_session, role="engineer")
    await seed_project(db_session, owner=owner)
    response = await api_client.patch(REORDER_PATH, json=bad_body, headers=headers_of(owner))
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION"
    assert "field" in body


async def test_floors_reorder_floors__C03(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Khoá lạ trong thân → 422 `VALIDATION`."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    floor = await make_floor(db_session, project=project, order=0)
    await db_session.commit()
    response = await api_client.patch(
        REORDER_PATH, json={"floorIds": [floor.level_id], "lạ": 1}, headers=headers_of(owner)
    )
    assert response.status_code == 422


async def test_floors_reorder_floors__C06(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Admin hệ thống không phải thành viên → tầng không được tính khi dò → 404 `resource:"floor"`."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    floor = await make_floor(db_session, project=project, order=0)
    await db_session.commit()
    outsider = await make_user(db_session, role="admin")

    response = await _reorder(api_client, [floor.level_id], headers_of(outsider))
    assert response.status_code == 404
    assert response.json()["resource"] == "floor"


async def test_floors_reorder_floors__C07(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Thành viên `viewer` thiếu `layer.edit` → 403."""
    owner = await make_user(db_session, role="engineer")
    viewer = await make_user(db_session, role=FORBIDDEN_ROLE)
    project = await seed_project(db_session, owner=owner, members=[viewer])
    floor = await make_floor(db_session, project=project, order=0)
    await db_session.commit()
    response = await _reorder(api_client, [floor.level_id], headers_of(viewer))
    assert response.status_code == 403


async def test_floors_reorder_floors__C08(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """`floorIds` toàn tầng đã xoá mềm → không tầng nào khớp → 404 `resource:"floor"`."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    floor = await make_floor(db_session, project=project, order=0)
    await db_session.commit()
    await api_client.delete(floor_path(floor.level_id), headers=headers_of(owner))

    response = await _reorder(api_client, [floor.level_id], headers_of(owner))
    assert response.status_code == 404
    assert response.json()["resource"] == "floor"


async def test_floors_reorder_floors__C17(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """`areaM2` vắng khi bảng đếm chưa có diện tích."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    floor = await make_floor(db_session, project=project, order=0)
    await db_session.commit()
    response = await _reorder(api_client, [floor.level_id], headers_of(owner))
    item = response.json()[0]
    assert "areaM2" not in item
    assert None not in item.values()


async def test_floors_reorder_floors__C18(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Đúng một dòng `activity_log`, `kind=FLOOR_REORDER`, `object_code` = id dự án."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner, name="Dự án sắp xếp")
    a = await make_floor(db_session, project=project, order=0)
    b = await make_floor(db_session, project=project, order=1)
    await db_session.commit()

    await _reorder(api_client, [b.level_id, a.level_id], headers_of(owner))
    row = await assert_one_activity(
        db_sessionmaker, actor_id=owner.id, kind=ActivityKind.FLOOR_REORDER, object_code=project.id
    )
    assert row.object_label == "Dự án sắp xếp"


async def test_floors_reorder_floors__C14(
    api_app: FastAPI, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Hai lượt sắp ngược nhau song song (K23) → cả hai 200, thứ tự cuối là đúng một trong hai."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    a = await make_floor(db_session, project=project, order=0)
    b = await make_floor(db_session, project=project, order=1)
    await db_session.commit()

    forward = [a.level_id, b.level_id]
    backward = [b.level_id, a.level_id]
    async with make_api_client(api_app) as client_a, make_api_client(api_app) as client_b:
        first, second = await asyncio.gather(
            _reorder(client_a, forward, headers_of(owner)), _reorder(client_b, backward, headers_of(owner))
        )
    assert (first.status_code, second.status_code) == (200, 200)

    row_a = await live_floor_row(db_sessionmaker, project_id=project.id, level_id=a.level_id)
    row_b = await live_floor_row(db_sessionmaker, project_id=project.id, level_id=b.level_id)
    assert row_a is not None
    assert row_b is not None
    final = (row_a.floor_order, row_b.floor_order)
    assert final in {(0, 1), (1, 0)}


# ---------------------------------------------------------------------------
# Test đặt tên theo việc (B2-03 [8] "Cách dựng")
# ---------------------------------------------------------------------------


async def test_floors_reorder_floors__missing_floor_is_mismatch(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Thiếu một tầng của dự án trong `floorIds` → 422 `FLOOR_REORDER_MISMATCH`."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    a = await make_floor(db_session, project=project, order=0)
    await make_floor(db_session, project=project, order=1)
    await db_session.commit()
    response = await _reorder(api_client, [a.level_id], headers_of(owner))
    assert response.status_code == 422
    assert response.json()["code"] == "FLOOR_REORDER_MISMATCH"


async def test_floors_reorder_floors__unknown_id_is_mismatch(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Id lạ (không thuộc dự án nào của người gọi) trộn vào → 422 `FLOOR_REORDER_MISMATCH`."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    floor = await make_floor(db_session, project=project, order=0)
    await db_session.commit()
    response = await _reorder(api_client, [floor.level_id, new_level_id()], headers_of(owner))
    assert response.status_code == 422
    assert response.json()["code"] == "FLOOR_REORDER_MISMATCH"


async def test_floors_reorder_floors__mixed_projects_is_mismatch(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """`floorIds` lẫn tầng của hai dự án khác nhau (không dự án nào chứa đủ) → 422 `FLOOR_REORDER_MISMATCH`."""
    owner = await make_user(db_session, role="engineer")
    project_a = await seed_project(db_session, owner=owner)
    project_b = await seed_project(db_session, owner=owner)
    floor_a = await make_floor(db_session, project=project_a, order=0)
    floor_b = await make_floor(db_session, project=project_b, order=0)
    await db_session.commit()
    response = await _reorder(api_client, [floor_a.level_id, floor_b.level_id], headers_of(owner))
    assert response.status_code == 422
    assert response.json()["code"] == "FLOOR_REORDER_MISMATCH"


async def test_floors_reorder_floors__duplicate_id_is_validation(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """`floorIds` có id trùng → 422 `VALIDATION` `field:"floorIds"`."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    floor = await make_floor(db_session, project=project, order=0)
    await db_session.commit()
    response = await _reorder(api_client, [floor.level_id, floor.level_id], headers_of(owner))
    assert response.status_code == 422
    body = response.json()
    assert (body["code"], body["field"]) == ("VALIDATION", "floorIds")


async def test_floors_reorder_floors__empty_array_is_validation(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """`floorIds` rỗng → 422 `VALIDATION` `field:"floorIds"`."""
    owner = await make_user(db_session, role="engineer")
    await seed_project(db_session, owner=owner)
    response = await _reorder(api_client, [], headers_of(owner))
    assert response.status_code == 422
    body = response.json()
    assert (body["code"], body["field"]) == ("VALIDATION", "floorIds")


async def test_floors_reorder_floors__non_json_content_type_is_validation(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """`Content-Type: text/plain` với thân `x` → thân không giải được JSON → 422 `field:"floorIds"`."""
    owner = await make_user(db_session, role="engineer")
    await seed_project(db_session, owner=owner)
    response = await api_client.patch(
        REORDER_PATH, content=b"x", headers={**headers_of(owner), "Content-Type": "text/plain"}
    )
    assert response.status_code == 422
    body = response.json()
    assert (body["code"], body["field"]) == ("VALIDATION", "floorIds")


async def test_floors_reorder_floors__top_level_array_body_is_validation(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Thân JSON hợp lệ nhưng không phải object (mảng trần) → 422 `field:"floorIds"` (vá của việc gộp)."""
    owner = await make_user(db_session, role="engineer")
    await seed_project(db_session, owner=owner)
    response = await api_client.patch(REORDER_PATH, json=["not", "an", "object"], headers=headers_of(owner))
    assert response.status_code == 422
    body = response.json()
    assert (body["code"], body["field"]) == ("VALIDATION", "floorIds")


async def test_floors_reorder_floors__unchanged_order_is_a_noop(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Gửi lại đúng thứ tự hiện tại → 200, không nhật ký thêm (K27, [6] "không đổi → không ghi")."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    a = await make_floor(db_session, project=project, order=0)
    b = await make_floor(db_session, project=project, order=1)
    await db_session.commit()
    response = await _reorder(api_client, [a.level_id, b.level_id], headers_of(owner))
    assert response.status_code == 200
    assert await activity_rows(db_sessionmaker, actor_id=owner.id, kind=ActivityKind.FLOOR_REORDER) == []


async def test_floors_reorder_floors__ambiguous_across_two_member_projects(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Id trùng chuỗi giữa hai dự án người gọi là thành viên cả hai → 409 `FLOOR_ID_AMBIGUOUS`, không đổi."""
    owner = await make_user(db_session, role="engineer")
    project_a = await seed_project(db_session, owner=owner)
    project_b = await seed_project(db_session, owner=owner)
    shared_id = new_level_id()
    await make_floor(db_session, project=project_a, level_id=shared_id, order=0)
    await make_floor(db_session, project=project_b, level_id=shared_id, order=0)
    await db_session.commit()

    response = await _reorder(api_client, [shared_id], headers_of(owner))
    assert response.status_code == 409
    assert response.json()["code"] == "FLOOR_ID_AMBIGUOUS"


async def test_floors_reorder_floors__shared_id_resolves_to_the_only_member_project(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Id trùng chuỗi ở dự án khác mà người gọi không là thành viên → không tính, 200."""
    owner = await make_user(db_session, role="engineer")
    other_owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    other_project = await seed_project(db_session, owner=other_owner)
    shared_id = new_level_id()
    floor = await make_floor(db_session, project=project, level_id=shared_id, order=0)
    await make_floor(db_session, project=other_project, level_id=shared_id, order=0)
    await db_session.commit()

    response = await _reorder(api_client, [shared_id], headers_of(owner))
    assert response.status_code == 200
    row = await live_floor_row(db_sessionmaker, project_id=project.id, level_id=shared_id)
    assert row is not None
    assert row.pk == floor.pk


async def test_floors_reorder_floors__concurrent_with_delete_does_not_500(
    api_app: FastAPI, db_session: AsyncSession
) -> None:
    """Xoá tầng song song với sắp xếp cùng dự án → không 500, không kẹt khoá (K23, [9])."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    a = await make_floor(db_session, project=project, order=0)
    b = await make_floor(db_session, project=project, order=1)
    await db_session.commit()

    async with make_api_client(api_app) as client_a, make_api_client(api_app) as client_b:
        delete_response, reorder_response = await asyncio.gather(
            client_a.delete(floor_path(b.level_id), headers=headers_of(owner)),
            _reorder(client_b, [a.level_id, b.level_id], headers_of(owner)),
        )
    assert delete_response.status_code != 500
    assert reorder_response.status_code != 500
