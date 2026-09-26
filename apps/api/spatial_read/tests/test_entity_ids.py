"""`apps.api.spatial_read.entity_ids.claim_entity_ids` trên Postgres thật (B3-02 [8]).

Mọi case đồng thời chạy trên **hai session thật** (K23): luật ở đây là luật của
`ON CONFLICT` và của khoá dòng Postgres, mô phỏng bằng mock thì không kiểm được gì.
"""

from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.floors.settings import get_floors_settings
from apps.api.spatial_read.entity_ids import claim_entity_ids
from apps.api.spatial_read.tests._helpers import make_scene, other_session, race
from packages.db.models.floors import FloorRow
from packages.db.models.spatial import FloorEntityIdRow
from packages.testing.factories.auth import make_user
from packages.testing.factories.floors import make_floor
from packages.testing.factories.projects import make_project
from packages.testing.fixtures.clock import FakeClock


async def _owner_of(db: AsyncSession, project_id: str, entity_id: str) -> int | None:
    """Tầng đang giữ một id, `None` khi id chưa có chủ."""
    stmt = select(FloorEntityIdRow.floor_pk).where(
        FloorEntityIdRow.project_id == project_id, FloorEntityIdRow.entity_id == entity_id
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def _soft_delete(db: AsyncSession, floor_pk: int, *, at: datetime) -> None:
    """Xoá mềm một tầng ở đúng thời điểm `at` (mô phỏng #11)."""
    await db.execute(update(FloorRow).where(FloorRow.pk == floor_pk).values(deleted_at=at))


async def test_claim_adds_new_ids(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Id chưa ai giữ → nhận hết, không xung đột."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]

    conflicts = await claim_entity_ids(
        db_session,
        project_id=scene.project.id,
        floor_pk=floor.pk,
        removed=(),
        added=("W-WALL000001", "R-ROOM000001"),
        clock=fake_clock,
    )

    assert conflicts == ()
    assert await _owner_of(db_session, scene.project.id, "W-WALL000001") == floor.pk


async def test_claim_without_added_ids_is_a_no_op(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Không thêm gì → `()` ngay, không câu tra chủ nào."""
    scene = await make_scene(db_session)
    conflicts = await claim_entity_ids(
        db_session,
        project_id=scene.project.id,
        floor_pk=scene.floors[0].pk,
        removed=(),
        added=(),
        clock=fake_clock,
    )
    assert conflicts == ()


async def test_removed_ids_are_released(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """`removed` gỡ dòng của **tầng mình**; id đó lập tức nhận lại được."""
    scene = await make_scene(db_session, floors=2)
    mine, other = scene.floors
    await claim_entity_ids(
        db_session,
        project_id=scene.project.id,
        floor_pk=mine.pk,
        removed=(),
        added=("W-WALL000001",),
        clock=fake_clock,
    )

    await claim_entity_ids(
        db_session,
        project_id=scene.project.id,
        floor_pk=mine.pk,
        removed=("W-WALL000001",),
        added=(),
        clock=fake_clock,
    )
    assert await _owner_of(db_session, scene.project.id, "W-WALL000001") is None

    conflicts = await claim_entity_ids(
        db_session,
        project_id=scene.project.id,
        floor_pk=other.pk,
        removed=(),
        added=("W-WALL000001",),
        clock=fake_clock,
    )
    assert conflicts == ()
    assert await _owner_of(db_session, scene.project.id, "W-WALL000001") == other.pk


async def test_removed_ignores_ids_owned_by_another_floor(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """`removed` không đụng id của tầng khác — một lượt ghi không gỡ được id người khác."""
    scene = await make_scene(db_session, floors=2)
    mine, other = scene.floors
    await claim_entity_ids(
        db_session,
        project_id=scene.project.id,
        floor_pk=other.pk,
        removed=(),
        added=("W-WALL000001",),
        clock=fake_clock,
    )

    await claim_entity_ids(
        db_session,
        project_id=scene.project.id,
        floor_pk=mine.pk,
        removed=("W-WALL000001",),
        added=(),
        clock=fake_clock,
    )

    assert await _owner_of(db_session, scene.project.id, "W-WALL000001") == other.pk


async def test_live_owner_always_conflicts(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Chủ cũ còn sống → xung đột, không bao giờ cướp id."""
    scene = await make_scene(db_session, floors=2)
    mine, other = scene.floors
    await claim_entity_ids(
        db_session,
        project_id=scene.project.id,
        floor_pk=other.pk,
        removed=(),
        added=("W-WALL000001",),
        clock=fake_clock,
    )

    conflicts = await claim_entity_ids(
        db_session,
        project_id=scene.project.id,
        floor_pk=mine.pk,
        removed=(),
        added=("W-WALL000001", "W-WALL000002"),
        clock=fake_clock,
    )

    assert conflicts == ("W-WALL000001",)
    assert await _owner_of(db_session, scene.project.id, "W-WALL000002") == mine.pk


async def test_soft_deleted_owner_inside_window_conflicts(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Chủ xoá mềm 5 phút trước (trong cửa sổ 10 phút) vẫn giữ id: tầng ấy còn khôi phục được."""
    scene = await make_scene(db_session, floors=2)
    mine, other = scene.floors
    await claim_entity_ids(
        db_session,
        project_id=scene.project.id,
        floor_pk=other.pk,
        removed=(),
        added=("W-WALL000001",),
        clock=fake_clock,
    )
    await _soft_delete(db_session, other.pk, at=fake_clock.now() - timedelta(minutes=5))

    conflicts = await claim_entity_ids(
        db_session,
        project_id=scene.project.id,
        floor_pk=mine.pk,
        removed=(),
        added=("W-WALL000001",),
        clock=fake_clock,
    )

    assert conflicts == ("W-WALL000001",)


async def test_soft_deleted_owner_past_window_is_reclaimed(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Chủ xoá mềm 11 phút trước (quá cửa sổ 10 phút) → nhận lại được."""
    scene = await make_scene(db_session, floors=2)
    mine, other = scene.floors
    await claim_entity_ids(
        db_session,
        project_id=scene.project.id,
        floor_pk=other.pk,
        removed=(),
        added=("W-WALL000001",),
        clock=fake_clock,
    )
    window = get_floors_settings().floor_restore_window_s
    await _soft_delete(db_session, other.pk, at=fake_clock.now() - timedelta(seconds=window + 60))

    conflicts = await claim_entity_ids(
        db_session,
        project_id=scene.project.id,
        floor_pk=mine.pk,
        removed=(),
        added=("W-WALL000001",),
        clock=fake_clock,
    )

    assert conflicts == ()
    assert await _owner_of(db_session, scene.project.id, "W-WALL000001") == mine.pk


async def test_ids_of_another_project_never_conflict(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Id chỉ duy nhất **trong một dự án**: cùng chuỗi ở dự án khác không cản ai."""
    first = await make_scene(db_session)
    user = await make_user(db_session)
    second_project = await make_project(db_session, owner=user)
    second_floor = await make_floor(db_session, project=second_project)
    await db_session.commit()
    await claim_entity_ids(
        db_session,
        project_id=first.project.id,
        floor_pk=first.floors[0].pk,
        removed=(),
        added=("W-WALL000001",),
        clock=fake_clock,
    )

    conflicts = await claim_entity_ids(
        db_session,
        project_id=second_project.id,
        floor_pk=second_floor.pk,
        removed=(),
        added=("W-WALL000001",),
        clock=fake_clock,
    )

    assert conflicts == ()
    assert await _owner_of(db_session, second_project.id, "W-WALL000001") == second_floor.pk


async def test_parallel_claims_of_one_id_give_exactly_one_conflict(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
) -> None:
    """Hai tầng cùng thêm `Z` song song → đúng **một** bên nhận `("Z-ZZZZ000001",)`."""
    scene = await make_scene(db_session, floors=2)
    left_floor, right_floor = scene.floors

    async def claim(session: AsyncSession, floor_pk: int) -> tuple[str, ...]:
        """Một lượt nhận id trọn vẹn, có commit — giao dịch riêng như B3-03 chạy thật."""
        conflicts = await claim_entity_ids(
            session,
            project_id=scene.project.id,
            floor_pk=floor_pk,
            removed=(),
            added=("W-WALL00000Z",),
            clock=fake_clock,
        )
        await session.commit()
        return conflicts

    async with other_session(db_sessionmaker) as left, other_session(db_sessionmaker) as right:
        results = await race(lambda: claim(left, left_floor.pk), lambda: claim(right, right_floor.pk))

    assert set(results) == {(), ("W-WALL00000Z",)}
    assert await _rows_for(db_session, scene.project.id, "W-WALL00000Z") == 1


async def test_parallel_claims_in_opposite_order_do_not_deadlock(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
) -> None:
    """A thêm `X,Y`, B thêm `Y,X` cùng lúc → không `40P01`: mọi câu đi theo thứ tự `entity_id`."""
    scene = await make_scene(db_session, floors=2)
    left_floor, right_floor = scene.floors

    async def claim(session: AsyncSession, floor_pk: int, added: tuple[str, ...]) -> tuple[str, ...]:
        """Một lượt nhận hai id theo thứ tự người gọi truyền vào (hàm tự sắp lại)."""
        conflicts = await claim_entity_ids(
            session, project_id=scene.project.id, floor_pk=floor_pk, removed=(), added=added, clock=fake_clock
        )
        await session.commit()
        return conflicts

    pair = ("W-WALL00000X", "W-WALL00000Y")
    async with other_session(db_sessionmaker) as left, other_session(db_sessionmaker) as right:
        results = await race(lambda: claim(left, left_floor.pk, pair), lambda: claim(right, right_floor.pk, pair[::-1]))

    assert not any(isinstance(result, BaseException) for result in results)
    for entity_id in pair:
        assert await _rows_for(db_session, scene.project.id, entity_id) == 1


async def test_parallel_reclaims_give_exactly_one_conflict(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
) -> None:
    """Hai tầng cùng nhận lại id của một chủ đã hết hạn → đúng một bên được, một bên xung đột."""
    scene = await make_scene(db_session, floors=3)
    left_floor, right_floor, dead = scene.floors
    await claim_entity_ids(
        db_session,
        project_id=scene.project.id,
        floor_pk=dead.pk,
        removed=(),
        added=("W-WALL00000R",),
        clock=fake_clock,
    )
    window = get_floors_settings().floor_restore_window_s
    await _soft_delete(db_session, dead.pk, at=fake_clock.now() - timedelta(seconds=window + 60))
    await db_session.commit()

    async def claim(session: AsyncSession, floor_pk: int) -> tuple[str, ...]:
        """Một lượt nhận lại id đã hết hạn, có commit."""
        conflicts = await claim_entity_ids(
            session,
            project_id=scene.project.id,
            floor_pk=floor_pk,
            removed=(),
            added=("W-WALL00000R",),
            clock=fake_clock,
        )
        await session.commit()
        return conflicts

    async with other_session(db_sessionmaker) as left, other_session(db_sessionmaker) as right:
        results = await race(lambda: claim(left, left_floor.pk), lambda: claim(right, right_floor.pk))

    assert set(results) == {(), ("W-WALL00000R",)}
    assert await _owner_of(db_session, scene.project.id, "W-WALL00000R") in {left_floor.pk, right_floor.pk}


async def _rows_for(db: AsyncSession, project_id: str, entity_id: str) -> int:
    """Số dòng giữ một id — phải luôn là 0 hoặc 1 (PK `(project_id, entity_id)`)."""
    stmt = (
        select(func.count())
        .select_from(FloorEntityIdRow)
        .where(FloorEntityIdRow.project_id == project_id, FloorEntityIdRow.entity_id == entity_id)
    )
    return (await db.execute(stmt)).scalar_one()
