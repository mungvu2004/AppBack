"""Test `require_project` trên app thử (Postgres thật, verifier giả — B2-01 [8])."""

from collections.abc import AsyncIterator
from typing import Annotated, Final

import httpx
import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from apps.api.core.app import create_app, discover_routers
from apps.api.core.auth import FakeTokenVerifier, Principal
from apps.api.core.openapi import Operation, operations
from apps.api.core.permissions import ANY_MEMBER
from apps.api.core.routing import protected_router
from apps.api.core.wire import WireModel, WireRequest
from apps.api.projects.access import ProjectAccess, require_project
from apps.api.projects.tests.sql_count import count_sql
from packages.core.error_codes import VERSION_CONFLICT
from packages.core.settings import get_core_settings
from packages.testing.factories.auth import make_user
from packages.testing.factories.projects import make_project
from packages.testing.fixtures.api import auth_headers, make_api_client
from packages.testing.fixtures.clock import FakeClock

PREFIX: Final = "/api/project-access-probe"

router = protected_router(prefix="/project-access-probe", tags=["project-access-probe"])


class RoleBody(WireRequest):
    """Thân mang `role` — chứng minh `require_project` không đọc vai từ thân (K05)."""

    role: str


class AccessOut(WireModel):
    """Bằng chứng `ProjectAccess` mà `require_project` trả cho handler."""

    project_id: str
    project_name: str
    user_id: str


def _out(access: ProjectAccess) -> AccessOut:
    """`AccessOut` từ một `ProjectAccess` — dùng chung cho mọi route mẫu."""
    return AccessOut(project_id=access.project_id, project_name=access.project_name, user_id=access.principal.user_id)


async def _conflict_resolver(request: Request, principal: Principal, db: AsyncSession) -> str:
    """Resolver giả: luôn 409 trước khi `require_project` kịp kiểm thành viên."""
    raise VERSION_CONFLICT.error()


@router.get("/{project_id}/member", response_model=AccessOut)
async def project_access_probe_member(
    access: Annotated[ProjectAccess, Depends(require_project())],
) -> AccessOut:
    """`require_project()` không khoá quyền — chỉ đòi là thành viên."""
    return _out(access)


@router.post("/{project_id}/member", response_model=AccessOut)
async def project_access_probe_member_post(
    body: RoleBody, access: Annotated[ProjectAccess, Depends(require_project())]
) -> AccessOut:
    """Route nhận thân có `role` — vẫn phải qua đúng luật thành viên (K05)."""
    del body
    return _out(access)


@router.get("/{project_id}/settings", response_model=AccessOut)
async def project_access_probe_settings_edit(
    access: Annotated[ProjectAccess, Depends(require_project("project.settings.edit"))],
) -> AccessOut:
    """`require_project("project.settings.edit")` — viewer bị 403 sau khi qua 404."""
    return _out(access)


@router.get("/{project_id}/conflict-resolver", response_model=AccessOut)
async def project_access_probe_conflict_resolver(
    access: Annotated[ProjectAccess, Depends(require_project(resolver=_conflict_resolver))],
) -> AccessOut:
    """Route dùng resolver giả — chứng minh lỗi của resolver thắng trước kiểm thành viên."""
    return _out(access)


@pytest.fixture
def access_app(api_env: None, fake_clock: FakeClock) -> FastAPI:
    """App thật cộng router mẫu; verifier giả (không cần đăng nhập thật)."""
    return create_app(
        get_core_settings(),
        token_verifier=FakeTokenVerifier(),
        clock=fake_clock,
        routers=[*discover_routers(), ("project_access_probe", router)],
    )


