"""Test ba bảng của B2-01 trên Postgres thật (K23): FK, CHECK, CASCADE."""

from decimal import Decimal
from typing import Final

import pytest
from sqlalchemy import ForeignKeyConstraint, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.base import Base
from packages.db.models import load_all_models
from packages.db.models.projects import PROJECTS, Project, ProjectFloorSummary, ProjectMembership
from packages.testing.factories.auth import make_user
from packages.testing.factories.projects import make_project

FLOOR_ID: Final = "L-0000000001"


def test_every_fk_to_projects_cascades() -> None:
    """Mọi FK tới `projects.id`, của bất kỳ module nào, phải `ON DELETE CASCADE`.

    Lịch dọn xoá cứng dự án bằng một `DELETE FROM projects`; một FK thiếu CASCADE làm lượt
    dọn ném `ForeignKeyViolation` và dòng nằm lại mãi (B2-01 [8] "FK").
    """
    load_all_models()
    offenders = [
        f"{table.name}.{fk.name}"
        for table in Base.metadata.tables.values()
        for fk in table.constraints
        if isinstance(fk, ForeignKeyConstraint)
        and any(element.column.table.name == PROJECTS for element in fk.elements)
        and fk.ondelete != "CASCADE"
    ]
    assert offenders == []


async def _summary(
    db: AsyncSession,
    project: Project,
    *,
    walls_total: int = 2,
    walls_reviewed: int = 1,
    pipeline_state: str = "none",
    area_m2: Decimal | None = None,
) -> None:
    """Chèn một dòng đếm; mỗi test ghi đè đúng cột nó thử CHECK."""
    db.add(
        ProjectFloorSummary(
            project_id=project.id,
            floor_level_id=FLOOR_ID,
            floor_order=0,
            walls_total=walls_total,
            walls_reviewed=walls_reviewed,
            pipeline_state=pipeline_state,
            area_m2=area_m2,
        )
    )
    await db.flush()


@pytest.mark.parametrize(
    ("walls_total", "walls_reviewed", "pipeline_state", "constraint"),
    [
        (2, 3, "none", "walls_reviewed_range"),
        (0, -1, "none", "walls_reviewed_range"),
        (-1, 0, "none", "walls_reviewed_range"),
        (2, 1, "queued", "pipeline_state"),
    ],
)
async def test_floor_summary_checks_reject_bad_rows(
    db_session: AsyncSession, walls_total: int, walls_reviewed: int, pipeline_state: str, constraint: str
) -> None:
    """DB từ chối "đã duyệt > tổng", số âm và `pipeline_state` lạ — tầng phòng thủ cuối."""
    user = await make_user(db_session)
    project = await make_project(db_session, owner=user)
    with pytest.raises(IntegrityError, match=constraint):
        await _summary(
            db_session,
            project,
            walls_total=walls_total,
            walls_reviewed=walls_reviewed,
            pipeline_state=pipeline_state,
        )


async def test_floor_summary_defaults(db_session: AsyncSession) -> None:
    """Chỉ `floor_order` là bắt buộc: đếm về 0, `area_m2` NULL, chưa tải, `none`, không ẩn."""
    user = await make_user(db_session)
    project = await make_project(db_session, owner=user)
    row = ProjectFloorSummary(project_id=project.id, floor_level_id=FLOOR_ID, floor_order=3)
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    assert (row.walls_total, row.walls_reviewed, row.area_m2) == (0, 0, None)
    assert (row.has_upload, row.pipeline_state, row.hidden) == (False, "none", False)


async def test_hard_delete_project_cascades(db_session: AsyncSession) -> None:
    """Xoá cứng dự án → membership và dòng đếm biến mất cùng lượt (không cần xoá tay)."""
    owner = await make_user(db_session)
    member = await make_user(db_session)
    project = await make_project(db_session, owner=owner, members=[member])
    await _summary(db_session, project, area_m2=Decimal("12.34"))
    await db_session.commit()

    await db_session.delete(await db_session.get_one(Project, project.id))
    await db_session.commit()

    memberships = await db_session.execute(
        select(func.count()).select_from(ProjectMembership).where(ProjectMembership.project_id == project.id)
    )
    summaries = await db_session.execute(
        select(func.count()).select_from(ProjectFloorSummary).where(ProjectFloorSummary.project_id == project.id)
    )
    assert (memberships.scalar_one(), summaries.scalar_one()) == (0, 0)


async def test_make_project_inserts_owner_and_members(db_session: AsyncSession) -> None:
    """Khói factory: owner và mỗi thành viên đúng một dòng, `added_by` luôn là owner.

    `owner` được truyền lại trong `members` để chắc id trùng bị bỏ chứ không hỏng PK.
    """
    owner = await make_user(db_session)
    member = await make_user(db_session)
    project = await make_project(db_session, owner=owner, members=[owner, member], name="Nhà B", code="NB")
    await db_session.commit()

    rows = (
        (
            await db_session.execute(
                select(ProjectMembership)
                .where(ProjectMembership.project_id == project.id)
                .order_by(ProjectMembership.user_id)
            )
        )
        .scalars()
        .all()
    )
    assert sorted(row.user_id for row in rows) == sorted([owner.id, member.id])
    assert {row.added_by for row in rows} == {owner.id}
    stored = await db_session.get_one(Project, project.id)
    assert (stored.name, stored.code, stored.created_by, stored.deleted_at) == ("Nhà B", "NB", owner.id, None)
