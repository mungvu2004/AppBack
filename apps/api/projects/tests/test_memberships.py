"""Hàm thành viên dự án trên Postgres thật (K23): xoá mềm, số truy vấn, thứ tự, mồ côi."""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.projects.memberships import (
    add_member,
    count_projects_of_users,
    is_member,
    list_projects_of_user,
    lock_editor_ids,
    member_users,
    remove_member,
    remove_user_from_all_projects,
)
from apps.api.projects.tests.sql_count import count_sql
from packages.db.models.projects import Project
from packages.testing.factories.auth import make_user
from packages.testing.factories.projects import make_project
from packages.testing.fixtures.clock import FakeClock

DELETED_AT = datetime(2026, 1, 1, tzinfo=UTC)


async def test_add_member_is_idempotent_and_remove_member_reports_the_row(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Lượt đầu `True`, lượt sau `False`; gỡ rồi gỡ lại → `True` rồi `False`."""
    owner = await make_user(db_session)
    guest = await make_user(db_session)
    project = await make_project(db_session, owner=owner)
    added = await add_member(db_session, project_id=project.id, user_id=guest.id, added_by=owner.id, clock=fake_clock)
    again = await add_member(db_session, project_id=project.id, user_id=guest.id, added_by=owner.id, clock=fake_clock)
    await db_session.commit()
    assert (added, again) == (True, False)
    async with db_sessionmaker() as fresh:
        assert await is_member(fresh, project.id, guest.id)
    assert await remove_member(db_session, project_id=project.id, user_id=guest.id) is True
    assert await remove_member(db_session, project_id=project.id, user_id=guest.id) is False
    await db_session.commit()
    async with db_sessionmaker() as fresh:
        assert not await is_member(fresh, project.id, guest.id)


async def test_is_member_is_false_for_a_soft_deleted_project(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Dự án xoá mềm → mọi thành viên mất quyền ngay (#27), kể cả người tạo."""
    owner = await make_user(db_session)
    project = await make_project(db_session, owner=owner, deleted_at=DELETED_AT)
    await db_session.commit()
    async with db_sessionmaker() as fresh:
        assert not await is_member(fresh, project.id, owner.id)
        assert not await is_member(fresh, "prj_khong-co", owner.id)


async def test_member_users_runs_one_query_and_drops_deleted_people(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Một truy vấn cho nhiều dự án; bỏ người xoá mềm; dự án không có ai vẫn có khoá."""
    owner = await make_user(db_session)
    gone = await make_user(db_session)
    gone.deleted_at = DELETED_AT
    first = await make_project(db_session, owner=owner, members=[gone])
    second = await make_project(db_session, owner=owner)
    await db_session.commit()
    with count_sql() as counter:
        async with db_sessionmaker() as fresh:
            by_project = await member_users(fresh, [first.id, second.id, "prj_khong-co"])
    assert counter.count == 1, counter.statements
    assert [user.id for user in by_project[first.id]] == [owner.id]
    assert [user.id for user in by_project[second.id]] == [owner.id]
    assert by_project["prj_khong-co"] == []


async def test_member_users_sorts_by_user_id(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Trong mỗi dự án, thành viên sắp `user_id ASC` (FE dựng chữ cái đầu theo thứ tự ổn định)."""
    owner = await make_user(db_session)
    mates = [await make_user(db_session) for _ in range(3)]
    project = await make_project(db_session, owner=owner, members=mates)
    await db_session.commit()
    async with db_sessionmaker() as fresh:
        ids = [user.id for user in (await member_users(fresh, [project.id]))[project.id]]
    assert ids == sorted(ids)
    assert set(ids) == {owner.id, *(mate.id for mate in mates)}


async def test_count_projects_of_users_skips_deleted_projects(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Dự án xoá mềm không tính; người không có dự án nào (hay id lạ) → 0."""
    owner = await make_user(db_session)
    await make_project(db_session, owner=owner)
    await make_project(db_session, owner=owner)
    await make_project(db_session, owner=owner, deleted_at=DELETED_AT)
    await db_session.commit()
    async with db_sessionmaker() as fresh:
        counts = await count_projects_of_users(fresh, [owner.id, "usr_khong-co"])
    assert counts == {owner.id: 2, "usr_khong-co": 0}


async def test_list_projects_of_user_sorts_by_id_and_honours_the_limit(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """`id ASC`, bỏ dự án xoá mềm, cắt đúng `limit`; trả `ProjectRef(id, name)`."""
    owner = await make_user(db_session)
    live = [await make_project(db_session, owner=owner, name=f"Dự án {index}") for index in range(3)]
    await make_project(db_session, owner=owner, deleted_at=DELETED_AT)
    await db_session.commit()
    async with db_sessionmaker() as fresh:
        refs = await list_projects_of_user(fresh, owner.id, limit=2)
        every = await list_projects_of_user(fresh, owner.id, limit=10)
    assert [ref.id for ref in refs] == sorted(project.id for project in live)[:2]
    assert len(every) == 3
    assert {ref.name for ref in every} == {project.name for project in live}


async def test_lock_editor_ids_returns_only_active_editors_in_order(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Chỉ `admin|engineer` đang `active` và chưa xoá mềm, sắp `user_id ASC`."""
    admin = await make_user(db_session, role="admin")
    engineer = await make_user(db_session, role="engineer")
    viewer = await make_user(db_session, role="viewer")
    disabled = await make_user(db_session, role="engineer", status="disabled")
    deleted = await make_user(db_session, role="admin")
    deleted.deleted_at = DELETED_AT
    project = await make_project(db_session, owner=admin, members=[engineer, viewer, disabled, deleted])
    await db_session.commit()
    async with db_sessionmaker() as fresh:
        ids = await lock_editor_ids(fresh, project.id)
    assert ids == sorted([admin.id, engineer.id])


async def test_remove_user_from_all_projects_reports_orphans_and_touches_projects(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Trả dự án còn sống mà không còn người sửa; dự án còn engineer hay đã xoá thì không."""
    target = await make_user(db_session, role="engineer")
    viewer = await make_user(db_session, role="viewer")
    engineer = await make_user(db_session, role="engineer")
    orphan_with_viewer = await make_project(db_session, owner=target, members=[viewer])
    kept = await make_project(db_session, owner=target, members=[engineer])
    alone = await make_project(db_session, owner=target)
    removed = await make_project(db_session, owner=target, deleted_at=DELETED_AT)
    await db_session.commit()

    orphans = await remove_user_from_all_projects(db_session, target.id, clock=fake_clock)
    await db_session.commit()
    assert orphans == sorted([orphan_with_viewer.id, alone.id])
    assert removed.id not in orphans
    assert kept.id not in orphans

    async with db_sessionmaker() as fresh:
        assert await count_projects_of_users(fresh, [target.id]) == {target.id: 0}
        touched = await fresh.get_one(Project, kept.id)
        assert touched.updated_at == fake_clock.now()


async def test_remove_user_from_all_projects_does_not_scale_sql_with_project_count(
    db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """PERF-01: 1 dự án và 5 dự án tốn **cùng** số câu SQL — `touch_projects` gộp một `UPDATE`."""
    one = await make_user(db_session, role="engineer")
    many = await make_user(db_session, role="engineer")
    await make_project(db_session, owner=one)
    for _ in range(5):
        await make_project(db_session, owner=many)
    await db_session.commit()

    with count_sql() as small:
        await remove_user_from_all_projects(db_session, one.id, clock=fake_clock)
    with count_sql() as big:
        await remove_user_from_all_projects(db_session, many.id, clock=fake_clock)
    assert big.count == small.count, f"1 dự án = {small.count} câu, 5 dự án = {big.count}; {big.statements}"


async def test_remove_user_from_all_projects_of_a_stranger_changes_nothing(
    db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Người chưa ở dự án nào → danh sách rỗng, không lệnh ghi nào hỏng."""
    stranger = await make_user(db_session)
    assert await remove_user_from_all_projects(db_session, stranger.id, clock=fake_clock) == []
