"""Sink lời mời qua N3 thật, cổng dò và luồng S2 với nhà cung cấp thật (B4-02 [6], [8] "Sink", "Cổng dò")."""

import json
from datetime import UTC, datetime, timedelta
from typing import Final

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core import extensions
from apps.api.notifications.invite_sinks import SINKS, ProjectInviteNotifier
from apps.api.notifications.schemas import NotificationOut
from apps.api.notifications.stream_providers import PROVIDERS
from apps.api.notifications.tests.support import LIST_PATH, commit_notify, rows_of, seed_project
from apps.api.project_members.sinks import ATTR, SUBMODULE, invite_sink
from apps.api.streams.registry import NOTIFICATIONS, build_registry
from packages.db.hooks import after_commit_idle
from packages.messaging.redis import AsyncRedis
from packages.messaging.streams import EventBus, user_stream
from packages.testing.factories.auth import make_user
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.streams import (
    SseOpen,
    StreamAppFactory,
    StreamUser,
    publish_notification,
    record_stream_frames,
    sample_notification,
    signed_stream_user,
)

OP: Final = "streams_open_notifications"
PATH: Final = "/api/streams/notifications"
FAST: Final = {"stream_heartbeat_s": "0.2", "stream_recheck_s": "0.2", "stream_read_block_ms": "100"}
WAIT_S: Final = 3.0
QUIET_S: Final = 0.6
HOUR_START: Final = datetime(2026, 1, 1, 0, 55, tzinfo=UTC)
"""Còn 5 phút tới giờ UTC kế; access token sống 10 phút nên cộng 6 phút vẫn hợp lệ."""


def _members(project_id: str, user_id: str | None = None) -> str:
    """`/api/projects/{id}/members[/{user_id}]`."""
    base = f"/api/projects/{project_id}/members"
    return base if user_id is None else f"{base}/{user_id}"


async def _add(actor: StreamUser, project_id: str, email: str, **headers: str) -> int:
    """N3 với tư cách `actor` (đăng nhập thật); trả status."""
    response = await actor.client.post(
        _members(project_id), json={"email": email}, headers={**actor.signed.headers, **headers}
    )
    return response.status_code


async def _remove(actor: StreamUser, project_id: str, user_id: str) -> int:
    """N4 với tư cách `actor`; trả status."""
    response = await actor.client.delete(_members(project_id, user_id), headers=actor.signed.headers)
    return response.status_code


async def _listing(user: StreamUser) -> list[dict[str, object]]:
    """#19 của `user` qua phiên đăng nhập thật."""
    response = await user.client.get(LIST_PATH, headers=user.signed.headers)
    assert response.status_code == 200
    return list(response.json())


async def test_sink__invite_through_n3_reaches_list_and_stream(
    stream_app: StreamAppFactory, sse_open: SseOpen, db_session: AsyncSession, streams_client: AsyncRedis
) -> None:
    """Admin thêm engineer qua N3 → 1 dòng `projectInvite`, luồng S2 mở sẵn nhận đúng 1 khung; N3 lặp không thêm gì."""
    app = stream_app(**FAST)
    async with (
        signed_stream_user(app, db_session, role="admin") as admin,
        signed_stream_user(app, db_session) as engineer,
    ):
        project = await seed_project(db_session, owner=admin.user, name="Chung cư Sông Hàn")
        stream_key = user_stream(engineer.user.id)
        async with sse_open(app, PATH, cookies=engineer.cookies) as stream:
            assert (
                await _add(admin, project.id, engineer.user.email, **{"Idempotency-Key": "khoa-them-thanh-vien-01"})
                == 201
            )
            frames = await stream.next_frames(1, WAIT_S)
            record_stream_frames(OP, "S02_invite", frames)

            (item,) = await _listing(engineer)
            assert json.loads(frames[0].data) == item, "một nguồn cho REST và SSE"
            assert item["kind"] == "projectInvite"
            assert item["place"] == "projectSettings"
            assert item["objectLabel"] == project.name == item["projectName"]
            assert item["message"] == f"{admin.user.name} đã thêm bạn vào dự án"

            # Cùng key: phát lại response cũ; khác key: đã là thành viên nên 200. Cả hai không dòng, không khung.
            assert (
                await _add(admin, project.id, engineer.user.email, **{"Idempotency-Key": "khoa-them-thanh-vien-01"})
                == 201
            )
            assert (
                await _add(admin, project.id, engineer.user.email, **{"Idempotency-Key": "khoa-them-thanh-vien-02"})
                == 200
            )
            with pytest.raises(TimeoutError):
                await stream.next_frames(1, QUIET_S)

        assert len(await rows_of(db_session, engineer.user.id)) == 1
        xlen = await streams_client.xlen(stream_key)
        print(f"XLEN events:user:{{u}} sau N3 lặp = {xlen}")  # số liệu cho báo cáo [11].4
        assert xlen == 1


async def test_sink__adding_yourself_makes_no_row(
    stream_app: StreamAppFactory, db_session: AsyncSession, streams_client: AsyncRedis
) -> None:
    """Admin tự thêm mình (đã là thành viên → không tới sink) → không dòng."""
    app = stream_app(**FAST)
    async with signed_stream_user(app, db_session, role="admin") as admin:
        project = await seed_project(db_session, owner=admin.user)
        assert await _add(admin, project.id, admin.user.email) == 200
        assert await rows_of(db_session) == []


