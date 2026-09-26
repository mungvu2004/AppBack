"""#32 `POST …/quality/straighten` — ma trận case G và phần "Nắn" của [8]."""

from typing import Any

import httpx
import pytest
from redis import Redis as SyncRedis
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.projects.tests.test_routes_common import headers_of
from apps.api.quality.tests._images import straight_drawing, tilted_drawing
from apps.api.quality.tests._route_helpers import (
    CPU_QUEUE,
    Stage,
    floor_view,
    make_stage,
    measure_real,
    read_path,
    run_count,
    runs_of,
    straighten_path,
)
from apps.api.quality.tests._route_helpers import (
    broker as broker,
)
from apps.api.quality.tests._route_helpers import (
    quality_env as quality_env,
)
from packages.core.clock import Clock
from packages.db.models.floors import FloorRow
from packages.storage.local import LocalDiskStorage
from packages.testing.factories.auth import make_user
from packages.testing.factories.floors import make_floor
from packages.testing.fixtures.messaging import queued_payloads
from packages.vision.preprocess import Homography

TILTED = tilted_drawing(4.0, 900, 640)
STRAIGHT = straight_drawing(900, 640)


async def _post(
    client: httpx.AsyncClient, stage: Stage, *, index: int = 0, headers: dict[str, str] | None = None, body: Any = None
) -> httpx.Response:
    """#32 trên tầng `index`; thân mặc định `{}`."""
    return await client.post(
        straighten_path(stage.project.id, stage.level(index)),
        json={} if body is None else body,
        headers=headers or stage.headers,
    )


async def _view(client: httpx.AsyncClient, stage: Stage, index: int = 0) -> dict[str, Any]:
    """Phần tử `floors` của tầng `index` đọc bằng #30."""
    response = await client.get(read_path(stage.project.id, stage.level(index)), headers=stage.headers)
    return floor_view(response, stage.level(index))


async def test_quality_straighten__C01(
    api_client: httpx.AsyncClient, db_session: AsyncSession, local_storage: LocalDiskStorage, fake_clock: Clock
) -> None:
    """Trang nghiêng 4° → 200 `ImageQualityAssessment` (golden H1) của trang đã nắn."""
    stage = await make_stage(db_session, local_storage, pixels=TILTED)
    await measure_real(db_session, fake_clock, stage.floors[0], TILTED)

    response = await _post(api_client, stage)

    assert response.status_code == 200, response.text
    assert floor_view(response, stage.level())["isMeasured"] is True


async def test_quality_straighten__deskews_and_renews_finding_ids(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: Clock,
) -> None:
    """Ảnh nghiêng 4° → `skewDeg` mới < 0,5, `finding.id` đều khác id trước, đúng một lượt mới."""
    stage = await make_stage(db_session, local_storage, pixels=TILTED)
    await measure_real(db_session, fake_clock, stage.floors[0], TILTED)
    before = await _view(api_client, stage)
    assert abs(before["measurement"]["skewDeg"]) > 1

    response = await _post(api_client, stage)

    after = floor_view(response, stage.level())
    assert abs(after["measurement"]["skewDeg"]) < 0.5
    assert {item["id"] for item in before["findings"]}.isdisjoint(item["id"] for item in after["findings"])
    assert after["sourceUrl"] != before["sourceUrl"]
    assert await run_count(db_sessionmaker, stage.floors[0].floor.pk) == 2


async def test_quality_straighten__already_straight_is_a_noop(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: Clock,
) -> None:
    """Ảnh thẳng, đã đo, không `SKEW_DETECTED` → 200 hiện trạng, không lượt mới, không đổi trang."""
    stage = await make_stage(db_session, local_storage, pixels=STRAIGHT)
    await measure_real(db_session, fake_clock, stage.floors[0], STRAIGHT)
    before = await _view(api_client, stage)

    response = await _post(api_client, stage)

    assert response.status_code == 200, response.text
    assert floor_view(response, stage.level()) == before
    assert await run_count(db_sessionmaker, stage.floors[0].floor.pk) == 1


async def test_quality_straighten__unmeasured_is_processed(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
) -> None:
    """Chưa đo (chưa có dòng đo) → xử lý: homography đơn vị, ra trang đã đo và một lượt mới."""
    stage = await make_stage(db_session, local_storage, pixels=TILTED)

    response = await _post(api_client, stage)

    assert response.status_code == 200, response.text
    assert floor_view(response, stage.level())["isMeasured"] is True
    assert await run_count(db_sessionmaker, stage.floors[0].floor.pk) == 1


async def test_quality_straighten__stored_homography_mismatch_is_409(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: Clock,
) -> None:
    """Homography đã lưu lệch kích thước trang → 409 `QUALITY_DRAWING_CHANGED`, không lượt mới."""
    stage = await make_stage(db_session, local_storage, pixels=TILTED)
    height, width = TILTED.shape[:2]
    stale = Homography.identity(width + 10, height).to_json()
    await measure_real(db_session, fake_clock, stage.floors[0], TILTED, homography=stale)

    response = await _post(api_client, stage)

    assert response.status_code == 409, response.text
    assert response.json()["code"] == "QUALITY_DRAWING_CHANGED"
    assert await run_count(db_sessionmaker, stage.floors[0].floor.pk) == 1


@pytest.mark.parametrize("body", [[1], "x", 5])
async def test_quality_straighten__C02(
    api_client: httpx.AsyncClient, db_session: AsyncSession, local_storage: LocalDiskStorage, body: Any
) -> None:
    """Thân khác object → 422 `VALIDATION`."""
    stage = await make_stage(db_session, local_storage)

    response = await _post(api_client, stage, body=body)

    assert response.status_code == 422, response.text
    assert response.json()["code"] == "VALIDATION"


