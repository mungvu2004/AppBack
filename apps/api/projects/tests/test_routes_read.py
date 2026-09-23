"""Test hợp đồng của #23 `projects_list_projects`, #24 `projects_read_project`,
N1 `projects_list_summaries` (B2-01 [2], [6], [8]).

Route (`router.py`, `service.py`) chưa hợp nhất trên nhánh này (việc M) — mỗi hàm ở đây chỉ
mồi dữ liệu qua factory/model của N và gọi HTTP theo đúng hợp đồng; M hiện thực để các test
này xanh. Không nhập `router`, `service`, `memberships`, `summaries`, `access`, `jobs`.
"""

from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Final

import httpx
import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.pagination import encode_cursor
from apps.api.projects.settings import get_projects_settings, reset_projects_settings_cache
from apps.api.projects.tests.test_routes_common import (
    PROJECTS_PATH,
    SUMMARIES_PATH,
    headers_of,
    project_path,
    seed_floor,
    seed_project,
)
from packages.db.models.projects import Project
from packages.testing.factories.auth import make_user
from packages.testing.fixtures.clock import FakeClock

LIST_SUMMARIES_OP: Final = "projects_list_summaries"


@pytest.fixture
def _list_max_3(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """C15 của #23 đặt `PROJECTS_LIST_MAX = 3` (B2-01 [8]); cache xoá cả trước lẫn sau."""
    monkeypatch.setenv("PROJECTS_LIST_MAX", "3")
    reset_projects_settings_cache()
    yield
    reset_projects_settings_cache()


async def _touch(db: AsyncSession, project: Project, at: datetime) -> None:
    """Đặt `updated_at` tường minh (giá trị Python trong `values()` thắng `onupdate`), để C15
    dựng thứ tự tất định thay vì trông vào `now()` của Postgres chạy sát nhau."""
    await db.execute(update(Project).where(Project.id == project.id).values(updated_at=at))
    await db.commit()


# ---------------------------------------------------------------------------
# #23 GET /api/projects — Đ*: C01 C15 C17
# ---------------------------------------------------------------------------


async def test_projects_list_projects__C01(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Đúng: dự án mình là thành viên có mặt, đủ khoá hợp đồng, ghi golden qua H1."""
    owner = await make_user(db_session)
    project = await seed_project(db_session, owner=owner)
    response = await api_client.get(PROJECTS_PATH, headers=headers_of(owner))
    assert response.status_code == 200
    items = response.json()
    assert any(item["id"] == project.id for item in items)
    item = next(item for item in items if item["id"] == project.id)
    assert set(item) >= {"id", "name", "createdAt", "updatedAt", "status", "floors", "members"}


@pytest.mark.usefixtures("_list_max_3")
async def test_projects_list_projects__C15(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Biên danh sách cũ: 0, 1, 4 dự án — trần `PROJECTS_LIST_MAX=3`, thứ tự `updated_at DESC, id DESC`."""
    owner = await make_user(db_session)

    empty = await api_client.get(PROJECTS_PATH, headers=headers_of(owner))
    assert empty.json() == []

    solo = await seed_project(db_session, owner=owner, name="Một mình")
    one = await api_client.get(PROJECTS_PATH, headers=headers_of(owner))
    assert [item["id"] for item in one.json()] == [solo.id]

    projects = [solo, *[await seed_project(db_session, owner=owner, name=f"Dự án {n}") for n in range(3)]]
    for offset, project in enumerate(projects):
        await _touch(db_session, project, fake_clock.now() + timedelta(minutes=offset))

    over = await api_client.get(PROJECTS_PATH, headers=headers_of(owner))
    ids = [item["id"] for item in over.json()]
    assert ids == [projects[3].id, projects[2].id, projects[1].id]
    assert len(ids) == get_projects_settings().projects_list_max


async def test_projects_list_projects__C17(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """`code`, `address` không đặt → vắng khoá, không `null` (W2, K02)."""
    owner = await make_user(db_session)
    project = await seed_project(db_session, owner=owner)
    response = await api_client.get(PROJECTS_PATH, headers=headers_of(owner))
    item = next(item for item in response.json() if item["id"] == project.id)
    assert "code" not in item
    assert "address" not in item
    assert None not in item.values()


# ---------------------------------------------------------------------------
# #24 GET /api/projects/{project_id} — Đ: C01 C06 C08 C17
# ---------------------------------------------------------------------------


async def test_projects_read_project__C01(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Đúng: thành viên đọc được dự án của mình."""
    owner = await make_user(db_session)
    project = await seed_project(db_session, owner=owner, name="Nhà chính")
    response = await api_client.get(project_path(project.id), headers=headers_of(owner))
    assert response.status_code == 200
    assert response.json()["id"] == project.id


async def test_projects_read_project__C06(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Admin hệ thống không phải thành viên → 404 `resource:"project"` (404 trước 403, K08)."""
    owner = await make_user(db_session)
    project = await seed_project(db_session, owner=owner)
    outsider = await make_user(db_session, role="admin")
    response = await api_client.get(project_path(project.id), headers=headers_of(outsider))
    assert response.status_code == 404
    assert response.json()["resource"] == "project"


async def test_projects_read_project__C08(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Dự án đã xoá mềm → 404, kể cả cho chính thành viên cũ."""
    owner = await make_user(db_session)
    project = await seed_project(db_session, owner=owner)
    await db_session.execute(update(Project).where(Project.id == project.id).values(deleted_at=fake_clock.now()))
    await db_session.commit()
    response = await api_client.get(project_path(project.id), headers=headers_of(owner))
    assert response.status_code == 404


async def test_projects_read_project__C17(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """`code` vắng khi không đặt."""
    owner = await make_user(db_session)
    project = await seed_project(db_session, owner=owner)
    response = await api_client.get(project_path(project.id), headers=headers_of(owner))
    assert "code" not in response.json()


# ---------------------------------------------------------------------------
# N1 GET /api/project-summaries — Đ*: C01 C15 C17; extra C02
# ---------------------------------------------------------------------------


async def test_projects_list_summaries__C01_processing(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """`processing`: tầng chưa có lượt tải nào → dù có tầng vẫn `processing`."""
    owner = await make_user(db_session)
    project = await seed_project(db_session, owner=owner, name="Đang xử lý")
    await seed_floor(db_session, project, walls_total=0, walls_reviewed=0, has_upload=False)
    await db_session.commit()
    response = await api_client.get(SUMMARIES_PATH, headers=headers_of(owner))
    assert response.status_code == 200
    item = next(row for row in response.json()["items"] if row["id"] == project.id)
    assert item["status"] == "processing"
    assert item["floorCount"] == 1


async def test_projects_list_summaries__C01_qc(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """`qc`: đã tải, pipeline xong, còn tường chưa duyệt."""
    owner = await make_user(db_session)
    project = await seed_project(db_session, owner=owner, name="Đang QC")
    await seed_floor(db_session, project, walls_total=5, walls_reviewed=3, has_upload=True, pipeline_state="completed")
    await db_session.commit()
    response = await api_client.get(SUMMARIES_PATH, headers=headers_of(owner))
    item = next(row for row in response.json()["items"] if row["id"] == project.id)
    assert item["status"] == "qc"
    assert item["defaultFloorId"] is not None


async def test_projects_list_summaries__C01_done(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """`done`: mọi tường của mọi tầng đã duyệt, `walls_total > 0`."""
    owner = await make_user(db_session)
    project = await seed_project(db_session, owner=owner, name="Xong rồi")
    await seed_floor(db_session, project, walls_total=5, walls_reviewed=5, has_upload=True, pipeline_state="completed")
    await db_session.commit()
    response = await api_client.get(SUMMARIES_PATH, headers=headers_of(owner))
    item = next(row for row in response.json()["items"] if row["id"] == project.id)
    assert item["status"] == "done"
    assert (item["wallsTotalCount"], item["wallsReviewedCount"]) == (5, 5)


async def test_projects_list_summaries__C01_no_floors(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """0 tầng: `floorCount == 0`, `defaultFloorId` vắng, `areaM2` số 0 (không phải `null`)."""
    owner = await make_user(db_session)
    project = await seed_project(db_session, owner=owner, name="Chưa có tầng")
    await db_session.commit()
    response = await api_client.get(SUMMARIES_PATH, headers=headers_of(owner))
    item = next(row for row in response.json()["items"] if row["id"] == project.id)
    assert item["floorCount"] == 0
    assert "defaultFloorId" not in item
    assert item["areaM2"] == 0
    assert isinstance(item["areaM2"], int | float)


async def test_projects_list_summaries__C01_null_area(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Hai tầng `area_m2` đều `NULL` → `COALESCE(SUM(...), 0)` = số JSON `0`, không chuỗi."""
    owner = await make_user(db_session)
    project = await seed_project(db_session, owner=owner, name="Diện tích trống")
    await seed_floor(db_session, project, area_m2=None, has_upload=True, pipeline_state="completed")
    await seed_floor(db_session, project, area_m2=None, has_upload=True, pipeline_state="completed")
    await db_session.commit()
    response = await api_client.get(SUMMARIES_PATH, headers=headers_of(owner))
    item = next(row for row in response.json()["items"] if row["id"] == project.id)
    assert item["areaM2"] == 0
    assert isinstance(item["areaM2"], int | float)


async def test_projects_list_summaries__C15(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Biên danh sách mới: `limit=3` trên 0, 1, 4 dự án — `id ASC`, `nextCursor` khi còn trang."""
    owner = await make_user(db_session)

    empty = await api_client.get(SUMMARIES_PATH, params={"limit": 3}, headers=headers_of(owner))
    assert empty.json() == {"items": []}

    solo = await seed_project(db_session, owner=owner, name="Một trang")
    one = await api_client.get(SUMMARIES_PATH, params={"limit": 3}, headers=headers_of(owner))
    body_one = one.json()
    assert [item["id"] for item in body_one["items"]] == [solo.id]
    assert "nextCursor" not in body_one

    projects = sorted([solo, *[await seed_project(db_session, owner=owner) for _ in range(3)]], key=lambda p: p.id)
    over = await api_client.get(SUMMARIES_PATH, params={"limit": 3}, headers=headers_of(owner))
    body_over = over.json()
    assert [item["id"] for item in body_over["items"]] == [p.id for p in projects[:3]]
    assert body_over["nextCursor"]

    rest = await api_client.get(
        SUMMARIES_PATH, params={"limit": 3, "cursor": body_over["nextCursor"]}, headers=headers_of(owner)
    )
    assert [item["id"] for item in rest.json()["items"]] == [projects[3].id]


async def test_projects_list_summaries__C17(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """`defaultFloorId` vắng khi 0 tầng (đã phủ ở `C01_no_floors`); kiểm lại ở mức "toàn trường tuỳ chọn"."""
    owner = await make_user(db_session)
    project = await seed_project(db_session, owner=owner)
    await db_session.commit()
    response = await api_client.get(SUMMARIES_PATH, headers=headers_of(owner))
    item = next(row for row in response.json()["items"] if row["id"] == project.id)
    assert "defaultFloorId" not in item
    assert None not in item.values()


@pytest.mark.parametrize("limit", [0, 501])
async def test_projects_list_summaries__C02_limit_out_of_range(
    api_client: httpx.AsyncClient, db_session: AsyncSession, limit: int
) -> None:
    """`limit=0` và `limit=501` (> trần 500 của N1) → 422 `VALIDATION`."""
    owner = await make_user(db_session)
    response = await api_client.get(SUMMARIES_PATH, params={"limit": limit}, headers=headers_of(owner))
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"


async def test_projects_list_summaries__C02_garbage_cursor(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Cursor rác (không giải mã được) → 422 `CURSOR_INVALID`."""
    owner = await make_user(db_session)
    response = await api_client.get(SUMMARIES_PATH, params={"cursor": "khong-phai-cursor"}, headers=headers_of(owner))
    assert response.status_code == 422
    assert response.json()["code"] == "CURSOR_INVALID"


async def test_projects_list_summaries__C02_cursor_of_another_user(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Cursor ký hợp lệ nhưng dấu vết bộ lọc (`sub`) khác người gọi → 422 `CURSOR_INVALID`."""
    owner = await make_user(db_session)
    other = await make_user(db_session)
    foreign_cursor = encode_cursor(LIST_SUMMARIES_OP, {"user": other.id}, {"id": "prj_" + "0" * 26})
    response = await api_client.get(SUMMARIES_PATH, params={"cursor": foreign_cursor}, headers=headers_of(owner))
    assert response.status_code == 422
    assert response.json()["code"] == "CURSOR_INVALID"


async def test_projects_list_summaries_excludes_projects_where_caller_is_not_a_member(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """N1 chỉ liệt dự án mình là thành viên — dự án của người khác không lọt vào trang."""
    owner = await make_user(db_session)
    other_owner = await make_user(db_session)
    mine = await seed_project(db_session, owner=owner, name="Của tôi")
    await seed_project(db_session, owner=other_owner, name="Của người khác")
    response = await api_client.get(SUMMARIES_PATH, headers=headers_of(owner))
    ids = [item["id"] for item in response.json()["items"]]
    assert ids == [mine.id]
