"""#30 `GET …/floors/{floor_id}/quality` — ma trận case Đ và phần "Đọc" của [8]."""

import httpx
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.projects.tests.test_routes_common import headers_of
from apps.api.quality.tests._images import desk_shot
from apps.api.quality.tests._route_helpers import (
    SHOT_H,
    SHOT_W,
    floor_view,
    make_image_floor,
    make_stage,
    measure_real,
    read_path,
)
from apps.api.quality.tests._route_helpers import (
    quality_env as quality_env,
)
from packages.core.clock import Clock
from packages.db.models.floors import FloorRow
from packages.storage.local import LocalDiskStorage
from packages.testing.factories.auth import make_user
from packages.testing.factories.floors import make_floor
from packages.testing.factories.projects import make_project


async def test_quality_read_assessment__C01_measured(
    api_client: httpx.AsyncClient, db_session: AsyncSession, local_storage: LocalDiskStorage, fake_clock: Clock
) -> None:
    """Tầng đã đo: `measurement`, `frame`, `findings` đủ; `expectedConfidence` vắng."""
    stage = await make_stage(db_session, local_storage)
    shot = desk_shot(SHOT_W, SHOT_H)
    await measure_real(db_session, fake_clock, stage.floors[0], shot.pixels)

    response = await api_client.get(read_path(stage.project.id, stage.level()), headers=stage.headers)

    assert response.status_code == 200, response.text
    floor = floor_view(response, stage.level())
    assert floor["isMeasured"] is True
    assert set(floor["measurement"]) == {"widthPx", "heightPx", "skewDeg", "contrastScore", "noiseScore"}
    assert floor["frame"]["isFound"] is False
    assert "FRAME_NOT_FOUND" in {item["code"] for item in floor["findings"]}
    assert "expectedConfidence" not in floor


async def test_quality_read_assessment__C01_unmeasured(
    api_client: httpx.AsyncClient, db_session: AsyncSession, local_storage: LocalDiskStorage
) -> None:
    """Tầng chưa đo: `findings: []` và vắng `measurement`, `frame`; viewer (thành viên) đọc được."""
    stage = await make_stage(db_session, local_storage)

    response = await api_client.get(read_path(stage.project.id, stage.level()), headers=stage.viewer_headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["projectId"] == stage.project.id
    assert body["floorId"] == stage.level()
    floor = floor_view(response, stage.level())
    assert floor["isMeasured"] is False
    assert floor["findings"] == []
    assert "measurement" not in floor
    assert "frame" not in floor
    assert floor["sourceUrl"]


async def test_quality_read_assessment__C06(
    api_client: httpx.AsyncClient, db_session: AsyncSession, local_storage: LocalDiskStorage
) -> None:
    """Người ngoài dự án, kể cả admin hệ thống → 404 `project`."""
    stage = await make_stage(db_session, local_storage)
    admin = await make_user(db_session, role="admin")
    await db_session.commit()

    response = await api_client.get(read_path(stage.project.id, stage.level()), headers=headers_of(admin))

    assert response.status_code == 404, response.text
    assert response.json()["resource"] == "project"


async def test_quality_read_assessment__C08(
    api_client: httpx.AsyncClient, db_session: AsyncSession, local_storage: LocalDiskStorage
) -> None:
    """Tầng không có, tầng đã xoá → 404 `floor`; dự án không tầng nào có bản vẽ → 404 `upload`."""
    stage = await make_stage(db_session, local_storage)
    empty = await make_project(db_session, owner=stage.owner)
    bare = await make_floor(db_session, project=empty)
    gone = await make_image_floor(
        db_session, local_storage, project=stage.project, pixels=desk_shot(SHOT_W, SHOT_H).pixels
    )
    await db_session.execute(
        update(FloorRow).where(FloorRow.pk == gone.floor.pk).values(deleted_at=FloorRow.created_at)
    )
    await db_session.commit()

    missing = await api_client.get(read_path(stage.project.id, "L-NOSUCHFLOOR0"), headers=stage.headers)
    deleted = await api_client.get(read_path(stage.project.id, gone.floor.level_id), headers=stage.headers)
    no_drawing = await api_client.get(read_path(empty.id, bare.level_id), headers=stage.headers)

    assert [missing.status_code, deleted.status_code, no_drawing.status_code] == [404, 404, 404]
    assert missing.json()["resource"] == "floor"
    assert deleted.json()["resource"] == "floor"
    assert no_drawing.json()["resource"] == "upload"


async def test_quality_read_assessment__C17(
    api_client: httpx.AsyncClient, db_session: AsyncSession, local_storage: LocalDiskStorage, fake_clock: Clock
) -> None:
    """Không phần tử nào mang `null` hay `expectedConfidence`; tầng chưa đo vắng `measurement`, `frame`."""
    stage = await make_stage(db_session, local_storage, floors=2)
    await measure_real(db_session, fake_clock, stage.floors[0], desk_shot(SHOT_W, SHOT_H).pixels)

    response = await api_client.get(read_path(stage.project.id, stage.level(1)), headers=stage.headers)

    assert response.status_code == 200, response.text
    assert "null" not in response.text
    measured, unmeasured = floor_view(response, stage.level(0)), floor_view(response, stage.level(1))
    assert "measurement" in measured
    assert "frame" in measured
    assert "measurement" not in unmeasured
    assert "frame" not in unmeasured
    assert "expectedConfidence" not in measured
    assert "expectedConfidence" not in unmeasured


async def test_quality_read_assessment__floor_without_drawing_points_at_first(
    api_client: httpx.AsyncClient, db_session: AsyncSession, local_storage: LocalDiskStorage
) -> None:
    """Hỏi tầng `order` 0 chưa tải: `floors` 2 phần tử theo `order`, `floorId` là phần tử đầu."""
    stage = await make_stage(db_session, local_storage, floors=2)
    bare = await make_floor(db_session, project=stage.project, order=0)
    await db_session.commit()

    response = await api_client.get(read_path(stage.project.id, bare.level_id), headers=stage.headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert [item["floorId"] for item in body["floors"]] == [stage.level(0), stage.level(1)]
    assert body["floorId"] == stage.level(0)