async def test_quality_straighten__C03(
    api_client: httpx.AsyncClient, db_session: AsyncSession, local_storage: LocalDiskStorage
) -> None:
    """Khoá lạ → 422 `VALIDATION`."""
    stage = await make_stage(db_session, local_storage)

    response = await _post(api_client, stage, body={"angle": 3})

    assert response.status_code == 422, response.text
    assert response.json()["code"] == "VALIDATION"


async def test_quality_straighten__C06(
    api_client: httpx.AsyncClient, db_session: AsyncSession, local_storage: LocalDiskStorage
) -> None:
    """Người ngoài dự án, kể cả admin hệ thống → 404 `project`."""
    stage = await make_stage(db_session, local_storage)
    admin = await make_user(db_session, role="admin")
    await db_session.commit()

    response = await _post(api_client, stage, headers=headers_of(admin))

    assert response.status_code == 404, response.text
    assert response.json()["resource"] == "project"


async def test_quality_straighten__C07(
    api_client: httpx.AsyncClient, db_session: AsyncSession, local_storage: LocalDiskStorage
) -> None:
    """Viewer → 403 `FORBIDDEN`."""
    stage = await make_stage(db_session, local_storage)

    response = await _post(api_client, stage, headers=stage.viewer_headers)

    assert response.status_code == 403, response.text
    assert response.json()["code"] == "FORBIDDEN"


async def test_quality_straighten__C08(
    api_client: httpx.AsyncClient, db_session: AsyncSession, local_storage: LocalDiskStorage
) -> None:
    """Tầng không có, tầng đã xoá → 404 `floor`; tầng chưa có bản vẽ → 404 `upload`."""
    stage = await make_stage(db_session, local_storage, floors=2)
    bare = await make_floor(db_session, project=stage.project)
    await db_session.execute(
        update(FloorRow).where(FloorRow.pk == stage.floors[1].floor.pk).values(deleted_at=FloorRow.created_at)
    )
    await db_session.commit()
    project = stage.project.id

    missing = await api_client.post(straighten_path(project, "L-NOSUCHFLOOR0"), json={}, headers=stage.headers)
    deleted = await _post(api_client, stage, index=1)
    no_drawing = await api_client.post(straighten_path(project, bare.level_id), json={}, headers=stage.headers)

    assert [r.status_code for r in (missing, deleted, no_drawing)] == [404, 404, 404]
    assert [r.json()["resource"] for r in (missing, deleted, no_drawing)] == ["floor", "floor", "upload"]


async def test_quality_straighten__C17(
    api_client: httpx.AsyncClient, db_session: AsyncSession, local_storage: LocalDiskStorage
) -> None:
    """Sau #32: không `null`, không `expectedConfidence`; tầng khác chưa đo vắng `measurement`, `frame`."""
    stage = await make_stage(db_session, local_storage, floors=2, pixels=TILTED)

    response = await _post(api_client, stage)

    assert response.status_code == 200, response.text
    assert "null" not in response.text
    assert "expectedConfidence" not in response.text
    other = floor_view(response, stage.level(1))
    assert other["isMeasured"] is False
    assert "measurement" not in other
    assert "frame" not in other


async def test_quality_straighten__C10_queue_once(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: Clock,
    broker: SyncRedis,
) -> None:
    """Lặp `Idempotency-Key` → cùng response, **một** lượt mới và **một** thông điệp `pipeline.cpu`."""
    stage = await make_stage(db_session, local_storage, pixels=TILTED)
    await measure_real(db_session, fake_clock, stage.floors[0], TILTED)
    broker.delete(CPU_QUEUE)
    headers = {**stage.headers, "Idempotency-Key": "b2-05b-straighten-once"}

    first = await _post(api_client, stage, headers=headers)
    second = await _post(api_client, stage, headers=headers)

    assert (first.status_code, second.status_code) == (200, 200), (first.text, second.text)
    assert first.json() == second.json()
    assert await run_count(db_sessionmaker, stage.floors[0].floor.pk) == 2
    assert len(queued_payloads(broker, CPU_QUEUE)) == 1


async def test_quality_straighten__C10_no_key_replay(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: Clock,
    broker: SyncRedis,
) -> None:
    """Không khoá: lượt lặp trên trang đã thẳng không làm gì; mỗi lượt có xử lý tạo đúng một lượt và một thông điệp."""
    stage = await make_stage(db_session, local_storage, floors=2, pixels=TILTED)
    for drawn in stage.floors:
        await measure_real(db_session, fake_clock, drawn, TILTED)
    broker.delete(CPU_QUEUE)

    first = await _post(api_client, stage)
    replay = await _post(api_client, stage)
    other = await _post(api_client, stage, index=1)

    assert [r.status_code for r in (first, replay, other)] == [200, 200, 200]
    assert replay.json() == first.json()
    runs = await runs_of(db_sessionmaker, stage.floors[0].floor.pk)
    assert [(run.status, run.error_code) for run in runs] == [("failed", "PIPELINE_SUPERSEDED"), ("pending", None)]
    second_floor = await runs_of(db_sessionmaker, stage.floors[1].floor.pk)
    assert sorted(str(p["run_id"]) for p in queued_payloads(broker, CPU_QUEUE)) == sorted(
        [runs[1].id, second_floor[1].id]
    )
