"""`require_project` — cổng quyền theo dự án (B2-01 [2], [6] "`require_project`").

Khác các khoá cấp hệ thống của `apps/api/access` (B1-02), khoá dự án
(`project.settings.edit`, …) chỉ kiểm được ở đây vì cần biết người gọi có phải thành
viên của **đúng** dự án trên đường hay không (K08: 404 luôn thắng 403, kể cả với admin
hệ thống không phải thành viên).
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from apps.api.core.auth import Principal
from apps.api.core.deps import CurrentPrincipal, DbSession
from apps.api.core.permissions import ANY_MEMBER, permission_dependency
from packages.core.error_codes import FORBIDDEN, NOT_FOUND
from packages.core.ids import is_id
from packages.db.models.projects import Project, ProjectMembership
from packages.domain.permissions import PERMISSION_KEYS, SYSTEM_SCOPED_KEYS, PermissionKey, can

ProjectResolver = Callable[[Request, Principal, AsyncSession], Awaitable[str]]
"""Hàm suy ra `project_id` từ request; lỗi của nó thắng — chạy trước kiểm thành viên."""


async def project_from_path(request: Request, principal: Principal, db: AsyncSession) -> str:
    """`project_id` từ tham số đường; sai mẫu `prj_<ULID>` → 404 **không** truy vấn DB."""
    project_id = request.path_params["project_id"]
    if not isinstance(project_id, str) or not is_id("prj", project_id):
        raise NOT_FOUND.error(resource="project")
    return project_id


@dataclass(frozen=True, slots=True)
class ProjectAccess:
    """Kết quả của `require_project`: dự án đã xác nhận cùng người gọi đã kiểm quyền."""

    project_id: str
    project_name: str
    principal: Principal


def require_project(
    permission: PermissionKey | None = None, *, resolver: ProjectResolver = project_from_path
) -> Callable[[Request, Principal, AsyncSession], Awaitable[ProjectAccess]]:
    """Cổng dependency: dự án chưa xoá **và** người gọi là thành viên, rồi kiểm `permission`.

    `permission` thuộc `SYSTEM_SCOPED_KEYS` (chỉ kiểm cấp hệ thống, K08) hay không phải
    khoá quyền hợp lệ → `ValueError` ngay lúc gọi (khai route), không đợi tới request.
    Một truy vấn duy nhất kiểm cả "dự án tồn tại, chưa xoá" lẫn "là thành viên": tách hai
    câu sẽ vừa N+1 vừa hé cho người ngoài biết dự án có tồn tại hay không (K08).
    """
    if permission is not None and (permission in SYSTEM_SCOPED_KEYS or permission not in PERMISSION_KEYS):
        raise ValueError(f"không phải khoá quyền theo dự án: {permission!r}")

    @permission_dependency(permission if permission is not None else ANY_MEMBER)
    async def dependency(request: Request, principal: CurrentPrincipal, db: DbSession) -> ProjectAccess:
        """Chạy resolver rồi kiểm thành viên + quyền; trả `ProjectAccess` hoặc ném 404/403."""
        project_id = await resolver(request, principal, db)
        name = (
            await db.execute(
                select(Project.name)
                .join(ProjectMembership, ProjectMembership.project_id == Project.id)
                .where(
                    Project.id == project_id,
                    Project.deleted_at.is_(None),
                    ProjectMembership.user_id == principal.user_id,
                )
            )
        ).scalar_one_or_none()
        return _checked_access(project_id, name, permission, principal)

    return dependency


def _checked_access(
    project_id: str, name: str | None, permission: PermissionKey | None, principal: Principal
) -> ProjectAccess:
    """404 nếu không có dòng (không phải thành viên hoặc dự án đã xoá), rồi 403 nếu thiếu `permission`."""
    if name is None:
        raise NOT_FOUND.error(resource="project")
    if permission is not None and not can(principal.role, permission):
        raise FORBIDDEN.error()
    return ProjectAccess(project_id=project_id, project_name=name, principal=principal)