@pytest_asyncio.fixture(loop_scope="function")
async def access_client(access_app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """Client của `access_app`, có chạy `lifespan`."""
    async with make_api_client(access_app) as client:
        yield client


def _principal(user_id: str, role: str) -> Principal:
    """`Principal` giả khớp `user_id` thật trong DB, vai `role`."""
    return Principal(user_id=user_id, session_id="sid-test", role=role)  # type: ignore[arg-type]  # vai là str để test dựng được vai tuỳ ý


async def _setup_member(
    db_session: AsyncSession, fake_clock: FakeClock, *, role: str = "engineer"
) -> tuple[str, dict[str, str]]:
    """Dự án có một thành viên vai `role`; trả `project_id` và header của người ấy."""
    owner = await make_user(db_session, role="admin")
    member = await make_user(db_session, role=role)
    project = await make_project(db_session, owner=owner, members=[member])
    await db_session.commit()
    return project.id, auth_headers(_principal(member.id, role))


async def test_member_reads_project(
    access_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Thành viên gọi được, `ProjectAccess` mang đúng id/tên dự án và người gọi."""
    project_id, headers = await _setup_member(db_session, fake_clock)
    response = await access_client.get(f"{PREFIX}/{project_id}/member", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["projectId"] == project_id


async def test_outsider_is_not_found(
    access_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Người không phải thành viên → 404 `resource:"project"`, không 403."""
    owner = await make_user(db_session, role="admin")
    outsider = await make_user(db_session, role="engineer")
    project = await make_project(db_session, owner=owner)
    await db_session.commit()
    headers = auth_headers(_principal(outsider.id, "engineer"))
    response = await access_client.get(f"{PREFIX}/{project.id}/member", headers=headers)
    assert response.status_code == 404
    assert response.json()["resource"] == "project"


async def test_system_admin_not_member_is_not_found(
    access_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Admin hệ thống không phải thành viên vẫn 404 (K08) — không có ngoại lệ cho vai."""
    owner = await make_user(db_session, role="admin")
    admin = await make_user(db_session, role="admin")
    project = await make_project(db_session, owner=owner)
    await db_session.commit()
    headers = auth_headers(_principal(admin.id, "admin"))
    response = await access_client.get(f"{PREFIX}/{project.id}/member", headers=headers)
    assert response.status_code == 404
    assert response.json()["resource"] == "project"


async def test_soft_deleted_project_is_not_found(
    access_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Dự án đã xoá mềm → 404 dù người gọi vẫn còn dòng membership."""
    owner = await make_user(db_session, role="admin")
    project = await make_project(db_session, owner=owner, deleted_at=fake_clock.now())
    await db_session.commit()
    headers = auth_headers(_principal(owner.id, "admin"))
    response = await access_client.get(f"{PREFIX}/{project.id}/member", headers=headers)
    assert response.status_code == 404
    assert response.json()["resource"] == "project"


async def test_viewer_member_lacks_permission_is_forbidden(
    access_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Thành viên viewer qua được 404 nhưng thiếu `project.settings.edit` → 403 (sau 404)."""
    project_id, headers = await _setup_member(db_session, fake_clock, role="viewer")
    response = await access_client.get(f"{PREFIX}/{project_id}/settings", headers=headers)
    assert response.status_code == 403


async def test_engineer_member_has_settings_edit(
    access_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Thành viên engineer có `project.settings.edit` → 200."""
    project_id, headers = await _setup_member(db_session, fake_clock, role="engineer")
    response = await access_client.get(f"{PREFIX}/{project_id}/settings", headers=headers)
    assert response.status_code == 200, response.text


async def test_bad_project_id_pattern_is_not_found_without_query(
    access_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """`project_id` sai mẫu `prj_<ULID>` → 404, **0** câu SQL (không đụng DB)."""
    user = await make_user(db_session, role="admin")
    headers = auth_headers(_principal(user.id, "admin"))
    with count_sql() as counter:
        response = await access_client.get(f"{PREFIX}/not-a-project-id/member", headers=headers)
    assert response.status_code == 404
    assert counter.count == 0, counter.statements


async def test_resolver_error_wins_before_membership_check(
    access_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Resolver giả ném 409: thắng trước khi `require_project` kịp kiểm thành viên."""
    owner = await make_user(db_session, role="admin")
    outsider = await make_user(db_session, role="engineer")
    project = await make_project(db_session, owner=owner)
    await db_session.commit()
    headers = auth_headers(_principal(outsider.id, "engineer"))
    response = await access_client.get(f"{PREFIX}/{project.id}/conflict-resolver", headers=headers)
    assert response.status_code == 409


@pytest.mark.parametrize("permission", ["project.create", "không.có"])
def test_require_project_rejects_non_project_keys(permission: str) -> None:
    """Khoá cấp hệ thống hay khoá lạ → `ValueError` **lúc khai**, không đợi request (K08)."""
    with pytest.raises(ValueError, match="dự án"):
        require_project(permission)  # type: ignore[arg-type]  # cố tình truyền khoá sai để kiểm ValueError


def test_operations_expose_permission_keys(access_app: FastAPI) -> None:
    """`permission_key` phơi ra đúng khoá, hoặc `"thành viên"` khi `permission=None`."""
    ops = {operation.op: operation for operation in operations(access_app)}
    settings_op: Operation = ops["project_access_probe_settings_edit"]
    member_op: Operation = ops["project_access_probe_member"]
    assert settings_op.permission_key == "project.settings.edit"
    assert member_op.permission_key == ANY_MEMBER


async def test_role_in_request_body_is_ignored(
    access_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """K05: thân `{"role": "admin"}` của người ngoài không đổi kết quả — vẫn 404."""
    owner = await make_user(db_session, role="admin")
    outsider = await make_user(db_session, role="viewer")
    project = await make_project(db_session, owner=owner)
    await db_session.commit()
    headers = auth_headers(_principal(outsider.id, "viewer"))
    response = await access_client.post(f"{PREFIX}/{project.id}/member", json={"role": "admin"}, headers=headers)
    assert response.status_code == 404


async def test_batch_of_projects_uses_one_query(
    access_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Một request thành viên chỉ đụng **một** câu SQL của `require_project` (không N+1)."""
    owner = await make_user(db_session, role="admin")
    member = await make_user(db_session, role="engineer")
    for _ in range(3):
        await make_project(db_session, owner=owner, members=[member])
    target = await make_project(db_session, owner=owner, members=[member])
    await db_session.commit()
    headers = auth_headers(_principal(member.id, "engineer"))
    with count_sql() as counter:
        response = await access_client.get(f"{PREFIX}/{target.id}/member", headers=headers)
    assert response.status_code == 200, response.text
    assert counter.count == 1, counter.statements
