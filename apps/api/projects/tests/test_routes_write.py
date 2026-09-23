"""Test hợp đồng của #25 `projects_create_project`, #26 `projects_update_project`,
#27 `projects_delete_project` (B2-01 [2], [6], [8]).

Route chưa hợp nhất trên nhánh này (việc M) — mỗi hàm chỉ mồi qua factory/model của N,
gọi HTTP theo hợp đồng, và với #25 cắm cổng mở rộng giả bằng `extensions.override` trên
chính `api_app` (khớp cách `request.app` của route thật sẽ resolve). Không nhập `router`,
`service`, `memberships`, `summaries`, `access`, `jobs`.
"""

import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.access.kinds import ActivityKind
from apps.api.core import extensions
from apps.api.core.auth import Principal
from apps.api.core.wire import WireModel
from apps.api.projects.parts import PROJECT_CREATE_FLOORS, PROJECT_FLOORS, SUBMODULE, CreateHook, FloorDraft, ViewPart
from apps.api.projects.tests.test_routes_common import (
    FORBIDDEN_ROLE,
    PROJECTS_PATH,
    headers_of,
    project_path,
    seed_project,
)
from apps.api.projects.wire import FloorOut
from packages.core.clock import Clock
from packages.core.error_codes import VALIDATION
from packages.db.models.projects import Project, ProjectMembership
from packages.testing.factories.auth import make_user
from packages.testing.fixtures.access import activity_rows, assert_one_activity
from packages.testing.fixtures.clock import FakeClock

# ---------------------------------------------------------------------------
# #25 POST /api/projects — G*: C01 C02 C03 C17; extra C07 C16 C18
# ---------------------------------------------------------------------------


