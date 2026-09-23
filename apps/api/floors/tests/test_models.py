"""Test bảng `floors` trên Postgres thật (K23): CHECK từng biên, `uq_floors_level`, cascade."""

from datetime import UTC, datetime
from typing import Final

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.floors import FloorRow
from packages.db.models.projects import Project
from packages.testing.factories.auth import make_user
from packages.testing.factories.projects import make_project

VALID_LEVEL: Final = "L-0000000001"
OTHER_LEVEL: Final = "L-0000000002"


def _floor(project: Project, **overrides: object) -> FloorRow:
    """Một `FloorRow` hợp lệ, ghi đè đúng cột đang thử CHECK."""
    values: dict[str, object] = {
        "project_id": project.id,
        "level_id": VALID_LEVEL,
        "name": "Tầng trệt",
        "floor_order": 0,
        "elevation_mm": 0,
        "height_mm": 3000,
        "created_by": project.created_by,
    }
    values.update(overrides)
    return FloorRow(**values)


@pytest.mark.parametrize(
    ("field", "value", "constraint"),
    [
        ("floor_order", -1, "floor_order_range"),
        ("floor_order", 1000, "floor_order_range"),
        ("elevation_mm", -30001, "elevation_mm_range"),
        ("elevation_mm", 300001, "elevation_mm_range"),
        ("height_mm", 1999, "height_mm_range"),
        ("height_mm", 10001, "height_mm_range"),
        ("name", "", "name_length"),
        ("name", "x" * 121, "name_length"),
        ("level_id", "L-abc", "level_id_format"),
    ],
)
async def test_floor_checks_reject_out_of_range_values(
    db_session: AsyncSession, field: str, value: object, constraint: str
) -> None:
    """Mỗi CHECK từ chối phía ngoài biên (B2-03 [5])."""
    user = await make_user(db_session)
    project = await make_project(db_session, owner=user)
    db_session.add(_floor(project, **{field: value}))
    with pytest.raises(IntegrityError, match=constraint):
        await db_session.flush()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("floor_order", 0),
        ("floor_order", 999),
        ("elevation_mm", -30000),
        ("elevation_mm", 300000),
        ("height_mm", 2000),
        ("height_mm", 10000),
        ("name", "x"),
        ("name", "x" * 120),
        ("level_id", "L-0123456789"),
    ],
)
async def test_floor_checks_accept_boundary_values(db_session: AsyncSession, field: str, value: object) -> None:
    """Đúng giá trị biên (0/999, ±trần, 1/120 ký tự, id 10 ký tự) đều được chấp nhận."""
    user = await make_user(db_session)
    project = await make_project(db_session, owner=user)
    db_session.add(_floor(project, **{field: value}))
    await db_session.flush()


async def test_uq_floors_level_blocks_live_duplicate_but_allows_after_soft_delete(db_session: AsyncSession) -> None:
    """Trùng `(project_id, level_id)` khi cả hai còn sống → 409 (DB); tầng cũ xoá mềm thì cho trùng."""
    user = await make_user(db_session)
    project = await make_project(db_session, owner=user)
    project_id, created_by = project.id, project.created_by  # đọc trước rollback (nó hết hạn object)
    first = _floor(project)
    db_session.add(first)
    await db_session.flush()
    first_pk = first.pk  # đọc trước `commit` — sau đó `pk` hết hạn, đọc lại cần một truy vấn
    await db_session.commit()

    def _own_floor(name: str) -> FloorRow:
        """Tầng mới không phụ thuộc `project` (có thể đã hết hạn sau `rollback`)."""
        return FloorRow(
            project_id=project_id,
            level_id=VALID_LEVEL,
            name=name,
            floor_order=0,
            elevation_mm=0,
            height_mm=3000,
            created_by=created_by,
        )

    db_session.add(_own_floor("Tầng trùng"))
    with pytest.raises(IntegrityError, match="uq_floors_level"):
        await db_session.flush()
    await db_session.rollback()

    stored_first = await db_session.get_one(FloorRow, first_pk)
    stored_first.deleted_at = datetime.now(UTC)
    await db_session.commit()

    db_session.add(_own_floor("Tầng mới"))
    await db_session.commit()  # không còn dòng sống trùng level_id → không lỗi


async def test_hard_delete_project_cascades_floors(db_session: AsyncSession) -> None:
    """Xoá cứng dự án → mọi dòng `floors` của nó biến mất cùng lượt."""
    user = await make_user(db_session)
    project = await make_project(db_session, owner=user)
    db_session.add(_floor(project, level_id=VALID_LEVEL))
    db_session.add(_floor(project, level_id=OTHER_LEVEL))
    await db_session.commit()

    await db_session.delete(await db_session.get_one(Project, project.id))
    await db_session.commit()

    remaining = await db_session.execute(
        select(func.count()).select_from(FloorRow).where(FloorRow.project_id == project.id)
    )
    assert remaining.scalar_one() == 0
