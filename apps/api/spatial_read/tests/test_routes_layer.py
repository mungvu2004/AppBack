"""N16 `GET /api/projects/{project_id}/floors/{floor_id}/spatial/layer` — Đ: C01 C06 C08 C17.

Golden của op này có bốn mẫu (`C01`, `C01_unresolved`, `C01_empty`, `C01_reviewed`) để H1
ngữ cảnh `n16` chạy trên đủ bốn hình dạng: có tỉ lệ người đặt, tỉ lệ tạm, tầng trống, và
tầng đã duyệt hết. Ba trong bốn không thể suy ra từ nhau — `scaleStatus` và `level.reviewed`
đổi theo nguồn tỉ lệ, còn tầng trống là đường `empty_document` không chạm DB.
"""

from decimal import Decimal

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.projects.tests.test_routes_common import headers_of
from apps.api.spatial_read.tests._helpers import make_scene
from apps.api.spatial_read.tests._read_helpers import FakePages, delete_floor_mid_request, layer_path, use_pages
from packages.db.models.floors import FloorRow
from packages.db.models.spatial import FloorDocumentRow
from packages.testing.factories.auth import make_user
from packages.testing.factories.spatial import make_floor_document, sample_floor_dimensions, sample_floor_layer
from packages.testing.fixtures.clock import FakeClock

SCALE = Decimal("12.700000")


