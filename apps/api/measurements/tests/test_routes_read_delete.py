"""Test hợp đồng của #16 `measurements_list_records` và #18 `measurements_delete_record` (B2-07 [2], [6], [8]).

Ma trận case: #16 Đ → C01 C06 C08 C15 C17; #18 G → C01 C06 C07 C08 (C16 miễn trong `cases.toml`). Cộng
test đặt tên theo việc: thứ tự số, #16 với trần thật (1000 x 20 điểm) < 2 s, chéo dự án, `touch_project`.
"""

import logging
import time
from datetime import timedelta

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.measurements.settings import reset_measurements_settings_cache
from apps.api.measurements.tests._helpers import (
    FORBIDDEN_ROLE,
    LIMIT_TEST,
    floor_area_body,
    headers_of,
    measurement_path,
    measurement_rows,
    measurements_path,
    project_updated_at,
    record_body,
    seed_project,
    with_env,
)
from packages.db.models.measurements import MeasurementRow
from packages.testing.factories.auth import make_user
from packages.testing.fixtures.clock import FakeClock

_log = logging.getLogger(__name__)
PERF_LIMIT_S = 2.0
PERF_COUNT = 1000
PERF_POINTS = 20

# ---------------------------------------------------------------------------
# #16 Đ: C01 C06 C08 C15 C17
# ---------------------------------------------------------------------------


