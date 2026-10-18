"""N7b `GET /api/projects/{project_id}/pipeline-runs` (UIFIX-B7, N5-08): lịch sử lượt chạy, mới nhất trước.

Mồi như `test_routes_latest.py`: mỗi lượt mồi `commit` **và** đẩy `fake_clock` một giây để
`created_at` (Postgres `now()`) và ULID của `run_` cùng tiến.
"""

from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.drawings.progress import FIRST_STEP
from apps.api.drawings.runs import RunRow, record_step, start_run
from apps.api.drawings.tests._helpers import Scene, make_scene
from apps.api.drawings.tests._helpers import sync_bus_reset as sync_bus_reset
from apps.api.projects.tests.test_routes_common import headers_of
from packages.db.models.floors import FloorRow
from packages.storage.local import LocalDiskStorage
from packages.testing.factories.drawings import make_complete_upload, png_bytes
from packages.testing.factories.floors import make_floor
from packages.testing.fixtures.clock import FakeClock

PNG = png_bytes(40, 30)


def runs_path(project_id: str) -> str:
    """Đường N7b của một dự án."""
    return f"/api/projects/{project_id}/pipeline-runs"


async def _tick(db: AsyncSession, clock: FakeClock) -> None:
    """Đóng giao dịch mồi và đẩy đồng hồ: hai lượt mồi liền nhau phải khác `created_at`."""
    await db.commit()
    clock.advance(timedelta(seconds=1))


async def _run(
    db: AsyncSession, storage: LocalDiskStorage, scene: Scene, clock: FakeClock, *, floor: FloorRow | None = None
) -> RunRow:
    """Một lượt tải `complete` cộng một lượt chạy `pending` trên tầng `floor` (mặc định tầng của scene)."""
    upload = await make_complete_upload(db, storage, project=scene.project, floor=floor or scene.floor, data=PNG)
    run = await start_run(db, upload_id=upload.id, clock=clock)
    await _tick(db, clock)
    return run


async def test_drawings_list_pipeline_runs__C01(
    db_session: AsyncSession,
    local_storage: LocalDiskStorage,
    api_client: AsyncClient,
    fake_clock: FakeClock,
    sync_bus_reset: None,
) -> None:
    """Hai tầng, ba lượt (một lượt bị thay, một lượt hỏng) → ba mục mới nhất trước, đủ trường."""
    scene = await make_scene(db_session)
    upper = await make_floor(db_session, project=scene.project, order=1, name="Tầng 2")
    await _tick(db_session, fake_clock)
    old = await _run(db_session, local_storage, scene, fake_clock)
    newer = await _run(db_session, local_storage, scene, fake_clock)
    failing = await _run(db_session, local_storage, scene, fake_clock, floor=upper)
    await record_step(db_session, run_id=failing.id, step=FIRST_STEP, status="running", clock=fake_clock)
    await _tick(db_session, fake_clock)
    await record_step(db_session, run_id=failing.id, step=FIRST_STEP, status="failed", clock=fake_clock, error_code="BOOM")
    await _tick(db_session, fake_clock)

    response = await api_client.get(runs_path(scene.project.id), headers=headers_of(scene.user))

    assert response.status_code == 200
    body = response.json()
    assert [item["runId"] for item in body["items"]] == [failing.id, newer.id, old.id]
    assert "nextCursor" not in body
    top = body["items"][0]
    assert (top["floorId"], top["floorName"], top["status"], top["errorCode"]) == (
        upper.level_id,
        "Tầng 2",
        "failed",
        "BOOM",
    )
    assert top["startedAt"].endswith("Z")
    assert top["updatedAt"].endswith("Z")
    assert "endedAt" not in top  # K33: lượt hỏng không có `endedAt`
    assert body["items"][2]["supersededBy"] == newer.id
    assert body["items"][1]["step"] == FIRST_STEP


async def test_drawings_list_pipeline_runs__C06(
    db_session: AsyncSession,
    local_storage: LocalDiskStorage,
    api_client: AsyncClient,
    fake_clock: FakeClock,
    sync_bus_reset: None,
) -> None:
    """Người ngoài dự án (kể cả vai `admin` hệ thống) → 404 `resource:"project"` (K08)."""
    scene = await make_scene(db_session)
    outsider = await make_scene(db_session)
    await _run(db_session, local_storage, scene, fake_clock)

    response = await api_client.get(runs_path(scene.project.id), headers=headers_of(outsider.user, role="admin"))
    assert response.status_code == 404
    assert response.json()["resource"] == "project"


async def test_drawings_list_pipeline_runs__C08(
    db_session: AsyncSession, api_client: AsyncClient, fake_clock: FakeClock
) -> None:
    """Dự án không tồn tại → 404."""
    scene = await make_scene(db_session)
    await _tick(db_session, fake_clock)
    response = await api_client.get(runs_path("prj_" + "0" * 26), headers=headers_of(scene.user))
    assert response.status_code == 404


