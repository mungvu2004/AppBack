"""N15 `GET /api/projects/{project_id}/spatial` — Đ: C01 C06 C08 C17.

Hai lời hứa nặng nhất của route này: **thứ tự** (`levels` theo `(floor_order, pk)`, mọi
danh sách thực thể nối theo đúng thứ tự ấy — H1 ngữ cảnh `n15`) và **không N+1** (số câu
SQL của dự án 1 tầng và 8 tầng bằng nhau).
"""

from decimal import Decimal

import httpx
from fastapi import FastAPI
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.projects.tests.sql_count import count_sql
from apps.api.projects.tests.test_routes_common import headers_of
from apps.api.spatial_read.tests._helpers import make_scene
from apps.api.spatial_read.tests._read_helpers import FakePages, graph_path, use_pages
from packages.db.models.floors import FloorRow
from packages.db.models.projects import Project
from packages.db.models.spatial import FloorDocumentRow
from packages.testing.factories.auth import make_user
from packages.testing.factories.spatial import make_floor_document, sample_floor_dimensions, sample_floor_layer
from packages.testing.fixtures.clock import FakeClock

SCALE = Decimal("12.700000")


async def _fill(db: AsyncSession, floor: FloorRow, index: int, clock: FakeClock, *, reviewed: bool = False) -> None:
    """Một tầng có tài liệu toà mẫu; `id_suffix` giữ id thực thể duy nhất trong dự án (W4)."""
    suffix = f"{index}"
    await make_floor_document(
        db,
        floor_pk=floor.pk,
        layer=sample_floor_layer(index % 4, level_id=floor.level_id, reviewed=reviewed, id_suffix=suffix),
        dimensions=sample_floor_dimensions(index % 4, level_id=floor.level_id, id_suffix=suffix),
        revision=index + 1,
        scale=SCALE,
        scale_source="human",
        clock=clock,
    )


