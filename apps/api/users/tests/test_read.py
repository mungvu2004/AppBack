"""#38 `users_list_users`, #39 `users_list_memberships`, #40 `users_list_activity` (B1-05 [6], [8]).

Loại A: C01 C07 C17 (+ C15 khai `extra` cho #38) và C08 cho #39/#40. Trần đặt = 3 bằng biến
môi trường (`users_limits`). Số truy vấn SQL của #38 đếm bằng `count_sql` dùng chung.
"""

from datetime import timedelta

import httpx
import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.access.activity import record_activity
from apps.api.access.kinds import ActivityKind
from apps.api.auth_recovery.tests.support import seed_token
from apps.api.projects.tests.sql_count import count_sql
from apps.api.users.tests.support import USERS, make_admin, send, users_limits
from packages.db.models.auth import User
from packages.storage.keys import avatar as avatar_key_of
from packages.testing.factories.auth import make_user
from packages.testing.factories.projects import make_project
from packages.testing.fixtures.clock import FakeClock

pytestmark = pytest.mark.usefixtures("api_env")

WIRE_KEYS = {"email", "id", "lastActiveAt", "name", "projectCount", "role", "status"}


async def _soft_delete(db: AsyncSession, user: User) -> None:
    """Xoá mềm thẳng trong DB (không qua #46) để dựng dữ liệu đọc."""
    await db.execute(update(User).where(User.id == user.id).values(deleted_at=User.created_at))
    await db.commit()