async def test_drawings_list_pipeline_runs__C15_empty(
    db_session: AsyncSession, api_client: AsyncClient, fake_clock: FakeClock
) -> None:
    """Chưa có lượt chạy nào → `{"items": []}`, không `nextCursor`."""
    scene = await make_scene(db_session)
    await _tick(db_session, fake_clock)
    response = await api_client.get(runs_path(scene.project.id), headers=headers_of(scene.user))
    assert response.status_code == 200
    assert response.json() == {"items": []}


async def test_drawings_list_pipeline_runs__C15(
    db_session: AsyncSession,
    local_storage: LocalDiskStorage,
    api_client: AsyncClient,
    fake_clock: FakeClock,
    sync_bus_reset: None,
) -> None:
    """Ba lượt với `limit=2` → trang đầu hai mục mới nhất + `nextCursor`, trang sau lượt cũ nhất."""
    scene = await make_scene(db_session)
    runs = [await _run(db_session, local_storage, scene, fake_clock) for _ in range(3)]

    first = await api_client.get(runs_path(scene.project.id), headers=headers_of(scene.user), params={"limit": 2})
    assert first.status_code == 200
    page_one = first.json()
    assert [item["runId"] for item in page_one["items"]] == [runs[2].id, runs[1].id]
    assert page_one["nextCursor"]

    second = await api_client.get(
        runs_path(scene.project.id),
        headers=headers_of(scene.user),
        params={"limit": 2, "cursor": page_one["nextCursor"]},
    )
    assert second.status_code == 200
    page_two = second.json()
    assert [item["runId"] for item in page_two["items"]] == [runs[0].id]
    assert "nextCursor" not in page_two


async def test_drawings_list_pipeline_runs__C15_foreign_cursor(
    db_session: AsyncSession,
    local_storage: LocalDiskStorage,
    api_client: AsyncClient,
    fake_clock: FakeClock,
    sync_bus_reset: None,
) -> None:
    """Cursor của dự án khác hay cursor bịa → 422 `CURSOR_INVALID`."""
    scene = await make_scene(db_session)
    other = await make_scene(db_session)
    for _ in range(2):
        await _run(db_session, local_storage, other, fake_clock)
    page = await api_client.get(runs_path(other.project.id), headers=headers_of(other.user), params={"limit": 1})
    foreign = page.json()["nextCursor"]

    for cursor in (foreign, "khong-phai-cursor"):
        response = await api_client.get(
            runs_path(scene.project.id), headers=headers_of(scene.user), params={"cursor": cursor}
        )
        assert response.status_code == 422
        assert response.json()["code"] == "CURSOR_INVALID"


async def test_drawings_list_pipeline_runs__C17(
    db_session: AsyncSession,
    local_storage: LocalDiskStorage,
    api_client: AsyncClient,
    fake_clock: FakeClock,
    sync_bus_reset: None,
) -> None:
    """Lượt `pending` chưa chạy → `startedAt`, `endedAt`, `errorCode`, `supersededBy` **vắng khoá** (W2)."""
    scene = await make_scene(db_session)
    await _run(db_session, local_storage, scene, fake_clock)
    response = await api_client.get(runs_path(scene.project.id), headers=headers_of(scene.user))
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["status"] == "pending"
    assert {"startedAt", "endedAt", "errorCode", "supersededBy"}.isdisjoint(item)


async def test_drawings_list_pipeline_runs__C15_deleted_floor_hidden(
    db_session: AsyncSession,
    local_storage: LocalDiskStorage,
    api_client: AsyncClient,
    fake_clock: FakeClock,
    sync_bus_reset: None,
) -> None:
    """Lượt của tầng đã xoá mềm không hiện (như N7)."""
    scene = await make_scene(db_session)
    await _run(db_session, local_storage, scene, fake_clock)
    scene.floor.deleted_at = fake_clock.now()
    await _tick(db_session, fake_clock)
    response = await api_client.get(runs_path(scene.project.id), headers=headers_of(scene.user))
    assert response.status_code == 200
    assert response.json() == {"items": []}


@pytest.mark.parametrize("limit", [0, 201])
async def test_drawings_list_pipeline_runs__C15_limit_out_of_range(
    db_session: AsyncSession, api_client: AsyncClient, fake_clock: FakeClock, limit: int
) -> None:
    """`limit` ngoài `1…200` → 422 `VALIDATION`."""
    scene = await make_scene(db_session)
    await _tick(db_session, fake_clock)
    response = await api_client.get(runs_path(scene.project.id), headers=headers_of(scene.user), params={"limit": limit})
    assert response.status_code == 422
