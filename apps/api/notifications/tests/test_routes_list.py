"""#19 `notifications_list` (B4-02 [8]): Đ* — C01 C15 C17, cộng luật ẩn của [6]."""

from datetime import timedelta
from typing import Final

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.notifications.kinds import FLOOR_PLACES, PLACES
from apps.api.notifications.tests.support import (
    FLOOR,
    commit_notify,
    get_list,
    remove_member,
    seed_project,
    settings_env,
)
from packages.testing.factories.auth import make_user
from packages.testing.factories.notifications import make_notification
from packages.testing.fixtures.clock import FakeClock

PLAIN_KEYS: Final = {"id", "kind", "place", "projectId", "projectName", "objectLabel", "message", "isRead", "createdAt"}


async def _seed_all_kinds(db: AsyncSession, clock: FakeClock, user_id: str, project_id: str) -> None:
    """Chín `place` với `aiCompleted`, cộng một `violationFound` và một `projectInvite`; mỗi dòng cách nhau 1 giây."""
    for place in PLACES:
        clock.advance(timedelta(seconds=1))
        kind, floor, label = "aiCompleted", (FLOOR if place in FLOOR_PLACES else None), "tầng trệt"
        if place == "projectSettings":
            kind, label = "projectInvite", "Chung cư Sông Hàn"
        await commit_notify(
            db,
            clock,
            user_id=user_id,
            project_id=project_id,
            project_name="Chung cư Sông Hàn",
            kind=kind,
            place=place,
            floor_level_id=floor,
            object_label=label,
        )
    clock.advance(timedelta(seconds=1))
    await commit_notify(
        db,
        clock,
        user_id=user_id,
        project_id=project_id,
        project_name="Chung cư Sông Hàn",
        kind="violationFound",
        floor_level_id=None,
        place="rules",
        object_label="tầng 2",
        message="phát hiện 3 vi phạm luật ở",
    )


async def test_notifications_list__C01(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Đủ 3 `kind` và 9 `place` dựng bằng `notify`: mảng trần, mới nhất trước, đúng bộ khoá của `NotificationSchema`."""
    user = await make_user(db_session)
    project = await seed_project(db_session, owner=user)
    await _seed_all_kinds(db_session, fake_clock, user.id, project.id)

    response = await get_list(api_client, user)

    assert response.status_code == 200
    items = response.json()
    assert isinstance(items, list)
    assert len(items) == len(PLACES) + 1
    assert items[0]["kind"] == "violationFound"  # dòng dựng sau cùng đứng đầu
    assert {item["kind"] for item in items} == {"aiCompleted", "violationFound", "projectInvite"}
    assert {item["place"] for item in items} == set(PLACES)
    for item in items:
        assert set(item) - {"floorId"} == PLAIN_KEYS
        assert (item["place"] in FLOOR_PLACES) == ("floorId" in item)
        assert item["isRead"] is False
        assert item["createdAt"].endswith("Z")


async def test_notifications_list__C15_empty_and_one(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """0 dòng → `[]`; 1 dòng → mảng một phần tử."""
    user = await make_user(db_session)
    project = await seed_project(db_session, owner=user)
    assert (await get_list(api_client, user)).json() == []
    await commit_notify(db_session, fake_clock, user_id=user.id, project_id=project.id, project_name="Dự án")
    assert len((await get_list(api_client, user)).json()) == 1


async def test_notifications_list__C15_cap(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`LIST_MAX=3` với 5 dòng → 3 dòng mới nhất, đúng thứ tự."""
    user = await make_user(db_session)
    project = await seed_project(db_session, owner=user)
    base = fake_clock.now()
    rows = [
        await make_notification(db_session, user=user, project=project, created_at=base + timedelta(minutes=n))
        for n in range(5)
    ]
    await db_session.commit()
    with settings_env(monkeypatch, list_max="3"):
        response = await get_list(api_client, user)
    assert [item["id"] for item in response.json()] == [row.id for row in reversed(rows[2:])]


async def test_notifications_list__C15_tie_break(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Hai dòng cùng `created_at` → thứ tự `id DESC`, ổn định giữa hai lần đọc."""
    user = await make_user(db_session)
    project = await seed_project(db_session, owner=user)
    same = fake_clock.now()
    rows = [await make_notification(db_session, user=user, project=project, created_at=same) for _ in range(3)]
    await db_session.commit()
    expected = sorted((row.id for row in rows), reverse=True)
    for _ in range(2):
        assert [item["id"] for item in (await get_list(api_client, user)).json()] == expected


async def test_notifications_list__C17(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """`projectInvite` không có `floorId`, `excerpt`; `aiCompleted` ở `walls` có `floorId`; `excerpt` chỉ khi có."""
    user = await make_user(db_session)
    project = await seed_project(db_session, owner=user)
    await commit_notify(
        db_session,
        fake_clock,
        user_id=user.id,
        project_id=project.id,
        project_name="Dự án",
        kind="projectInvite",
        place="projectSettings",
        floor_level_id=None,
        object_label="Dự án",
        message="bạn vừa được thêm vào dự án",
    )
    fake_clock.advance(timedelta(seconds=1))
    await commit_notify(
        db_session, fake_clock, user_id=user.id, project_id=project.id, project_name="Dự án", excerpt="  đoạn   trích "
    )
    items = (await get_list(api_client, user)).json()
    walls, invite = items
    assert walls["floorId"] == FLOOR
    assert walls["excerpt"] == "đoạn trích"
    assert "floorId" not in invite
    assert "excerpt" not in invite


async def test_notifications_list__only_own_rows(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Không thấy dòng của người khác, kể cả trong dự án chung."""
    mine, other = await make_user(db_session), await make_user(db_session)
    project = await seed_project(db_session, owner=mine, members=[other])
    await make_notification(db_session, user=other, project=project)
    await db_session.commit()
    assert (await get_list(api_client, mine)).json() == []


async def test_notifications_list__hidden_when_removed_or_project_deleted(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Người nhận bị gỡ khỏi dự án, hay dự án xoá mềm → dòng ẩn khỏi #19; dự án khác vẫn hiện."""
    user = await make_user(db_session)
    owner = await make_user(db_session)
    kept = await seed_project(db_session, owner=owner, members=[user])
    removed = await seed_project(db_session, owner=owner, members=[user])
    deleted = await seed_project(db_session, owner=owner, members=[user], deleted_at=fake_clock.now())
    visible = await make_notification(db_session, user=user, project=kept)
    for project in (removed, deleted):
        await make_notification(db_session, user=user, project=project)
    await db_session.commit()
    await remove_member(db_session, removed, user)

    assert [item["id"] for item in (await get_list(api_client, user)).json()] == [visible.id]
