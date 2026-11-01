"""`dimension-strings` và `detected-geometry` (QT-SCALE-API) — Đ: C01 C06 C08 C17.

Artifact ML ghi thẳng vào kho của test dưới khoá `run_artifact` của một lượt `completed`;
route chỉ đọc, chưa có lượt → danh sách rỗng chứ không lỗi.
"""

from decimal import Decimal

import httpx
import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.drawings.runs import start_run
from apps.api.projects.tests.test_routes_common import headers_of
from apps.api.spatial_read.tests._helpers import Scene, make_scene
from packages.db.models.drawings import PipelineRunRow
from packages.db.models.floors import FloorRow
from packages.ml_contracts.artifacts import (
    BoxPx,
    DetectionPx,
    ObjectsResult,
    PointPx,
    TextPx,
    TextResult,
    WallPx,
    WallsResult,
    objects_to_json,
    text_to_json,
    walls_to_json,
)
from packages.storage import keys
from packages.storage.local import LocalDiskStorage
from packages.testing.factories.auth import make_user
from packages.testing.factories.drawings import make_complete_upload, make_drawing, png_bytes
from packages.testing.factories.spatial import make_floor_document, sample_floor_layer
from packages.testing.fixtures.clock import FakeClock

OPS = ("dimension-strings", "detected-geometry")


def _path(project_id: str, floor_id: str, op: str) -> str:
    return f"/api/projects/{project_id}/floors/{floor_id}/{op}"


def _box(x_min: float, y_min: float, x_max: float, y_max: float) -> BoxPx:
    return BoxPx(x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max)


def _wall(x1: float, y1: float, x2: float, y2: float, thickness: float) -> WallPx:
    return WallPx(start=PointPx(x=x1, y=y1), end=PointPx(x=x2, y=y2), thickness_px=thickness, confidence=0.9)


async def _run_with_artifacts(
    db: AsyncSession, storage: LocalDiskStorage, clock: FakeClock, *, scene: Scene, floor: FloorRow
) -> None:
    """Lượt `completed` + bản vẽ 200 x 100 px + ba artifact ML mẫu."""
    upload = await make_complete_upload(db, storage, project=scene.project, floor=floor, data=png_bytes(10, 10))
    await make_drawing(db, storage, upload=upload, png=png_bytes(200, 100))
    run = await start_run(db, upload_id=upload.id, clock=clock)
    await db.execute(update(PipelineRunRow).where(PipelineRunRow.id == run.id).values(status="completed"))
    texts = TextResult(
        items=(
            TextPx(text="3.600", box=_box(10, 10, 50, 20), confidence=0.9, span_px=120.0),
            TextPx(text="1 200", box=_box(5, 30, 15, 80), confidence=0.8),
            TextPx(text="P.NGỦ", box=_box(60, 60, 90, 70), confidence=0.9),
            TextPx(text="100", box=_box(60, 10, 70, 15), confidence=0.9),
            TextPx(text="40000", box=_box(60, 20, 90, 25), confidence=0.9),
        )
    )
    walls = WallsResult(
        walls=(_wall(10, 10, 110, 10, 4), _wall(60, 0, 60, 50, 6), _wall(110, 10, 110, 60, 5)),
    )
    objects = ObjectsResult(
        detections=(
            DetectionPx(label="door", box=_box(0, 0, 30, 8), confidence=0.9),
            DetectionPx(label="chair", box=_box(40, 40, 50, 50), confidence=0.9),
            DetectionPx(label="double_door", box=_box(100, 20, 108, 60), confidence=0.7),
        )
    )
    for step, name, body in (
        ("dimensionReading", "text.json", text_to_json(texts)),
        ("wallSegmentation", "walls.json", walls_to_json(walls)),
        ("openingAndFurnitureDetection", "objects.json", objects_to_json(objects)),
    ):
        key = keys.run_artifact(scene.project.id, floor.level_id, upload.id, run.id, step, name)
        await storage.put(key, body, content_type="application/json", max_bytes=len(body))