async def test_sink__add_remove_add_same_utc_hour_makes_one_row_next_hour_two(
    stream_app: StreamAppFactory, db_session: AsyncSession, fake_clock: FakeClock, streams_client: AsyncRedis
) -> None:
    """Thêm-gỡ-thêm trong cùng giờ UTC → 1 dòng; sang giờ sau (`fake_clock`) → 2 dòng."""
    fake_clock.set(HOUR_START)
    app = stream_app(**FAST)
    async with (
        signed_stream_user(app, db_session, role="admin") as admin,
        signed_stream_user(app, db_session) as engineer,
    ):
        project = await seed_project(db_session, owner=admin.user)
        assert await _add(admin, project.id, engineer.user.email) == 201
        assert await _remove(admin, project.id, engineer.user.id) == 200
        assert await _add(admin, project.id, engineer.user.email) == 201
        assert len(await rows_of(db_session, engineer.user.id)) == 1

        fake_clock.advance(timedelta(minutes=6))
        assert await _remove(admin, project.id, engineer.user.id) == 200
        assert await _add(admin, project.id, engineer.user.email) == 201
        assert len(await rows_of(db_session, engineer.user.id)) == 2


async def test_sink__direct_call_rules(
    db_session: AsyncSession, fake_clock: FakeClock, streams_client: AsyncRedis
) -> None:
    """Gọi thẳng: `user_id == actor_id` → không làm gì; người thêm đã xoá mềm → câu vô danh; cùng giờ → một dòng."""
    admin, target = await make_user(db_session, role="admin"), await make_user(db_session)
    ghost = await make_user(db_session, role="admin")
    ghost.deleted_at = fake_clock.now()
    project = await seed_project(db_session, owner=admin, members=[target, ghost])
    sink = ProjectInviteNotifier()

    async def added(actor_id: str, user_id: str = target.id) -> None:
        """Gọi sink cho `user_id` do `actor_id` thêm vào `project`."""
        await sink.on_member_added(
            db_session,
            project_id=project.id,
            project_name=project.name,
            user_id=user_id,
            actor_id=actor_id,
            clock=fake_clock,
        )

    await added(target.id)
    assert await rows_of(db_session) == []

    await added(ghost.id)
    await added(admin.id)
    await db_session.commit()
    await after_commit_idle(db_session)
    rows = await rows_of(db_session, target.id)
    assert [row.message for row in rows] == ["bạn vừa được thêm vào dự án"], "khoá cùng giờ: lượt hai bị gộp"

    fake_clock.advance(timedelta(hours=1))
    await added(admin.id)
    await db_session.commit()
    await after_commit_idle(db_session)
    assert [row.message for row in await rows_of(db_session, target.id)][-1] == f"{admin.name} đã thêm bạn vào dự án"


# ---------------------------------------------------------------------------
# Cổng dò
# ---------------------------------------------------------------------------


def test_discovery__invite_sinks_finds_exactly_one_sink() -> None:
    """Dò `invite_sinks` của B2-02 thấy đúng một sink (của module này), và `invite_sink()` trả chính nó."""
    found = extensions.discover(SUBMODULE, ATTR)
    assert [name for name, _ in found] == ["apps.api.notifications.invite_sinks"]
    assert len(SINKS) == 1
    assert isinstance(invite_sink(), ProjectInviteNotifier)


def test_discovery__stream_providers_resolve_without_error() -> None:
    """Sổ nhà cung cấp thật dựng được; `notifications` dùng `NotificationOut`, không policy, không snapshot."""
    provider = build_registry(None)[NOTIFICATIONS]
    assert provider is PROVIDERS[0]
    assert provider.event_model is NotificationOut
    assert (provider.policy, provider.snapshot) == (None, None)


async def test_stream__event_without_place_is_dropped(
    stream_app: StreamAppFactory, sse_open: SseOpen, db_session: AsyncSession, event_bus: EventBus
) -> None:
    """Sự kiện thiếu `place` bị luồng bỏ; sự kiện hợp lệ đi tiếp và giải được bằng `NotificationOut`."""
    app = stream_app(**FAST)
    async with signed_stream_user(app, db_session) as owner, sse_open(app, PATH, cookies=owner.cookies) as stream:
        broken = {key: value for key, value in sample_notification().items() if key != "place"}
        await publish_notification(event_bus, owner.user.id, broken)
        good = await publish_notification(event_bus, owner.user.id)
        frames = await stream.next_frames(1, WAIT_S)
        record_stream_frames(OP, "S03_place", frames)
    assert [frame.id for frame in frames] == [good]
    NotificationOut.model_validate(json.loads(frames[0].data))


async def test_notify__rows_visible_only_to_owner_stream(
    db_session: AsyncSession, fake_clock: FakeClock, streams_client: AsyncRedis
) -> None:
    """XADD đi vào stream của người nhận, không của người khác."""
    mine, other = await make_user(db_session), await make_user(db_session)
    project = await seed_project(db_session, owner=mine, members=[other])
    await commit_notify(db_session, fake_clock, user_id=mine.id, project_id=project.id, project_name="A")
    assert (await streams_client.xlen(user_stream(mine.id)), await streams_client.xlen(user_stream(other.id))) == (1, 0)