async def test_users_list_users__C01(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Người chưa xoá `created_at ASC`; `total` bỏ người xoá mềm; dự án xoá mềm không tính; lời mời hết hạn vẫn hiện."""
    admin = await make_admin(db_session)
    engineer = await make_user(db_session, role="engineer", email="Ky.Su@Example.com")
    pending = await make_user(db_session, status="pending", password=None)
    await seed_token(db_session, user_id=pending.id, purpose="invite", clock=fake_clock, ttl=timedelta(hours=-1))
    gone = await make_user(db_session)
    await _soft_delete(db_session, gone)
    await make_project(db_session, owner=admin, members=[engineer])
    await make_project(db_session, owner=admin, deleted_at=fake_clock.now())
    await db_session.commit()

    response = await send(api_client, admin, "GET", USERS)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"total", "users"}
    assert body["total"] == 3
    rows = body["users"]
    assert [row["id"] for row in rows] == [admin.id, engineer.id, pending.id]
    assert {row["id"]: row["projectCount"] for row in rows} == {admin.id: 1, engineer.id: 1, pending.id: 0}
    assert rows[1]["email"] == "Ky.Su@Example.com"
    assert set(rows[0]) == WIRE_KEYS
    expired = rows[2]
    assert expired["status"] == "pending"
    assert expired["invitedAt"].endswith("Z")
    assert expired["inviteExpiresAt"].endswith("Z")
    assert not {"invitedAt", "inviteExpiresAt"} & set(rows[1])


async def test_users_list_users__C17(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """`lastActiveAt` luôn có khoá (`null` nếu chưa hoạt động); `avatarUrl`/lời mời vắng khoá khi không có."""
    admin = await make_admin(db_session)
    active = await make_user(db_session)
    with_avatar = await make_user(db_session)
    key = avatar_key_of(with_avatar.id, "01JABCDEFGHJKMNPQRSTVWXYZ0", "png")
    await db_session.execute(update(User).where(User.id == with_avatar.id).values(avatar_key=key))
    await db_session.commit()

    rows = (await send(api_client, admin, "GET", USERS)).json()["users"]
    by_id = {row["id"]: row for row in rows}

    assert by_id[active.id]["lastActiveAt"] is None
    assert set(by_id[active.id]) == WIRE_KEYS
    assert "avatarUrl" not in by_id[admin.id]
    assert by_id[with_avatar.id]["avatarUrl"].startswith("http")


async def test_users_list_users__C07(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """`engineer` và `viewer` → 403 `FORBIDDEN` (chỉ admin có `user.manage`)."""
    for role in ("engineer", "viewer"):
        caller = await make_user(db_session, role=role)
        response = await send(api_client, caller, "GET", USERS)
        assert response.status_code == 403
        assert response.json()["code"] == "FORBIDDEN"


async def test_users_list_users__C15(
    api_client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Trần = 3: một người, đúng trần, vượt trần (`total` vẫn đếm đủ, thứ tự cố định)."""
    admin = await make_admin(db_session)
    with users_limits(monkeypatch, users_list_max=3):
        one = (await send(api_client, admin, "GET", USERS)).json()
        assert (one["total"], len(one["users"])) == (1, 1)
        for _ in range(2):
            await make_user(db_session)
        exact = (await send(api_client, admin, "GET", USERS)).json()
        assert (exact["total"], len(exact["users"])) == (3, 3)
        for _ in range(2):
            await make_user(db_session)
        over = (await send(api_client, admin, "GET", USERS)).json()
        assert (over["total"], len(over["users"])) == (5, 3)
        assert [row["id"] for row in over["users"]] == [row["id"] for row in exact["users"]]


async def test_users_list_users_sql_count_is_flat(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Không N+1: 3 và 30 người ra **cùng** số câu SQL (in số để báo cáo)."""
    admin = await make_admin(db_session)
    for _ in range(2):
        await make_user(db_session, password=None)
    with count_sql() as small:
        assert (await send(api_client, admin, "GET", USERS)).status_code == 200
    for _ in range(27):
        await make_user(db_session, password=None)
    with count_sql() as large:
        response = await send(api_client, admin, "GET", USERS)
    assert response.json()["total"] == 30
    print(f"SQL_COUNT users_list_users: 3 nguoi = {small.count}, 30 nguoi = {large.count}")
    assert small.count == large.count


# --------------------------------------------------------------------------- #39


async def test_users_list_memberships__C01(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Dự án chưa xoá mềm, `projectId ASC`, `role` là vai hệ thống hiện tại; dự án xoá mềm và của người khác bị bỏ."""
    admin = await make_admin(db_session)
    member = await make_user(db_session, role="viewer")
    first = await make_project(db_session, owner=admin, members=[member], name="Nhà A")
    second = await make_project(db_session, owner=admin, members=[member], name="Nhà B")
    await make_project(db_session, owner=admin, members=[member], deleted_at=fake_clock.now())
    await make_project(db_session, owner=admin, name="Không có member")
    await db_session.commit()

    response = await send(api_client, admin, "GET", f"{USERS}/{member.id}/memberships")

    assert response.status_code == 200
    assert response.json() == [
        {"projectId": project.id, "projectName": project.name, "role": "viewer"}
        for project in sorted((first, second), key=lambda p: p.id)
    ]


async def test_users_list_memberships__C07(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Thiếu quyền → 403."""
    caller = await make_user(db_session, role="engineer")
    response = await send(api_client, caller, "GET", f"{USERS}/{caller.id}/memberships")
    assert response.status_code == 403


async def test_users_list_memberships__C08(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Không có người hoặc đã xoá mềm → 404 `resource:"user"`."""
    admin = await make_admin(db_session)
    gone = await make_user(db_session)
    await _soft_delete(db_session, gone)
    for user_id in (gone.id, "usr_01JABCDEFGHJKMNPQRSTVWXYZ0"):
        response = await send(api_client, admin, "GET", f"{USERS}/{user_id}/memberships")
        assert response.status_code == 404
        assert response.json()["resource"] == "user"


async def test_users_list_memberships__C15(
    api_client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Trần = 3: rỗng, một dự án, vượt trần (3 dự án đầu theo `projectId ASC`)."""
    admin = await make_admin(db_session)
    member = await make_user(db_session)
    path = f"{USERS}/{member.id}/memberships"
    with users_limits(monkeypatch, user_memberships_max=3):
        assert (await send(api_client, admin, "GET", path)).json() == []
        projects = [await make_project(db_session, owner=admin, members=[member]) for _ in range(5)]
        await db_session.commit()
        ids = [row["projectId"] for row in (await send(api_client, admin, "GET", path)).json()]
    assert ids == sorted(project.id for project in projects)[:3]


# --------------------------------------------------------------------------- #40


async def _log(db: AsyncSession, actor: User, clock: FakeClock, label: str) -> None:
    """Một dòng `activity_log` của `actor`, mốc giờ tăng dần theo `clock`."""
    clock.advance(timedelta(seconds=1))
    await record_activity(
        db, actor_id=actor.id, kind=ActivityKind.PROJECT_CREATE, object_code=label, object_label=label, clock=clock
    )
    await db.commit()


async def test_users_list_activity__C01(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Chỉ dòng có `actor_id` là người này, mới nhất trước; `id` là chuỗi thập phân."""
    admin = await make_admin(db_session)
    other = await make_user(db_session)
    for label in ("một", "hai"):
        await _log(db_session, admin, fake_clock, label)
    await _log(db_session, other, fake_clock, "của người khác")

    response = await send(api_client, admin, "GET", f"{USERS}/{admin.id}/activity")

    assert response.status_code == 200
    rows = response.json()
    assert [row["objectCode"] for row in rows] == ["hai", "một"]
    assert all(row["id"].isdecimal() and row["kind"] == "project.create" for row in rows)
    assert set(rows[0]) == {"id", "at", "kind", "objectCode", "objectLabel"}
    assert rows[0]["at"].endswith("Z")


async def test_users_list_activity__C07(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Thiếu quyền → 403."""
    caller = await make_user(db_session, role="viewer")
    assert (await send(api_client, caller, "GET", f"{USERS}/{caller.id}/activity")).status_code == 403


async def test_users_list_activity__C08(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Không có người hoặc đã xoá mềm → 404."""
    admin = await make_admin(db_session)
    gone = await make_user(db_session)
    await _soft_delete(db_session, gone)
    for user_id in (gone.id, "usr_01JABCDEFGHJKMNPQRSTVWXYZ0"):
        response = await send(api_client, admin, "GET", f"{USERS}/{user_id}/activity")
        assert response.status_code == 404
        assert response.json()["resource"] == "user"


async def test_users_list_activity__C15(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trần = 3: rỗng, một dòng, vượt trần (3 dòng mới nhất)."""
    admin = await make_admin(db_session)
    path = f"{USERS}/{admin.id}/activity"
    with users_limits(monkeypatch, user_activity_max=3):
        assert (await send(api_client, admin, "GET", path)).json() == []
        await _log(db_session, admin, fake_clock, "m1")
        assert len((await send(api_client, admin, "GET", path)).json()) == 1
        for label in ("m2", "m3", "m4", "m5"):
            await _log(db_session, admin, fake_clock, label)
        codes = [row["objectCode"] for row in (await send(api_client, admin, "GET", path)).json()]
    assert codes == ["m5", "m4", "m3"]