async def test_spatial_read_dimension_strings__C01(
    api_client: httpx.AsyncClient, db_session: AsyncSession, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """Chữ toàn số 300-30 000 mm của lượt mới nhất; hướng theo tỉ lệ cạnh hộp; không `spanPx`."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    await _run_with_artifacts(db_session, local_storage, fake_clock, scene=scene, floor=floor)
    await db_session.commit()
    response = await api_client.get(
        _path(scene.project.id, floor.level_id, "dimension-strings"), headers=headers_of(scene.owner)
    )
    assert response.status_code == 200
    body = response.json()
    assert body["runId"].startswith("run")
    assert body["pagePx"] == [200, 100]
    assert body["items"] == [
        {
            "id": "dim-0",
            "text": "3.600",
            "valueMm": 3600,
            "box": {"xMin": 10.0, "yMin": 10.0, "xMax": 50.0, "yMax": 20.0},
            "confidence": 0.9,
            "orientation": "horizontal",
        },
        {
            "id": "dim-1",
            "text": "1 200",
            "valueMm": 1200,
            "box": {"xMin": 5.0, "yMin": 30.0, "xMax": 15.0, "yMax": 80.0},
            "confidence": 0.8,
            "orientation": "vertical",
        },
    ]


async def test_spatial_read_detected_geometry__C01(
    api_client: httpx.AsyncClient, db_session: AsyncSession, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """Điểm bắt (đầu + giao, gộp < 3 px), bề dày median/p90, cửa, phòng lớn nhất theo px, hộp ngoài."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    layer = sample_floor_layer(0, level_id=floor.level_id)
    await make_floor_document(
        db_session, floor_pk=floor.pk, layer=layer, scale=Decimal("12.5"), scale_source="human", clock=fake_clock
    )
    await _run_with_artifacts(db_session, local_storage, fake_clock, scene=scene, floor=floor)
    await db_session.commit()
    response = await api_client.get(
        _path(scene.project.id, floor.level_id, "detected-geometry"), headers=headers_of(scene.owner)
    )
    assert response.status_code == 200
    body = response.json()
    assert body["pagePx"] == [200, 100]
    assert body["wallThicknessPx"] == {"median": 5.0, "p90": 6.0}
    assert body["snapPoints"] == [
        {"x": 10.0, "y": 10.0, "kind": "wallEnd"},
        {"x": 110.0, "y": 10.0, "kind": "junction"},
        {"x": 60.0, "y": 0.0, "kind": "wallEnd"},
        {"x": 60.0, "y": 50.0, "kind": "wallEnd"},
        {"x": 110.0, "y": 60.0, "kind": "wallEnd"},
        {"x": 60.0, "y": 10.0, "kind": "junction"},
    ]
    assert body["doors"] == [
        {
            "id": "door-0",
            "box": {"xMin": 0.0, "yMin": 0.0, "xMax": 30.0, "yMax": 8.0},
            "widthPx": 30.0,
            "confidence": 0.9,
        },
        {
            "id": "door-2",
            "box": {"xMin": 100.0, "yMin": 20.0, "xMax": 108.0, "yMax": 60.0},
            "widthPx": 40.0,
            "confidence": 0.7,
        },
    ]
    room = max(layer.rooms, key=lambda candidate: candidate.area_m2)
    assert body["largestRoom"]["roomId"] == room.id
    assert body["largestRoom"]["label"] == room.name
    assert body["largestRoom"]["boxPx"]["xMin"] == round(min(p.x for p in room.outline) / 12.5, 1)
    assert body["outerBoxPx"] == {"xMin": 10.0, "yMin": 0.0, "xMax": 110.0, "yMax": 60.0}


async def test_spatial_read_dimension_strings__C17(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Chưa có lượt → `runId`/`pagePx` **có khoá**, giá trị `null`; `items: []` (không lỗi)."""
    scene = await make_scene(db_session)
    response = await api_client.get(
        _path(scene.project.id, scene.floors[0].level_id, "dimension-strings"), headers=headers_of(scene.owner)
    )
    assert response.status_code == 200
    assert response.json() == {"runId": None, "pagePx": None, "items": []}


async def test_spatial_read_detected_geometry__C17(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Chưa có lượt, chưa có lớp → mọi danh sách rỗng, hộp/bề dày/phòng `null` có khoá."""
    scene = await make_scene(db_session)
    response = await api_client.get(
        _path(scene.project.id, scene.floors[0].level_id, "detected-geometry"), headers=headers_of(scene.owner)
    )
    assert response.status_code == 200
    assert response.json() == {
        "pagePx": None,
        "wallThicknessPx": None,
        "snapPoints": [],
        "doors": [],
        "largestRoom": None,
        "outerBoxPx": None,
    }


async def _outsider_status(api_client: httpx.AsyncClient, db_session: AsyncSession, op: str) -> httpx.Response:
    scene = await make_scene(db_session)
    outsider = await make_user(db_session, role="admin")
    await db_session.commit()
    return await api_client.get(_path(scene.project.id, scene.floors[0].level_id, op), headers=headers_of(outsider))


async def test_spatial_read_dimension_strings__C06(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Admin hệ thống ngoài dự án → 404 `resource:"project"` (K08)."""
    response = await _outsider_status(api_client, db_session, "dimension-strings")
    assert response.status_code == 404
    assert response.json()["resource"] == "project"


async def test_spatial_read_detected_geometry__C06(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Admin hệ thống ngoài dự án → 404 `resource:"project"` (K08)."""
    response = await _outsider_status(api_client, db_session, "detected-geometry")
    assert response.status_code == 404
    assert response.json()["resource"] == "project"


async def _floor_404(
    api_client: httpx.AsyncClient, db_session: AsyncSession, clock: FakeClock, case: str, op: str
) -> httpx.Response:
    scene = await make_scene(db_session)
    other = await make_scene(db_session)
    floor_id = "L-NOSUCHFLOOR"
    if case == "deleted":
        floor_id = scene.floors[0].level_id
        await db_session.execute(
            update(FloorRow).where(FloorRow.pk == scene.floors[0].pk).values(deleted_at=clock.now())
        )
        await db_session.commit()
    elif case == "other_project":
        floor_id = other.floors[0].level_id
    return await api_client.get(_path(scene.project.id, floor_id, op), headers=headers_of(scene.owner))


@pytest.mark.parametrize("case", ["missing", "deleted", "other_project"])
async def test_spatial_read_dimension_strings__C08(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock, case: str
) -> None:
    """Tầng không có, đã xoá mềm, hay của dự án khác → 404 `resource:"floor"`."""
    response = await _floor_404(api_client, db_session, fake_clock, case, "dimension-strings")
    assert response.status_code == 404
    assert response.json()["resource"] == "floor"


@pytest.mark.parametrize("case", ["missing", "deleted", "other_project"])
async def test_spatial_read_detected_geometry__C08(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock, case: str
) -> None:
    """Tầng không có, đã xoá mềm, hay của dự án khác → 404 `resource:"floor"`."""
    response = await _floor_404(api_client, db_session, fake_clock, case, "detected-geometry")
    assert response.status_code == 404
    assert response.json()["resource"] == "floor"


@pytest.mark.parametrize("op", OPS)
async def test_detected_routes_require_login(api_client: httpx.AsyncClient, db_session: AsyncSession, op: str) -> None:
    """Không đăng nhập → 401."""
    scene = await make_scene(db_session)
    response = await api_client.get(_path(scene.project.id, scene.floors[0].level_id, op))
    assert response.status_code == 401
