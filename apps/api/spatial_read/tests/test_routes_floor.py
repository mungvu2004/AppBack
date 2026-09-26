"""#33 `GET /api/projects/{project_id}/floors/{floor_id}/spatial` — Đ: C01 C06 C08 C17.

Route này trả đúng `Floor` của #12 (cùng đường `floors.lookup.floor_outs`), nên phần lớn
phép kiểm là "hai đường không được lệch nhau", cộng cuộc đua tầng bị xoá giữa hai câu lệnh.
"""

import httpx
import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.projects.tests.test_routes_common import headers_of
from apps.api.spatial_read.tests._read_helpers import delete_floor_mid_request, floor_path, make_stage
from packages.db.models.floors import FloorRow
from packages.testing.factories.auth import make_user
from packages.testing.fixtures.clock import FakeClock


async def test_spatial_read_floor__C01(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Đúng: thành viên đọc siêu dữ liệu một tầng của dự án mình."""
    stage = await make_stage(db_session, floors=2)
    floor = stage.floors[1]
    response = await api_client.get(floor_path(stage.project.id, floor.level_id), headers=headers_of(stage.owner))
    assert response.status_code == 200
    body = response.json()
    assert (body["id"], body["name"], body["order"]) == (floor.level_id, floor.name, floor.floor_order)
    assert (body["elevationMm"], body["heightMm"]) == (floor.elevation_mm, floor.height_mm)
    assert body["drawings"] == []


async def test_spatial_read_floor_matches_floors_list(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """`Floor` của #33 trùng từng khoá với mục cùng tầng ở #12 — một nguồn, không hai luật."""
    stage = await make_stage(db_session, floors=2)
    floor = stage.floors[0]
    single = await api_client.get(floor_path(stage.project.id, floor.level_id), headers=headers_of(stage.owner))
    listed = await api_client.get(f"/api/projects/{stage.project.id}/floors", headers=headers_of(stage.owner))
    assert single.json() == next(item for item in listed.json() if item["id"] == floor.level_id)


async def test_spatial_read_floor__C06(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Admin hệ thống không phải thành viên → 404 `resource:"project"`, **trước** khi tìm tầng (K08)."""
    stage = await make_stage(db_session)
    outsider = await make_user(db_session, role="admin")
    await db_session.commit()
    response = await api_client.get(
        floor_path(stage.project.id, stage.floors[0].level_id), headers=headers_of(outsider)
    )
    assert response.status_code == 404
    assert response.json()["resource"] == "project"


@pytest.mark.parametrize("case", ["missing", "deleted", "other_project"])
async def test_spatial_read_floor__C08(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock, case: str
) -> None:
    """Tầng không có, đã xoá mềm, hay của dự án khác → 404 `resource:"floor"`."""
    stage = await make_stage(db_session)
    other = await make_stage(db_session)
    floor_id = "L-NOSUCHFLOOR"
    if case == "deleted":
        floor_id = stage.floors[0].level_id
        await db_session.execute(
            update(FloorRow).where(FloorRow.pk == stage.floors[0].pk).values(deleted_at=fake_clock.now())
        )
        await db_session.commit()
    elif case == "other_project":
        floor_id = other.floors[0].level_id
    response = await api_client.get(floor_path(stage.project.id, floor_id), headers=headers_of(stage.owner))
    assert response.status_code == 404
    assert response.json()["resource"] == "floor"


async def test_spatial_read_floor__C17(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Tầng chưa đo diện tích → **vắng khoá** `areaM2`, không `null` (W2, K02)."""
    stage = await make_stage(db_session)
    response = await api_client.get(
        floor_path(stage.project.id, stage.floors[0].level_id), headers=headers_of(stage.owner)
    )
    assert "areaM2" not in response.json()


async def test_spatial_read_floor_when_floor_vanishes_mid_request(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
) -> None:
    """Tầng bị xoá mềm **giữa** `get_floor` và lần đọc sau → 404, không `IndexError`."""
    stage = await make_stage(db_session)
    with delete_floor_mid_request(db_sessionmaker, stage.floors[0].pk, fake_clock):
        response = await api_client.get(
            floor_path(stage.project.id, stage.floors[0].level_id), headers=headers_of(stage.owner)
        )
    assert response.status_code == 404
    assert response.json()["resource"] == "floor"