async def test_measurements_list_records__C01(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Thân FE thật của hai chế độ → mảng trần, đúng bản đã ghim, không `bodySha256`/`createdBy`/`updatedAt`."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    headers = headers_of(owner)
    bodies = [record_body(), floor_area_body()]
    for body in bodies:
        await api_client.post(measurements_path(project.id), json=body, headers=headers)
    response = await api_client.get(measurements_path(project.id), headers=headers)
    assert response.status_code == 200
    assert response.json() == bodies


async def test_measurements_list_records__C06(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Admin hệ thống không là thành viên → 404 `resource:"project"`."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    outsider = await make_user(db_session, role="admin")
    response = await api_client.get(measurements_path(project.id), headers=headers_of(outsider))
    assert (response.status_code, response.json()["resource"]) == (404, "project")


async def test_measurements_list_records__C08(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Dự án đã xoá mềm → 404."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner, deleted_at=fake_clock.now())
    response = await api_client.get(measurements_path(project.id), headers=headers_of(owner))
    assert response.status_code == 404


@pytest.mark.parametrize("count", [0, 1, LIMIT_TEST])
async def test_measurements_list_records__C15(
    api_client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, count: int
) -> None:
    """Trần = 3: 0, 1, 3 mục trả trọn đúng số lượng; mục thứ 4 → 422 `MEASUREMENT_LIMIT_REACHED`, danh sách vẫn 3."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    headers = headers_of(owner)
    with with_env(monkeypatch, reset_measurements_settings_cache, MEASUREMENTS_MAX=LIMIT_TEST):
        for number in range(1, count + 1):
            await api_client.post(measurements_path(project.id), json=record_body(f"MS-{number:04d}"), headers=headers)
        listed = await api_client.get(measurements_path(project.id), headers=headers)
        assert [item["id"] for item in listed.json()] == [f"MS-{n:04d}" for n in range(1, count + 1)]
        if count == LIMIT_TEST:
            over = await api_client.post(measurements_path(project.id), json=record_body("MS-0004"), headers=headers)
            assert (over.status_code, over.json()["code"]) == (422, "MEASUREMENT_LIMIT_REACHED")
            assert len((await api_client.get(measurements_path(project.id), headers=headers)).json()) == LIMIT_TEST


async def test_measurements_list_records__C17(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Điểm không `z` → khoá `z` vắng trong danh sách, không `null`."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    headers = headers_of(owner)
    await api_client.post(measurements_path(project.id), json=record_body(), headers=headers)
    response = await api_client.get(measurements_path(project.id), headers=headers)
    assert all("z" not in point for point in response.json()[0]["points"])
    assert "null" not in response.text


async def test_measurements_list_records__numeric_id_order(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Thứ tự số của id: `MS-10000` đứng sau `MS-9999` (sắp chữ sẽ đặt nó trước)."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    headers = headers_of(owner)
    for record_id in ("MS-10000", "MS-9999", "MS-0001"):
        await api_client.post(measurements_path(project.id), json=record_body(record_id), headers=headers)
    response = await api_client.get(measurements_path(project.id), headers=headers)
    assert [item["id"] for item in response.json()] == ["MS-0001", "MS-9999", "MS-10000"]


async def test_measurements_list_records__isolated_per_project(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Phép đo của dự án khác không lọt vào danh sách."""
    owner = await make_user(db_session, role="engineer")
    mine = await seed_project(db_session, owner=owner)
    other = await seed_project(db_session, owner=owner)
    headers = headers_of(owner)
    await api_client.post(measurements_path(other.id), json=record_body("MS-0007"), headers=headers)
    response = await api_client.get(measurements_path(mine.id), headers=headers)
    assert response.json() == []


@pytest.mark.perf
async def test_measurements_list_records__real_limit_under_two_seconds(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Trần thật: 1000 phép đo x 20 điểm (= tổng điểm trần 20000) trả đủ, < 2 s."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    points = [{"x": float(i), "y": float(i) * 2, "z": 1.0} for i in range(PERF_POINTS)]
    for number in range(1, PERF_COUNT + 1):
        db_session.add(
            MeasurementRow(
                project_id=project.id,
                measurement_id=f"MS-{number:04d}",
                name=f"Phép đo {number}",
                mode="pointToPoint",
                points=points,
                raw_value=float(number),
                body_sha256="0" * 64,
                created_by=owner.id,
            )
        )
    await db_session.commit()
    started = time.perf_counter()
    response = await api_client.get(measurements_path(project.id), headers=headers_of(owner))
    elapsed = time.perf_counter() - started
    assert response.status_code == 200
    assert len(response.json()) == PERF_COUNT
    _log.info("measurements_list_elapsed_s=%.3f count=%d", elapsed, PERF_COUNT)
    assert elapsed < PERF_LIMIT_S


# ---------------------------------------------------------------------------
# #18 G: C01 C06 C07 C08; waive C16
# ---------------------------------------------------------------------------


async def test_measurements_delete_record__C01(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Xoá → 204 thân rỗng; dòng bị xoá **cứng**, dòng khác còn (K22)."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    headers = headers_of(owner)
    for record_id in ("MS-0001", "MS-0002"):
        await api_client.post(measurements_path(project.id), json=record_body(record_id), headers=headers)
    response = await api_client.delete(measurement_path(project.id, "MS-0001"), headers=headers)
    assert (response.status_code, response.content) == (204, b"")
    assert [row.measurement_id for row in await measurement_rows(db_sessionmaker, project.id)] == ["MS-0002"]


async def test_measurements_delete_record__C06(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Admin hệ thống không là thành viên, id có thật → 404 `resource:"project"` (K08)."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    await api_client.post(measurements_path(project.id), json=record_body(), headers=headers_of(owner))
    outsider = await make_user(db_session, role="admin")
    response = await api_client.delete(measurement_path(project.id, "MS-0001"), headers=headers_of(outsider))
    assert (response.status_code, response.json()["resource"]) == (404, "project")


async def test_measurements_delete_record__C07(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """`viewer` → 403 và dòng còn nguyên."""
    owner = await make_user(db_session, role="engineer")
    viewer = await make_user(db_session, role=FORBIDDEN_ROLE)
    project = await seed_project(db_session, owner=owner, members=[viewer])
    await api_client.post(measurements_path(project.id), json=record_body(), headers=headers_of(owner))
    response = await api_client.delete(measurement_path(project.id, "MS-0001"), headers=headers_of(viewer))
    assert response.status_code == 403
    assert len(await measurement_rows(db_sessionmaker, project.id)) == 1


@pytest.mark.parametrize("missing_id", ["MS-9999", "MS-12", "MS-9999999999999999", "xyz"])
async def test_measurements_delete_record__C08(
    api_client: httpx.AsyncClient, db_session: AsyncSession, missing_id: str
) -> None:
    """`MS-9999` không có, hoặc id sai mẫu → 404 `resource:"measurement"`."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    response = await api_client.delete(measurement_path(project.id, missing_id), headers=headers_of(owner))
    assert (response.status_code, response.json()["resource"]) == (404, "measurement")


async def test_measurements_delete_record__C08_deleted_project(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Dự án đã xoá mềm → 404 `resource:"project"`."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner, deleted_at=fake_clock.now())
    response = await api_client.delete(measurement_path(project.id, "MS-0001"), headers=headers_of(owner))
    assert (response.status_code, response.json()["resource"]) == (404, "project")


async def test_measurements_delete_record__other_project_id_not_deletable(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """`MS-0001` của dự án A không xoá được qua đường của dự án B (404), dòng còn nguyên."""
    owner = await make_user(db_session, role="engineer")
    project_a = await seed_project(db_session, owner=owner)
    project_b = await seed_project(db_session, owner=owner)
    headers = headers_of(owner)
    await api_client.post(measurements_path(project_a.id), json=record_body(), headers=headers)
    response = await api_client.delete(measurement_path(project_b.id, "MS-0001"), headers=headers)
    assert (response.status_code, response.json()["resource"]) == (404, "measurement")
    assert len(await measurement_rows(db_sessionmaker, project_a.id)) == 1


async def test_measurements_delete_record__touch_project(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
) -> None:
    """`touch_project` chạy khi xoá được (204), không chạy khi 404 (đo bằng `projects.updated_at`)."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    headers = headers_of(owner)
    await api_client.post(measurements_path(project.id), json=record_body(), headers=headers)
    before = await project_updated_at(db_sessionmaker, project.id)

    fake_clock.advance(timedelta(hours=1))
    assert (await api_client.delete(measurement_path(project.id, "MS-0002"), headers=headers)).status_code == 404
    assert await project_updated_at(db_sessionmaker, project.id) == before

    assert (await api_client.delete(measurement_path(project.id, "MS-0001"), headers=headers)).status_code == 204
    assert await project_updated_at(db_sessionmaker, project.id) == fake_clock.now()