async def test_spatial_read_layer__C01(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Đúng: tầng có tài liệu toà mẫu và kích thước; `level.id` là `Floor.id` (H1 `n16`)."""
    scene = await make_scene(db_session, floors=2)
    floor = scene.floors[0]
    layer = sample_floor_layer(0, level_id=floor.level_id)
    await make_floor_document(
        db_session,
        floor_pk=floor.pk,
        layer=layer,
        dimensions=sample_floor_dimensions(0, level_id=floor.level_id),
        revision=3,
        scale=SCALE,
        scale_source="human",
        clock=fake_clock,
    )
    await db_session.commit()
    response = await api_client.get(layer_path(scene.project.id, floor.level_id), headers=headers_of(scene.owner))
    assert response.status_code == 200
    body = response.json()
    assert body["revision"] == 3
    assert body["level"]["id"] == floor.level_id
    assert body["level"]["scaleMillimetresPerPixel"] == 12.7
    assert "scaleStatus" not in body
    assert len(body["layer"]["walls"]) == len(layer.walls)
    assert body["axes"] == []
    assert {item["levelId"] for item in body["dimensions"]} == {floor.level_id}
    assert {wall["levelId"] for wall in body["layer"]["walls"]} == {floor.level_id}


async def test_spatial_read_layer__C01_unresolved(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Tỉ lệ do pipeline suy → `scaleStatus: 'unresolved'`, và tầng **chưa** duyệt."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    await make_floor_document(
        db_session,
        floor_pk=floor.pk,
        layer=sample_floor_layer(0, level_id=floor.level_id, reviewed=True),
        scale=SCALE,
        scale_source="pipeline",
        clock=fake_clock,
    )
    await db_session.commit()
    body = (await api_client.get(layer_path(scene.project.id, floor.level_id), headers=headers_of(scene.owner))).json()
    assert body["scaleStatus"] == "unresolved"
    assert body["level"]["reviewed"] is False


async def test_spatial_read_layer__C01_empty(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Tầng chưa có tài liệu → `revision 0`, bốn danh sách rỗng, không tỉ lệ (`empty_document`)."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    body = (await api_client.get(layer_path(scene.project.id, floor.level_id), headers=headers_of(scene.owner))).json()
    assert body["revision"] == 0
    assert body["layer"] == {"walls": [], "openings": [], "rooms": [], "furniture": []}
    assert body["dimensions"] == []
    assert body["level"]["reviewed"] is False


async def test_spatial_read_layer__C01_reviewed(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Mọi mục đã duyệt và tỉ lệ `human` → `level.reviewed` đúng (HOP-DONG-MOI §4.1)."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    await make_floor_document(
        db_session,
        floor_pk=floor.pk,
        layer=sample_floor_layer(0, level_id=floor.level_id, reviewed=True),
        dimensions=sample_floor_dimensions(0, level_id=floor.level_id),
        scale=SCALE,
        scale_source="human",
        clock=fake_clock,
    )
    await db_session.commit()
    body = (await api_client.get(layer_path(scene.project.id, floor.level_id), headers=headers_of(scene.owner))).json()
    assert body["level"]["reviewed"] is True
    assert body["level"]["source"] == "human"


async def test_spatial_read_layer__C06(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Admin hệ thống ngoài dự án → 404 `resource:"project"` (K08)."""
    scene = await make_scene(db_session)
    outsider = await make_user(db_session, role="admin")
    await db_session.commit()
    response = await api_client.get(
        layer_path(scene.project.id, scene.floors[0].level_id), headers=headers_of(outsider)
    )
    assert response.status_code == 404
    assert response.json()["resource"] == "project"


@pytest.mark.parametrize("case", ["missing", "deleted", "other_project"])
async def test_spatial_read_layer__C08(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock, case: str
) -> None:
    """Tầng không có, đã xoá mềm, hay của dự án khác → 404 `resource:"floor"`."""
    scene = await make_scene(db_session)
    other = await make_scene(db_session)
    floor_id = "L-NOSUCHFLOOR"
    if case == "deleted":
        floor_id = scene.floors[0].level_id
        await db_session.execute(
            update(FloorRow).where(FloorRow.pk == scene.floors[0].pk).values(deleted_at=fake_clock.now())
        )
        await db_session.commit()
    elif case == "other_project":
        floor_id = other.floors[0].level_id
    response = await api_client.get(layer_path(scene.project.id, floor_id), headers=headers_of(scene.owner))
    assert response.status_code == 404
    assert response.json()["resource"] == "floor"


async def test_spatial_read_layer__C17(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Tầng chưa có gì: vắng `areaM2`, `scaleMillimetresPerPixel`, `scaleStatus` (W2, K02)."""
    scene = await make_scene(db_session)
    body = (
        await api_client.get(layer_path(scene.project.id, scene.floors[0].level_id), headers=headers_of(scene.owner))
    ).json()
    assert "scaleStatus" not in body
    assert "areaM2" not in body["level"]
    assert "scaleMillimetresPerPixel" not in body["level"]


async def test_spatial_read_layer_when_floor_vanishes_mid_request(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
) -> None:
    """Tầng xoá mềm giữa `get_floor` và lần đọc sau → 404, không `IndexError` ([6] N16)."""
    scene = await make_scene(db_session)
    with delete_floor_mid_request(db_sessionmaker, scene.floors[0].pk, fake_clock):
        response = await api_client.get(
            layer_path(scene.project.id, scene.floors[0].level_id), headers=headers_of(scene.owner)
        )
    assert response.status_code == 404
    assert response.json()["resource"] == "floor"


async def test_spatial_read_layer_never_writes(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Đọc tầng chưa có tài liệu **không** sinh dòng `floor_documents` ([6]: đọc không ghi)."""
    scene = await make_scene(db_session)
    before = (await db_session.execute(select(func.count()).select_from(FloorDocumentRow))).scalar_one()
    await api_client.get(layer_path(scene.project.id, scene.floors[0].level_id), headers=headers_of(scene.owner))
    await db_session.commit()
    after = (await db_session.execute(select(func.count()).select_from(FloorDocumentRow))).scalar_one()
    assert after == before


async def test_spatial_read_layer_demotes_scale_on_other_page(
    api_client: httpx.AsyncClient, db_session: AsyncSession, api_app: FastAPI, fake_clock: FakeClock
) -> None:
    """Tỉ lệ `human` gắn trang P1, cổng trả P2 → `scaleStatus` hiện, `reviewed` sai; tỉ lệ vẫn gửi."""
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
    body = (await api_client.get(layer_path(scene.project.id, floor.level_id), headers=headers_of(scene.owner))).json()
    assert body["scaleStatus"] == "unresolved"
    assert body["level"]["reviewed"] is False
    assert body["level"]["scaleMillimetresPerPixel"] == 12.7


@pytest.mark.parametrize("page", ["P1", None])
async def test_spatial_read_layer_keeps_scale_on_same_or_unknown_page(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    api_app: FastAPI,
    fake_clock: FakeClock,
    page: str | None,
) -> None:
    """Cổng trả đúng trang, hay không biết tầng → hạng `human` giữ nguyên, vắng `scaleStatus`."""
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
    use_pages(api_app, FakePages({floor.pk: page} if page is not None else {}))
    body = (await api_client.get(layer_path(scene.project.id, floor.level_id), headers=headers_of(scene.owner))).json()
    assert "scaleStatus" not in body
    assert body["level"]["reviewed"] is True


async def test_spatial_read_layer_without_page_gate(
    api_client: httpx.AsyncClient, db_session: AsyncSession, api_app: FastAPI, fake_clock: FakeClock
) -> None:
    """Không ai cài cổng trang, hay `scale_page_key` NULL → hạng tỉ lệ như đã lưu."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    await make_floor_document(
        db_session,
        floor_pk=floor.pk,
        layer=sample_floor_layer(0, level_id=floor.level_id, reviewed=True),
        scale=SCALE,
        scale_source="human",
        clock=fake_clock,
    )
    await db_session.commit()
    use_pages(api_app)
    body = (await api_client.get(layer_path(scene.project.id, floor.level_id), headers=headers_of(scene.owner))).json()
    assert "scaleStatus" not in body
    assert body["level"]["reviewed"] is True