async def test_spatial_read_graph__C01(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Đúng: dự án hai tầng, một tầng có tài liệu và một tầng chưa — cả hai vào đồ thị."""
    scene = await make_scene(db_session, floors=2, address="12 Nguyễn Huệ, Quận 1")
    first, second = scene.floors
    await _fill(db_session, first, 0, fake_clock)
    await db_session.commit()
    response = await api_client.get(graph_path(scene.project.id), headers=headers_of(scene.owner))
    assert response.status_code == 200
    body = response.json()
    graph = body["graph"]
    assert [level["id"] for level in graph["levels"]] == [first.level_id, second.level_id]
    assert [item["floorId"] for item in body["floorRevisions"]] == [first.level_id, second.level_id]
    assert [item["revision"] for item in body["floorRevisions"]] == [1, 0]
    assert graph["building"]["name"] == scene.project.name
    assert graph["building"]["address"] == "12 Nguyễn Huệ, Quận 1"
    assert graph["building"]["datumElevationMm"] == 0
    assert (graph["axes"], graph["notes"]) == ([], [])
    assert {wall["levelId"] for wall in graph["walls"]} == {first.level_id}
    assert {item["levelId"] for item in graph["dimensions"]} == {first.level_id}


async def test_spatial_read_graph__C01_empty_project(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Dự án chưa có tầng → `levels: []`, `floorRevisions: []`, `building.reviewed: false` ([6])."""
    scene = await make_scene(db_session, floors=0)
    body = (await api_client.get(graph_path(scene.project.id), headers=headers_of(scene.owner))).json()
    assert body["graph"]["levels"] == []
    assert body["floorRevisions"] == []
    assert body["graph"]["building"]["reviewed"] is False
    assert body["graph"]["building"]["grossFloorAreaM2"] == 0


async def test_spatial_read_graph__C06(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Admin hệ thống ngoài dự án → 404 `resource:"project"` (K08)."""
    scene = await make_scene(db_session)
    outsider = await make_user(db_session, role="admin")
    await db_session.commit()
    response = await api_client.get(graph_path(scene.project.id), headers=headers_of(outsider))
    assert response.status_code == 404
    assert response.json()["resource"] == "project"


async def test_spatial_read_graph__C08(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Dự án đã xoá mềm → 404 `resource:"project"`, kể cả cho chính thành viên cũ."""
    scene = await make_scene(db_session)
    await db_session.execute(update(Project).where(Project.id == scene.project.id).values(deleted_at=fake_clock.now()))
    await db_session.commit()
    response = await api_client.get(graph_path(scene.project.id), headers=headers_of(scene.owner))
    assert response.status_code == 404
    assert response.json()["resource"] == "project"


async def test_spatial_read_graph__C17(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Dự án không địa chỉ → **vắng khoá** `address`; tầng chưa đo → vắng `areaM2` (W2, K02)."""
    scene = await make_scene(db_session, address=None)
    body = (await api_client.get(graph_path(scene.project.id), headers=headers_of(scene.owner))).json()
    assert "address" not in body["graph"]["building"]
    assert "areaM2" not in body["graph"]["levels"][0]
    assert "scaleMillimetresPerPixel" not in body["graph"]["levels"][0]


async def test_spatial_read_graph_orders_equal_order_by_pk(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Hai tầng trùng `order` sắp theo `pk` — H1 `n15` chỉ đòi không giảm, hợp đồng đòi ổn định."""
    scene = await make_scene(db_session, floors=3)
    await db_session.execute(update(FloorRow).where(FloorRow.project_id == scene.project.id).values(floor_order=0))
    await db_session.commit()
    body = (await api_client.get(graph_path(scene.project.id), headers=headers_of(scene.owner))).json()
    expected = [floor.level_id for floor in sorted(scene.floors, key=lambda row: row.pk)]
    assert [level["id"] for level in body["graph"]["levels"]] == expected


async def test_spatial_read_graph_skips_soft_deleted_floor(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Tầng xoá mềm vắng khỏi `levels` **và** `floorRevisions` (song ánh vẫn đúng)."""
    scene = await make_scene(db_session, floors=2)
    await db_session.execute(
        update(FloorRow).where(FloorRow.pk == scene.floors[0].pk).values(deleted_at=fake_clock.now())
    )
    await db_session.commit()
    body = (await api_client.get(graph_path(scene.project.id), headers=headers_of(scene.owner))).json()
    assert [level["id"] for level in body["graph"]["levels"]] == [scene.floors[1].level_id]
    assert [item["floorId"] for item in body["floorRevisions"]] == [scene.floors[1].level_id]


async def test_spatial_read_graph_query_count_is_flat(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Số câu SQL của dự án 1 tầng và dự án 8 tầng bằng nhau — không N+1 ([6] N15)."""
    small = await make_scene(db_session, floors=1)
    large = await make_scene(db_session, floors=8)
    await _fill(db_session, small.floors[0], 0, fake_clock)
    for index, floor in enumerate(large.floors):
        await _fill(db_session, floor, index, fake_clock)
    await db_session.commit()
    with count_sql() as one:
        await api_client.get(graph_path(small.project.id), headers=headers_of(small.owner))
    with count_sql() as eight:
        await api_client.get(graph_path(large.project.id), headers=headers_of(large.owner))
    assert one.count == eight.count, eight.statements


async def test_spatial_read_graph_level_matches_floors_list(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """`Level.id` = `Floor.id`, và `areaM2` là **số** JSON bằng đúng #12/#33 (cùng bảng đếm)."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    await _fill(db_session, floor, 0, fake_clock)
    await db_session.commit()
    listed = (await api_client.get(f"/api/projects/{scene.project.id}/floors", headers=headers_of(scene.owner))).json()[
        0
    ]
    level = (await api_client.get(graph_path(scene.project.id), headers=headers_of(scene.owner))).json()["graph"][
        "levels"
    ][0]
    assert level["id"] == listed["id"]
    assert (level["name"], level["order"]) == (listed["name"], listed["order"])
    assert (level["elevationMm"], level["heightMm"]) == (listed["elevationMm"], listed["heightMm"])
    assert level.get("areaM2") == listed.get("areaM2")


async def test_spatial_read_graph_building_reviewed_when_every_level_is(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """`building.reviewed` đúng khi có ≥ 1 tầng và **mọi** tầng đã duyệt (HOP-DONG-MOI §4.1)."""
    scene = await make_scene(db_session, floors=2)
    for index, floor in enumerate(scene.floors):
        await _fill(db_session, floor, index, fake_clock, reviewed=True)
    await db_session.commit()
    body = (await api_client.get(graph_path(scene.project.id), headers=headers_of(scene.owner))).json()
    assert all(level["reviewed"] for level in body["graph"]["levels"])
    assert body["graph"]["building"]["reviewed"] is True


async def test_spatial_read_graph_level_reviewed_follows_page_gate(
    api_client: httpx.AsyncClient, db_session: AsyncSession, api_app: FastAPI, fake_clock: FakeClock
) -> None:
    """Cổng trang trả trang khác → tỉ lệ tụt hạng, `Level.reviewed` sai ở N15 y như N16 (#35)."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    await make_floor_document(
        db_session,
        floor_pk=floor.pk,
        layer=sample_floor_layer(0, level_id=floor.level_id, reviewed=True),
        scale=SCALE,
        scale_source="human",
        scale_page_key="P1",
        clock=fake_clock,
    )
    await db_session.commit()
    use_pages(api_app, FakePages({floor.pk: "P2"}))
    body = (await api_client.get(graph_path(scene.project.id), headers=headers_of(scene.owner))).json()
    assert body["graph"]["levels"][0]["reviewed"] is False
    assert body["graph"]["building"]["reviewed"] is False


async def test_spatial_read_graph_never_writes(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Đọc dự án toàn tầng chưa có tài liệu **không** sinh dòng nào ([6]: đọc không ghi)."""
    scene = await make_scene(db_session, floors=2)
    before = (await db_session.execute(select(func.count()).select_from(FloorDocumentRow))).scalar_one()
    await api_client.get(graph_path(scene.project.id), headers=headers_of(scene.owner))
    await db_session.commit()
    after = (await db_session.execute(select(func.count()).select_from(FloorDocumentRow))).scalar_one()
    assert after == before
