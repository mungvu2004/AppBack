"""Đọc và ghi `project_memberships` (B2-01 [2], [6]).

Mọi hàm nhận `AsyncSession` của người gọi và **không** `commit`: người gọi (route, task
nền, CLI) quyết ranh giới giao dịch của mình. Module này không nhập `fastapi`, `starlette`,
`jwt`, `argon2` — worker B5-06a/b nhập nó (BE-00 §7 "Hàm worker nhập").

Hàm nhận **danh sách** id (`member_users`, `count_projects_of_users`) chạy đúng một truy
vấn và trả khoá cho **mọi** id vào, kể cả id không có dòng nào: người gọi dựng lô
(`ProjectOut`, N1) không phải kiểm `None` rồi lỡ tay thêm một truy vấn nữa (K, N+1).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from sqlalchemy import delete, exists, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.projects.summaries import touch_projects
from packages.core.clock import Clock
from packages.db.models.auth import User
from packages.db.models.projects import Project, ProjectMembership

EDITOR_ROLES: Final = ("admin", "engineer")
"""Vai được sửa dữ liệu dự án; `viewer` còn lại **không** cứu dự án khỏi mồ côi (B1-05)."""


@dataclass(frozen=True, slots=True)
class ProjectRef:
    """Dự án rút gọn cho B1-05 (màn "người này đang ở những dự án nào") — không phải dây."""

    id: str
    name: str


async def is_member(db: AsyncSession, project_id: str, user_id: str) -> bool:
    """Dự án **chưa xoá mềm** và người này là thành viên — một truy vấn, kể cả khi sai cả hai."""
    stmt = (
        select(ProjectMembership.user_id)
        .join(Project, Project.id == ProjectMembership.project_id)
        .where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.user_id == user_id,
            Project.deleted_at.is_(None),
        )
        .limit(1)
    )
    return (await db.execute(stmt)).first() is not None


async def add_member(db: AsyncSession, *, project_id: str, user_id: str, added_by: str, clock: Clock) -> bool:
    """Thêm thành viên (`ON CONFLICT DO NOTHING`); `True` khi dòng là **mới**, `False` khi đã có."""
    now = clock.now()
    stmt = (
        pg_insert(ProjectMembership)
        .values(project_id=project_id, user_id=user_id, added_by=added_by, created_at=now, updated_at=now)
        .on_conflict_do_nothing()
        .returning(ProjectMembership.user_id)
    )
    return (await db.execute(stmt)).first() is not None


async def remove_member(db: AsyncSession, *, project_id: str, user_id: str) -> bool:
    """Gỡ thành viên (xoá dòng, không xoá mềm); `True` khi có đúng một dòng bị xoá."""
    stmt = (
        delete(ProjectMembership)
        .where(ProjectMembership.project_id == project_id, ProjectMembership.user_id == user_id)
        .returning(ProjectMembership.user_id)
    )
    return (await db.execute(stmt)).first() is not None


async def lock_editor_ids(db: AsyncSession, project_id: str) -> list[str]:
    """Khoá (`FOR UPDATE OF project_memberships`) và trả id các thành viên sửa được, `user_id ASC`.

    Chỉ khoá dòng membership, không khoá `users`: người gọi đang sửa quyền của **một** dự
    án, khoá dòng người dùng sẽ chặn cả những lượt sửa hồ sơ chẳng liên quan.
    """
    stmt = (
        select(ProjectMembership.user_id)
        .join(User, User.id == ProjectMembership.user_id)
        .where(
            ProjectMembership.project_id == project_id,
            User.role.in_(EDITOR_ROLES),
            User.status == "active",
            User.deleted_at.is_(None),
        )
        .order_by(ProjectMembership.user_id)
        .with_for_update(of=ProjectMembership)
    )
    return list((await db.execute(stmt)).scalars().all())


async def member_users(db: AsyncSession, project_ids: Sequence[str]) -> dict[str, list[User]]:
    """Thành viên **chưa xoá mềm** của từng dự án, một truy vấn; dự án không có ai → `[]`.

    Lô rỗng trả `{}` **không** chạy câu nào: một trang danh sách rỗng không đáng một vòng DB
    cho `IN ()`.
    """
    if not project_ids:
        return {}
    stmt = (
        select(ProjectMembership.project_id, User)
        .join(User, User.id == ProjectMembership.user_id)
        .where(ProjectMembership.project_id.in_(project_ids), User.deleted_at.is_(None))
        .order_by(ProjectMembership.project_id, ProjectMembership.user_id)
    )
    by_project: dict[str, list[User]] = {project_id: [] for project_id in project_ids}
    for project_id, user in (await db.execute(stmt)).all():
        by_project[project_id].append(user)
    return by_project


async def count_projects_of_users(db: AsyncSession, user_ids: Sequence[str]) -> dict[str, int]:
    """Số dự án **chưa xoá mềm** của từng người, một truy vấn; id không có dòng nào → 0."""
    stmt = (
        select(ProjectMembership.user_id, func.count())
        .join(Project, Project.id == ProjectMembership.project_id)
        .where(ProjectMembership.user_id.in_(user_ids), Project.deleted_at.is_(None))
        .group_by(ProjectMembership.user_id)
    )
    counts: dict[str, int] = {user_id: 0 for user_id in user_ids}
    for user_id, total in (await db.execute(stmt)).all():
        counts[user_id] = total
    return counts


async def list_projects_of_user(db: AsyncSession, user_id: str, *, limit: int) -> list[ProjectRef]:
    """Tối đa `limit` dự án **chưa xoá mềm** của một người, `id ASC` (B1-05 xem trước khi xoá)."""
    stmt = (
        select(Project.id, Project.name)
        .join(ProjectMembership, ProjectMembership.project_id == Project.id)
        .where(ProjectMembership.user_id == user_id, Project.deleted_at.is_(None))
        .order_by(Project.id)
        .limit(limit)
    )
    return [ProjectRef(id=project_id, name=name) for project_id, name in (await db.execute(stmt)).all()]


async def remove_user_from_all_projects(db: AsyncSession, user_id: str, *, clock: Clock) -> list[str]:
    """Gỡ người này khỏi **mọi** dự án; trả id các dự án còn sống mà từ nay **không còn** người sửa.

    Khoá membership của người ấy `ORDER BY project_id FOR UPDATE` trước khi xoá (thứ tự
    khoá BE-00 §7: membership trước `projects`), rồi `touch_projects` **một câu** cho mọi dự
    án vừa chạm — lời khoá mới cuối cùng, và không phải N vòng DB cho N dự án. Dự án chỉ còn
    `viewer` vẫn là mồ côi: không ai sửa được nữa.
    """
    locked = (
        (
            await db.execute(
                select(ProjectMembership.project_id)
                .where(ProjectMembership.user_id == user_id)
                .order_by(ProjectMembership.project_id)
                .with_for_update()
            )
        )
        .scalars()
        .all()
    )
    await db.execute(delete(ProjectMembership).where(ProjectMembership.user_id == user_id))
    await touch_projects(db, project_ids=locked, clock=clock)
    editor_left = (
        select(ProjectMembership.project_id)
        .join(User, User.id == ProjectMembership.user_id)
        .where(
            ProjectMembership.project_id == Project.id,
            User.role.in_(EDITOR_ROLES),
            User.status == "active",
            User.deleted_at.is_(None),
        )
    )
    orphans = (
        select(Project.id)
        .where(Project.id.in_(locked), Project.deleted_at.is_(None), ~exists(editor_left))
        .order_by(Project.id)
    )
    return list((await db.execute(orphans)).scalars().all())
