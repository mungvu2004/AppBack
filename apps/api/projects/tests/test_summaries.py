"""Bảng đếm theo tầng trên Postgres thật (K23): rollup, dòng ẩn, `ValueError`, số truy vấn."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Final

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.projects.summaries import (
    project_rollups,
    purge_floor,
    register_floor,
    set_floor_orders,
    set_layer_counts,
    set_upload_state,
    touch_project,
    unregister_floor,
)
from apps.api.projects.tests.sql_count import count_sql
from apps.api.projects.wire import ProjectRollup
from packages.db.models.projects import Project
from packages.testing.factories.auth import make_user
from packages.testing.factories.projects import make_project
from packages.testing.fixtures.clock import FakeClock

FLOOR: Final = "L-0000000001"
OTHER: Final = "L-0000000002"


@dataclass(frozen=True, slots=True)
class Floor:
    """Một dòng đếm cần dựng trong test; mặc định là tầng đã upload, pipeline xong, chưa có tường."""

    floor_level_id: str = FLOOR
    order: int = 0
    total: int = 0
    reviewed: int = 0
    area: Decimal | None = None
    upload: bool = True
    state: str = "completed"


async def _project(db: AsyncSession, floors: list[Floor]) -> Project:
    """Một dự án có sẵn các dòng đếm, đã `commit` (test đọc lại bằng session mới)."""
    project = await make_project(db, owner=await make_user(db))
    for floor in floors:
        await register_floor(db, project_id=project.id, floor_level_id=floor.floor_level_id, floor_order=floor.order)
        await set_layer_counts(
            db,
            project_id=project.id,
            floor_level_id=floor.floor_level_id,
            walls_total=floor.total,
            walls_reviewed=floor.reviewed,
            area_m2=floor.area,
        )
        await set_upload_state(
            db,
            project_id=project.id,
            floor_level_id=floor.floor_level_id,
            has_upload=floor.upload,
            pipeline_state=floor.state,
        )
    await db.commit()
    return project


async def _rollup(sessionmaker: async_sessionmaker[AsyncSession], project_id: str) -> ProjectRollup:
    """Rollup của một dự án, đọc lại qua **session mới** (K22)."""
    async with sessionmaker() as fresh:
        return (await project_rollups(fresh, [project_id]))[project_id]


@pytest.mark.parametrize(
    ("floors", "status", "legacy", "default_floor_id"),
    [
        ([], "processing", "draft", None),
        ([Floor(upload=False, state="none")], "processing", "draft", FLOOR),
        ([Floor(total=2, reviewed=1, state="pending")], "processing", "processing", FLOOR),
        ([Floor(total=2, reviewed=1, state="running")], "processing", "processing", FLOOR),
        ([Floor(total=2, reviewed=1, state="failed")], "processing", "error", FLOOR),
        ([Floor(total=4, reviewed=4)], "done", "approved", FLOOR),
        ([Floor()], "qc", "draft", FLOOR),
        ([Floor(total=2, reviewed=1), Floor(OTHER, order=1, total=1, reviewed=0)], "qc", "draft", FLOOR),
        ([Floor(total=4, reviewed=4, state="failed")], "done", "error", FLOOR),
    ],
    ids=[
        "khong-tang",
        "chua-upload",
        "pending",
        "running",
        "failed",
        "moi-tuong-da-duyet",
        "khong-tuong-nao",
        "hai-tang-dang-duyet",
        "duyet-het-nhung-pipeline-hong",
    ],
)
async def test_rollup_status_covers_every_branch(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    floors: list[Floor],
    status: str,
    legacy: str,
    default_floor_id: str | None,
) -> None:
    """Mọi nhánh `status`/`legacy_status` của B2-01 [6], kể cả dự án chưa có tầng nào."""
    project = await _project(db_session, floors)
    rollup = await _rollup(db_sessionmaker, project.id)
    assert (rollup.status, rollup.legacy_status, rollup.default_floor_id) == (status, legacy, default_floor_id)
    assert rollup.floor_count == len(floors)


async def test_rollup_sums_null_areas_as_zero(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Hai tầng `area_m2` NULL → `areaM2` là 0, không phải `None` (N1 gửi số JSON)."""
    project = await _project(db_session, [Floor(), Floor(OTHER, order=1)])
    rollup = await _rollup(db_sessionmaker, project.id)
    assert (rollup.area_m2, rollup.walls_total, rollup.walls_reviewed) == (Decimal(0), 0, 0)