async def test_projects_create_project__C01(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Đúng: 201, người tạo (`sub`) là `created_by` và là thành viên (K05)."""
    creator = await make_user(db_session, role="engineer")
    response = await api_client.post(PROJECTS_PATH, json={"name": "Nhà mới"}, headers=headers_of(creator))
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Nhà mới"

    stored = await db_session.get_one(Project, body["id"])
    assert stored.created_by == creator.id
    membership = await db_session.execute(
        select(ProjectMembership).where(
            ProjectMembership.project_id == body["id"], ProjectMembership.user_id == creator.id
        )
    )
    assert membership.scalar_one_or_none() is not None
    await assert_one_activity(
        db_sessionmaker, actor_id=creator.id, kind=ActivityKind.PROJECT_CREATE, object_code=body["id"]
    )


@pytest.mark.parametrize("bad_body", [{"elevation": True}, {"name": 7}])
async def test_projects_create_project__C02(
    api_client: httpx.AsyncClient, db_session: AsyncSession, bad_body: dict[str, Any]
) -> None:
    """Thân sai kiểu/thiếu trường bắt buộc → 422 `VALIDATION` có `field`."""
    creator = await make_user(db_session, role="engineer")
    response = await api_client.post(PROJECTS_PATH, json=bad_body, headers=headers_of(creator))
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION"
    assert "field" in body or "count" in body


async def test_projects_create_project__C03(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Thân có khoá lạ → 422 `VALIDATION` (`extra="forbid"`)."""
    creator = await make_user(db_session, role="engineer")
    response = await api_client.post(PROJECTS_PATH, json={"name": "Nhà mới", "lạ": 1}, headers=headers_of(creator))
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"


async def test_projects_create_project__C07(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Vai mạnh nhất thiếu `project.create` (`viewer`) → 403 `FORBIDDEN`."""
    viewer = await make_user(db_session, role=FORBIDDEN_ROLE)
    response = await api_client.post(PROJECTS_PATH, json={"name": "Nhà mới"}, headers=headers_of(viewer))
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


async def test_projects_create_project__C16(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Tên NFD người dùng gõ → lưu và trả NFC (K20)."""
    creator = await make_user(db_session, role="engineer")
    nfd_name = unicodedata.normalize("NFD", "Nhà Ở Xã Hội")
    response = await api_client.post(PROJECTS_PATH, json={"name": nfd_name}, headers=headers_of(creator))
    assert response.status_code == 201
    assert response.json()["name"] == unicodedata.normalize("NFC", nfd_name)


async def test_projects_create_project__C17(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Trường tuỳ chọn không gửi → vắng khoá trong 201, không `null` (W2, K02)."""
    creator = await make_user(db_session, role="engineer")
    response = await api_client.post(PROJECTS_PATH, json={"name": "Không mã"}, headers=headers_of(creator))
    assert response.status_code == 201
    body = response.json()
    assert "code" not in body
    assert "address" not in body
    assert None not in body.values()


async def test_projects_create_project__C18(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Đúng một dòng `activity_log`, `kind=PROJECT_CREATE`, `object_code` = id dự án mới."""
    creator = await make_user(db_session, role="engineer")
    response = await api_client.post(PROJECTS_PATH, json={"name": "Nhà ghi nhật ký"}, headers=headers_of(creator))
    row = await assert_one_activity(
        db_sessionmaker,
        actor_id=creator.id,
        kind=ActivityKind.PROJECT_CREATE,
        object_code=response.json()["id"],
    )
    assert row.object_label == "Nhà ghi nhật ký"


async def test_create_project_ignores_status_members_progress_current_version(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """W18: bốn khoá server sở hữu mà FE vẫn gửi bị nhận rồi bỏ, không 422, không đổi nghĩa."""
    creator = await make_user(db_session, role="engineer")
    body = {
        "name": "Nhà mặc kệ",
        "status": "approved",
        "members": [{"id": "usr_x", "name": "Ai đó"}],
        "progress": {"percent": 42},
        "currentVersion": 9,
    }
    response = await api_client.post(PROJECTS_PATH, json=body, headers=headers_of(creator))
    assert response.status_code == 201
    assert response.json()["status"] == "draft"


async def test_create_project_without_hook_ignores_floors(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Chưa module nào cắm `project.create_floors` → `floors` trong thân bị bỏ qua lặng lẽ."""
    creator = await make_user(db_session, role="engineer")
    body = {"name": "Không hook", "floors": [{"name": "Tầng 1", "order": 0, "elevationMm": 0, "heightMm": 3000}]}
    response = await api_client.post(PROJECTS_PATH, json=body, headers=headers_of(creator))
    assert response.status_code == 201
    assert response.json()["floors"] == []


async def test_create_project_hook_receives_drafts_and_sees_row_in_same_transaction(
    api_client: httpx.AsyncClient, api_app: FastAPI, db_session: AsyncSession
) -> None:
    """Hook giả nhận đúng `FloorDraft`, thấy dòng `projects` trong cùng giao dịch, và tầng nó
    tạo hiện diện trong response qua phần giả `project.floors` (cổng mở rộng khớp nhau)."""
    captured_drafts: list[FloorDraft] = []
    floor_ids_by_project: dict[str, list[str]] = {}

    async def _create_floors(
        db: AsyncSession, project_id: str, drafts: Sequence[FloorDraft], principal: Principal, clock: Clock
    ) -> None:
        """Vẫn trong giao dịch của #25: dòng `projects` phải đã tồn tại (`SELECT` thấy nó)."""
        row = await db.execute(select(Project.id).where(Project.id == project_id))
        assert row.scalar_one() == project_id
        captured_drafts.extend(drafts)
        floor_ids_by_project[project_id] = [f"L-{index}" for index in range(len(drafts))]

    async def _floors(db: AsyncSession, ids: Sequence[str]) -> Mapping[str, Sequence[WireModel]]:
        """Trả đúng những tầng hook vừa "tạo" cho mỗi dự án được hỏi."""
        return {
            project_id: [
                FloorOut(id=floor_id, name=f"Tầng {index}", order=index, elevation_mm=0, height_mm=3000, drawings=[])
                for index, floor_id in enumerate(floor_ids_by_project.get(project_id, []))
            ]
            for project_id in ids
        }

    extensions.override(
        api_app,
        SUBMODULE,
        [
            (
                "test_create_hook",
                [
                    CreateHook(kind=PROJECT_CREATE_FLOORS, run=_create_floors),
                    ViewPart(kind=PROJECT_FLOORS, load=_floors),
                ],
            )
        ],
    )
    creator = await make_user(db_session, role="engineer")
    body = {
        "name": "Có hook",
        "floors": [{"name": "Tầng trệt", "order": 0, "elevationMm": 0, "heightMm": 3000}],
    }
    response = await api_client.post(PROJECTS_PATH, json=body, headers=headers_of(creator))
    assert response.status_code == 201
    result = response.json()
    assert len(result["floors"]) == 1
    assert result["floors"][0]["name"] == "Tầng 0"
    assert captured_drafts == [FloorDraft(name="Tầng trệt", order=0, elevation_mm=0, height_mm=3000)]


async def test_create_project_hook_error_rolls_back_project_and_membership(
    api_client: httpx.AsyncClient,
    api_app: FastAPI,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """Hook ném → cả lượt rollback: không dự án, không membership, không nhật ký (BE-00 §7)."""

    async def _failing_hook(
        db: AsyncSession, project_id: str, drafts: Sequence[FloorDraft], principal: Principal, clock: Clock
    ) -> None:
        """Ném 422 giữa giao dịch — mô phỏng tầng nháp không hợp lệ theo luật của B2-03."""
        raise VALIDATION.error(field="floors")

    extensions.override(
        api_app, SUBMODULE, [("test_failing_hook", [CreateHook(kind=PROJECT_CREATE_FLOORS, run=_failing_hook)])]
    )
    creator = await make_user(db_session, role="engineer")
    body = {"name": "Sẽ rollback", "floors": [{"name": "Tầng 1", "order": 0, "elevationMm": 0, "heightMm": 3000}]}
    response = await api_client.post(PROJECTS_PATH, json=body, headers=headers_of(creator))
    assert response.status_code == 422

    remaining = await db_session.execute(select(Project).where(Project.name == "Sẽ rollback"))
    assert remaining.scalar_one_or_none() is None
    assert await activity_rows(db_sessionmaker, actor_id=creator.id, kind=ActivityKind.PROJECT_CREATE) == []


async def test_create_project_twice_with_same_name_both_return_201(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Không có luật tên duy nhất: hai lượt cùng tên đều 201, không route nào trả 409."""
    creator = await make_user(db_session, role="engineer")
    first = await api_client.post(PROJECTS_PATH, json={"name": "Trùng tên"}, headers=headers_of(creator))
    second = await api_client.post(PROJECTS_PATH, json={"name": "Trùng tên"}, headers=headers_of(creator))
    assert (first.status_code, second.status_code) == (201, 201)
    assert first.json()["id"] != second.json()["id"]


# ---------------------------------------------------------------------------
# #26 PATCH /api/projects/{project_id} — G: C01 C02 C03 C06 C07 C08 C16 C17 C18
# ---------------------------------------------------------------------------


async def test_projects_update_project__C01(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Đúng: đổi `name`, thấy ngay ở response 200."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner, name="Tên cũ")
    response = await api_client.patch(project_path(project.id), json={"name": "Tên mới"}, headers=headers_of(owner))
    assert response.status_code == 200
    assert response.json()["name"] == "Tên mới"


@pytest.mark.parametrize(
    "bad_body",
    [{"code": "x" * 33}, {"name": "Nhà‮Lật"}, {"address": None}],
)
async def test_projects_update_project__C02(
    api_client: httpx.AsyncClient, db_session: AsyncSession, bad_body: dict[str, Any]
) -> None:
    """`code` 33 ký tự, `name` có U+202E, `address: null` tường minh → 422 `VALIDATION` có `field`."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    response = await api_client.patch(project_path(project.id), json=bad_body, headers=headers_of(owner))
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"


async def test_projects_update_project__C03(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Khoá lạ → 422 `VALIDATION`."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    response = await api_client.patch(project_path(project.id), json={"lạ": 1}, headers=headers_of(owner))
    assert response.status_code == 422


async def test_projects_update_project__C06(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Admin hệ thống không phải thành viên → 404 `resource:"project"`, không phải 403."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    outsider = await make_user(db_session, role="admin")
    response = await api_client.patch(project_path(project.id), json={"name": "X"}, headers=headers_of(outsider))
    assert response.status_code == 404


async def test_projects_update_project__C07(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Thành viên `viewer` (vai mạnh nhất thiếu `project.settings.edit`) → 403."""
    owner = await make_user(db_session, role="engineer")
    viewer = await make_user(db_session, role=FORBIDDEN_ROLE)
    project = await seed_project(db_session, owner=owner, members=[viewer])
    response = await api_client.patch(project_path(project.id), json={"name": "X"}, headers=headers_of(viewer))
    assert response.status_code == 403


async def test_projects_update_project__C08(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Dự án đã xoá mềm → 404."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner, deleted_at=fake_clock.now())
    response = await api_client.patch(project_path(project.id), json={"name": "X"}, headers=headers_of(owner))
    assert response.status_code == 404


async def test_projects_update_project__C16(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Tên NFD → lưu và trả NFC."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    nfd_name = unicodedata.normalize("NFD", "Toà Nhà Xanh")
    response = await api_client.patch(project_path(project.id), json={"name": nfd_name}, headers=headers_of(owner))
    assert response.json()["name"] == unicodedata.normalize("NFC", nfd_name)


async def test_projects_update_project__C17(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """`code` không gửi và chưa từng đặt → vẫn vắng khoá sau khi sửa trường khác."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    response = await api_client.patch(project_path(project.id), json={"name": "Đổi tên"}, headers=headers_of(owner))
    assert "code" not in response.json()


async def test_projects_update_project__C18(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Đúng một dòng nhật ký `PROJECT_UPDATE`, nhãn = **tên mới**."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner, name="Trước")
    await api_client.patch(project_path(project.id), json={"name": "Sau"}, headers=headers_of(owner))
    row = await assert_one_activity(
        db_sessionmaker, actor_id=owner.id, kind=ActivityKind.PROJECT_UPDATE, object_code=project.id
    )
    assert row.object_label == "Sau"


async def test_update_project_empty_body_is_a_noop(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """`{}` → 200 dự án hiện tại, `updatedAt` không đổi, không nhật ký."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner, name="Không đổi")
    before = await api_client.get(project_path(project.id), headers=headers_of(owner))
    response = await api_client.patch(project_path(project.id), json={}, headers=headers_of(owner))
    assert response.status_code == 200
    assert response.json()["updatedAt"] == before.json()["updatedAt"]
    assert await activity_rows(db_sessionmaker, actor_id=owner.id, kind=ActivityKind.PROJECT_UPDATE) == []


async def test_update_project_same_values_behaves_like_empty_body(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Gửi lại đúng giá trị hiện tại → như `{}`: không nhật ký, không đổi `updatedAt`."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner, name="Giữ nguyên", code="G1")
    before = await api_client.get(project_path(project.id), headers=headers_of(owner))
    response = await api_client.patch(
        project_path(project.id), json={"name": "Giữ nguyên", "code": "G1"}, headers=headers_of(owner)
    )
    assert response.json()["updatedAt"] == before.json()["updatedAt"]
    assert await activity_rows(db_sessionmaker, actor_id=owner.id, kind=ActivityKind.PROJECT_UPDATE) == []


# ---------------------------------------------------------------------------
# #27 DELETE /api/projects/{project_id} — G: C01 C06 C07 C08 C17 C18; waive C16
# ---------------------------------------------------------------------------


async def test_projects_delete_project__C01(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """200, thân là trạng thái **ngay trước khi xoá** (K01)."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner, name="Sắp xoá")
    response = await api_client.delete(project_path(project.id), headers=headers_of(owner))
    assert response.status_code == 200
    assert response.json()["name"] == "Sắp xoá"


async def test_projects_delete_project__C06(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Admin hệ thống không phải thành viên → 404."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    outsider = await make_user(db_session, role="admin")
    response = await api_client.delete(project_path(project.id), headers=headers_of(outsider))
    assert response.status_code == 404


async def test_projects_delete_project__C07(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Thành viên `viewer` thiếu `project.settings.edit` → 403."""
    owner = await make_user(db_session, role="engineer")
    viewer = await make_user(db_session, role=FORBIDDEN_ROLE)
    project = await seed_project(db_session, owner=owner, members=[viewer])
    response = await api_client.delete(project_path(project.id), headers=headers_of(viewer))
    assert response.status_code == 403


async def test_projects_delete_project__C08(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Đã xoá mềm từ trước → 404."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner, deleted_at=fake_clock.now())
    response = await api_client.delete(project_path(project.id), headers=headers_of(owner))
    assert response.status_code == 404


async def test_projects_delete_project__C17(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """`code` vắng khi chưa từng đặt."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    response = await api_client.delete(project_path(project.id), headers=headers_of(owner))
    assert "code" not in response.json()


async def test_projects_delete_project__C18(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Đúng một dòng nhật ký `PROJECT_DELETE`."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner, name="Ghi rồi xoá")
    await api_client.delete(project_path(project.id), headers=headers_of(owner))
    row = await assert_one_activity(
        db_sessionmaker, actor_id=owner.id, kind=ActivityKind.PROJECT_DELETE, object_code=project.id
    )
    assert row.object_label == "Ghi rồi xoá"


async def test_delete_project_second_delete_returns_404(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Xoá lần hai (dự án đã `deleted_at`) → 404, không nhật ký thêm."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    first = await api_client.delete(project_path(project.id), headers=headers_of(owner))
    second = await api_client.delete(project_path(project.id), headers=headers_of(owner))
    assert (first.status_code, second.status_code) == (200, 404)


async def test_delete_project_keeps_membership_row_but_revokes_access(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Xoá mềm giữ `project_memberships` (cho lịch dọn) nhưng mọi thành viên mất quyền ngay."""
    owner = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=owner)
    await api_client.delete(project_path(project.id), headers=headers_of(owner))

    membership = await db_session.execute(
        select(ProjectMembership).where(
            ProjectMembership.project_id == project.id, ProjectMembership.user_id == owner.id
        )
    )
    assert membership.scalar_one_or_none() is not None

    denied = await api_client.get(project_path(project.id), headers=headers_of(owner))
    assert denied.status_code == 404