async def test_rollup_sums_areas_and_walls(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """`area_m2`, `walls_total`, `walls_reviewed` là tổng của các tầng chưa ẩn."""
    floors = [
        Floor(total=3, reviewed=1, area=Decimal("10.25")),
        Floor(OTHER, order=1, total=2, reviewed=2, area=Decimal("1.50")),
    ]
    rollup = await _rollup(db_sessionmaker, (await _project(db_session, floors)).id)
    assert (rollup.area_m2, rollup.walls_total, rollup.walls_reviewed) == (Decimal("11.75"), 5, 3)


async def test_default_floor_id_prefers_unreviewed_then_order_then_id(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Thứ tự `defaultFloorId`: tầng chưa duyệt xong trước, rồi `floor_order`, rồi `floor_level_id`."""
    floors = [
        Floor("L-b", order=5, total=2, reviewed=2),
        Floor("L-c", order=1, total=1, reviewed=0),
        Floor("L-a", order=1, total=3, reviewed=1),
    ]
    rollup = await _rollup(db_sessionmaker, (await _project(db_session, floors)).id)
    assert rollup.default_floor_id == "L-a"


async def test_rollups_of_thirty_projects_run_one_query(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """30 dự án → đúng **một** câu SQL (không N+1 ở #23, N1)."""
    owner = await make_user(db_session)
    projects = [await make_project(db_session, owner=owner) for _ in range(30)]
    await register_floor(db_session, project_id=projects[0].id, floor_level_id=FLOOR, floor_order=0)
    await db_session.commit()
    ids = [project.id for project in projects]
    with count_sql() as counter:
        async with db_sessionmaker() as fresh:
            rollups = await project_rollups(fresh, ids)
    assert counter.count == 1, counter.statements
    assert sorted(rollups) == sorted(ids)
    assert rollups[ids[1]].floor_count == 0


async def test_hidden_floor_keeps_counts_and_leaves_the_rollup(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Gỡ tầng: rollup bỏ tầng, số vẫn còn; ghi lên dòng ẩn không lỗi; khôi phục trả lại số."""
    project = await _project(db_session, [Floor(total=5, reviewed=5)])
    await unregister_floor(db_session, project_id=project.id, floor_level_id=FLOOR)
    await db_session.commit()
    hidden = await _rollup(db_sessionmaker, project.id)
    assert (hidden.floor_count, hidden.walls_total, hidden.status) == (0, 0, "processing")

    await set_upload_state(
        db_session, project_id=project.id, floor_level_id=FLOOR, has_upload=True, pipeline_state="completed"
    )
    await register_floor(db_session, project_id=project.id, floor_level_id=FLOOR, floor_order=0, restored=True)
    await db_session.commit()
    restored = await _rollup(db_sessionmaker, project.id)
    assert (restored.floor_count, restored.walls_total, restored.walls_reviewed) == (1, 5, 5)
    assert (restored.status, restored.legacy_status) == ("done", "approved")


async def test_register_floor_restored_inserts_a_default_row_when_missing(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """`restored=True` mà chưa có dòng nào → chèn dòng mặc định, không ném."""
    project = await _project(db_session, [])
    await register_floor(db_session, project_id=project.id, floor_level_id=FLOOR, floor_order=2, restored=True)
    await db_session.commit()
    rollup = await _rollup(db_sessionmaker, project.id)
    assert (rollup.floor_count, rollup.walls_total, rollup.status) == (1, 0, "processing")


async def test_register_floor_without_restored_resets_the_counts(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """`restored=False` ghi đè bằng mặc định: số về 0, chưa upload, `pipeline_state='none'`."""
    project = await _project(db_session, [Floor(total=7, reviewed=7)])
    await register_floor(db_session, project_id=project.id, floor_level_id=FLOOR, floor_order=0)
    await db_session.commit()
    rollup = await _rollup(db_sessionmaker, project.id)
    assert (rollup.walls_total, rollup.walls_reviewed, rollup.status) == (0, 0, "processing")


async def test_purge_floor_is_idempotent(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """`purge_floor` xoá dòng; gọi lần hai trên dòng đã mất **không** lỗi."""
    project = await _project(db_session, [Floor(total=2, reviewed=1)])
    await purge_floor(db_session, project_id=project.id, floor_level_id=FLOOR)
    await purge_floor(db_session, project_id=project.id, floor_level_id=FLOOR)
    await db_session.commit()
    assert (await _rollup(db_sessionmaker, project.id)).floor_count == 0


async def test_set_floor_orders_rewrites_every_order(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Đổi thứ tự nhiều tầng bằng một lệnh; `defaultFloorId` đổi theo thứ tự mới."""
    project = await _project(db_session, [Floor("L-a", order=0), Floor("L-b", order=1)])
    await set_floor_orders(db_session, project_id=project.id, orders={"L-a": 9, "L-b": 0})
    await set_floor_orders(db_session, project_id=project.id, orders={})
    await db_session.commit()
    assert (await _rollup(db_sessionmaker, project.id)).default_floor_id == "L-b"


async def test_touch_project_moves_updated_at(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """`touch_project` đặt `projects.updated_at` theo đồng hồ của người gọi."""
    project = await _project(db_session, [])
    await touch_project(db_session, project_id=project.id, clock=fake_clock)
    await db_session.commit()
    await db_session.refresh(project)
    assert project.updated_at == fake_clock.now()


@pytest.mark.parametrize(
    ("total", "reviewed", "area"),
    [(2, 3, None), (-1, 0, None), (2, -1, None), (2, 1, Decimal("-0.01"))],
    ids=["duyet-hon-tong", "tong-am", "duyet-am", "dien-tich-am"],
)
async def test_set_layer_counts_rejects_impossible_numbers(
    db_session: AsyncSession, total: int, reviewed: int, area: Decimal | None
) -> None:
    """Số âm hay `walls_reviewed > walls_total` → `ValueError` **trước** khi chạm DB."""
    project = await _project(db_session, [Floor()])
    with pytest.raises(ValueError, match=r"âm|lớn hơn"):
        await set_layer_counts(
            db_session,
            project_id=project.id,
            floor_level_id=FLOOR,
            walls_total=total,
            walls_reviewed=reviewed,
            area_m2=area,
        )


async def test_set_upload_state_rejects_unknown_pipeline_state(db_session: AsyncSession) -> None:
    """`pipeline_state` ngoài `PIPELINE_STATES` → `ValueError`, không để `CHECK` của DB ném."""
    project = await _project(db_session, [Floor()])
    with pytest.raises(ValueError, match="pipeline_state"):
        await set_upload_state(
            db_session, project_id=project.id, floor_level_id=FLOOR, has_upload=True, pipeline_state="cooking"
        )


async def test_writes_to_a_missing_row_raise_value_error(db_session: AsyncSession) -> None:
    """Mọi hàm ghi (trừ `register_floor`, `purge_floor`) gặp dòng không tồn tại → `ValueError`."""
    project = await _project(db_session, [])
    with pytest.raises(ValueError, match="không có dòng đếm"):
        await unregister_floor(db_session, project_id=project.id, floor_level_id=FLOOR)
    with pytest.raises(ValueError, match="không có dòng đếm"):
        await set_upload_state(
            db_session, project_id=project.id, floor_level_id=FLOOR, has_upload=True, pipeline_state="none"
        )
    with pytest.raises(ValueError, match="không có dòng đếm"):
        await set_layer_counts(
            db_session, project_id=project.id, floor_level_id=FLOOR, walls_total=0, walls_reviewed=0, area_m2=None
        )
    with pytest.raises(ValueError, match="thiếu dòng đếm"):
        await set_floor_orders(db_session, project_id=project.id, orders={FLOOR: 1})
