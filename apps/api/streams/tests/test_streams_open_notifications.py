"""`streams_open_notifications` (S2) — S01-S05, S07, S09 trên route thật (B4-01 [8]).

Khác S1 ở hai chỗ và cả hai đều được kiểm ở đây: luồng thông báo **không** có ảnh chụp và
**không** phát lại sự kiện cũ khi mở mới (K32), và nó không có tham số đường nào — người
gọi chỉ đọc được stream của chính `principal.user_id` (không có S06).
"""

import json
import logging
from datetime import timedelta
from typing import Final

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth.sessions import revoke_sessions
from apps.api.auth.settings import get_auth_settings, reset_auth_settings_cache
from apps.api.streams.connections import conn_key
from apps.api.streams.registry import NOTIFICATIONS
from apps.api.streams.sse import PING
from apps.api.streams.tests.fakes import FakePolicy, notifications_provider
from packages.db.hooks import after_commit_idle
from packages.messaging.redis import AsyncRedis
from packages.messaging.streams import EventBus, user_stream
from packages.testing.fixtures.auth import ORIGIN, REFRESH_PATH
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.streams import (
    SseOpen,
    StreamAppFactory,
    publish_notification,
    record_stream_frames,
    sample_notification,
    signed_stream_user,
)

OP: Final = "streams_open_notifications"
PATH: Final = "/api/streams/notifications"

FAST: Final = {"stream_heartbeat_s": "0.2", "stream_recheck_s": "0.2", "stream_read_block_ms": "100"}
CLOSE_BUDGET_S: Final = 1.0
WAIT_S: Final = 3.0

RECHECKS_BEFORE_EVENT: Final = 3
"""Số `: ping` (0,2 s một cái) phải trôi qua trước khi test tin rằng recheck đã chạy vài lượt."""


def _short_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """`AUTH_PRINCIPAL_CACHE_TTL_S=1` — S07 không phải chờ TTL mặc định."""
    monkeypatch.setenv("AUTH_PRINCIPAL_CACHE_TTL_S", "1")
    reset_auth_settings_cache()


# ---------------------------------------------------------------------------
# S01 — cookie luồng thiếu hoặc hỏng → 401
# ---------------------------------------------------------------------------


async def test_streams_open_notifications__S01(stream_app: StreamAppFactory, sse_open: SseOpen) -> None:
    """Không có cookie luồng → 401 `UNAUTHENTICATED`."""
    app = stream_app(providers=[notifications_provider()], **FAST)
    async with sse_open(app, PATH) as stream:
        assert stream.status == 401
        assert json.loads(stream.body)["code"] == "UNAUTHENTICATED"


async def test_streams_open_notifications__S01_malformed(stream_app: StreamAppFactory, sse_open: SseOpen) -> None:
    """Cookie luồng hỏng dạng hay ký bằng khoá lạ → 401."""
    app = stream_app(providers=[notifications_provider()], **FAST)
    async with sse_open(app, PATH, cookies={"appback_stream": "khong.phai.jwt"}) as stream:
        assert stream.status == 401
        assert json.loads(stream.body)["code"] == "UNAUTHENTICATED"


async def test_streams_open_notifications__S01_wrong_audience(
    stream_app: StreamAppFactory, sse_open: SseOpen, db_session: AsyncSession
) -> None:
    """Access token trong cookie luồng → 401: khoá con `access` không mở được luồng."""
    app = stream_app(providers=[notifications_provider()], **FAST)
    async with (
        signed_stream_user(app, db_session) as owner,
        sse_open(app, PATH, cookies={"appback_stream": owner.signed.access_token}) as stream,
    ):
        assert stream.status == 401


async def test_streams_open_notifications__S01_expired(
    stream_app: StreamAppFactory, sse_open: SseOpen, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Cookie luồng hết hạn → 401."""
    app = stream_app(providers=[notifications_provider()], **FAST)
    async with signed_stream_user(app, db_session) as owner:
        fake_clock.advance(timedelta(seconds=get_auth_settings().stream_token_ttl_s + 1))
        async with sse_open(app, PATH, cookies=owner.cookies) as stream:
            assert stream.status == 401


# ---------------------------------------------------------------------------
# S02 — nối lại bằng lastEventId
# ---------------------------------------------------------------------------


async def test_streams_open_notifications__S02(
    stream_app: StreamAppFactory, sse_open: SseOpen, db_session: AsyncSession, event_bus: EventBus
) -> None:
    """Nhận 2/5 rồi rớt; nối lại từ id thứ 2 → đúng 3, 4, 5, đúng thứ tự, không trùng."""
    app = stream_app(providers=[notifications_provider()], **FAST)
    async with signed_stream_user(app, db_session) as owner:
        async with sse_open(app, PATH, cookies=owner.cookies) as first:
            ids = [await publish_notification(event_bus, owner.user.id) for _ in range(5)]
            received = await first.next_frames(2, WAIT_S)
            assert [frame.id for frame in received] == ids[:2]
            await first.disconnect()
        async with sse_open(app, PATH, cookies=owner.cookies, query={"lastEventId": ids[1]}) as second:
            rest = await second.next_frames(3, WAIT_S)
            assert [frame.id for frame in rest] == ids[2:]


async def test_notifications_stream_does_not_replay_on_fresh_open(
    stream_app: StreamAppFactory, sse_open: SseOpen, db_session: AsyncSession, event_bus: EventBus
) -> None:
    """K32: mở mới **không** phát lại thông báo cũ và **không** có ảnh chụp — chỉ sự kiện sau đuôi."""
    app = stream_app(providers=[notifications_provider()], **FAST)
    async with signed_stream_user(app, db_session) as owner:
        for _ in range(3):
            await publish_notification(event_bus, owner.user.id)
        async with sse_open(app, PATH, cookies=owner.cookies) as stream:
            fresh = await publish_notification(event_bus, owner.user.id)
            frames = await stream.next_frames(1, WAIT_S)
            assert [frame.id for frame in frames] == [fresh], "khung đầu tiên phải là sự kiện MỚI"


# ---------------------------------------------------------------------------
# S03 — định dạng khung
# ---------------------------------------------------------------------------


async def test_streams_open_notifications__S03(
    stream_app: StreamAppFactory, sse_open: SseOpen, db_session: AsyncSession, event_bus: EventBus
) -> None:
    """Dây W15 và mẫu H5: khung có `id:`/`data:`, không `event:`, `data` giải được bằng schema FE."""
    app = stream_app(providers=[notifications_provider()], **FAST)
    async with signed_stream_user(app, db_session) as owner, sse_open(app, PATH, cookies=owner.cookies) as stream:
        assert stream.status == 200
        assert stream.headers["content-type"] == "text/event-stream; charset=utf-8"
        assert stream.headers["cache-control"] == "no-store"
        assert stream.headers["x-accel-buffering"] == "no"
        payload = sample_notification()
        await publish_notification(event_bus, owner.user.id, payload)
        frames = await stream.next_frames(1, WAIT_S)
        record_stream_frames(OP, "S03", frames)
        assert frames[0].event is None, "K03: không bao giờ có dòng event:"
        assert frames[0].id
        assert json.loads(frames[0].data) == payload
        assert b"event:" not in stream._raw


async def test_streams_open_notifications__S03_invalid_event(
    stream_app: StreamAppFactory,
    sse_open: SseOpen,
    db_session: AsyncSession,
    event_bus: EventBus,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Sự kiện sai `event_model` bị bỏ; log chỉ có `loc`/`type`, không có nội dung thông báo (K11)."""
    app = stream_app(providers=[notifications_provider()], **FAST)
    private_text = "noi-dung-thong-bao-rieng-tu"
    async with signed_stream_user(app, db_session) as owner, sse_open(app, PATH, cookies=owner.cookies) as stream:
        with caplog.at_level(logging.WARNING, logger="apps.api.streams.sse"):
            await event_bus.publish(user_stream(owner.user.id), {"message": private_text})
            good = await publish_notification(event_bus, owner.user.id)
            frames = await stream.next_frames(1, WAIT_S)
        assert [frame.id for frame in frames] == [good]
        assert any(record.getMessage() == "stream_event_invalid" for record in caplog.records)
        assert private_text not in caplog.text


# ---------------------------------------------------------------------------
# S04 — heartbeat
# ---------------------------------------------------------------------------


async def test_streams_open_notifications__S04(
    stream_app: StreamAppFactory, sse_open: SseOpen, db_session: AsyncSession
) -> None:
    """`STREAM_HEARTBEAT_S=0.1` → `: ping` khi im lặng."""
    app = stream_app(
        providers=[notifications_provider()],
        stream_heartbeat_s="0.1",
        stream_recheck_s="0.2",
        stream_read_block_ms="100",
    )
    async with signed_stream_user(app, db_session) as owner, sse_open(app, PATH, cookies=owner.cookies) as stream:
        raw = await stream.raw_until(lambda data: PING.encode() in data, WAIT_S)
        assert PING.encode() in raw


# ---------------------------------------------------------------------------
# S05 — client rớt
# ---------------------------------------------------------------------------


async def test_streams_open_notifications__S05(
    stream_app: StreamAppFactory,
    sse_open: SseOpen,
    db_session: AsyncSession,
    event_bus: EventBus,
    cache_client: AsyncRedis,
) -> None:
    """Rớt client → `ZREM` chỗ giữ, kể cả khi luồng đang chờ `XREAD BLOCK`."""
    app = stream_app(providers=[notifications_provider()], **FAST)
    async with signed_stream_user(app, db_session) as owner:
        key = conn_key(owner.user.id)
        async with sse_open(app, PATH, cookies=owner.cookies) as stream:
            await publish_notification(event_bus, owner.user.id)
            await stream.next_frames(1, WAIT_S)
            assert await cache_client.zcard(key) == 1
            await stream.disconnect()
        assert await cache_client.zcard(key) == 0


# ---------------------------------------------------------------------------
# S07 — mất quyền giữa chừng
# ---------------------------------------------------------------------------


async def test_streams_open_notifications__S07(
    stream_app: StreamAppFactory,
    sse_open: SseOpen,
    db_session: AsyncSession,
    event_bus: EventBus,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Thu hồi phiên → luồng thông báo đóng ≤ 1 s, không gửi thêm gì."""
    _short_cache(monkeypatch)
    app = stream_app(providers=[notifications_provider()], **FAST)
    async with signed_stream_user(app, db_session) as owner:
        async with sse_open(app, PATH, cookies=owner.cookies) as stream:
            await publish_notification(event_bus, owner.user.id)
            await stream.next_frames(1, WAIT_S)
            await revoke_sessions(db_session, user_id=owner.user.id, reason="logout", clock=fake_clock)
            await db_session.commit()
            await after_commit_idle(db_session)
            elapsed = await stream.wait_closed(WAIT_S)
        with capsys.disabled():
            print(f"\n[S07] notifications revoke_sessions: đóng sau {elapsed:.3f}s")
        assert elapsed <= CLOSE_BUDGET_S


async def test_streams_open_notifications__S07_policy_revoked(
    stream_app: StreamAppFactory,
    sse_open: SseOpen,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Chính sách của B4-02 đổi sang từ chối giữa chừng → luồng đóng ≤ 1 s."""
    _short_cache(monkeypatch)
    policy = FakePolicy()
    app = stream_app(providers=[notifications_provider(policy=policy)], **FAST)
    async with signed_stream_user(app, db_session) as owner:
        async with sse_open(app, PATH, cookies=owner.cookies) as stream:
            policy.allowed = False
            elapsed = await stream.wait_closed(WAIT_S)
        with capsys.disabled():
            print(f"\n[S07] notifications policy từ chối: đóng sau {elapsed:.3f}s")
        assert elapsed <= CLOSE_BUDGET_S


# ---------------------------------------------------------------------------
# S09 — refresh cấp lại cookie; Origin
# ---------------------------------------------------------------------------


async def test_streams_open_notifications__S09(
    stream_app: StreamAppFactory, sse_open: SseOpen, db_session: AsyncSession, event_bus: EventBus
) -> None:
    """Refresh thật xoay cookie luồng; GET **không** `Origin` vẫn mở được (K31)."""
    app = stream_app(providers=[notifications_provider()], **FAST)
    async with signed_stream_user(app, db_session) as owner:
        refreshed = await owner.client.post(REFRESH_PATH, headers=ORIGIN)
        assert refreshed.status_code == 200, refreshed.text
        async with sse_open(app, PATH, cookies=owner.cookies) as stream:
            assert stream.status == 200
            await publish_notification(event_bus, owner.user.id)
            await stream.next_frames(1, WAIT_S)


async def test_streams_open_notifications__S09_foreign_origin(
    stream_app: StreamAppFactory, sse_open: SseOpen, db_session: AsyncSession
) -> None:
    """`Origin` lệch → 403 `ORIGIN_MISMATCH`."""
    app = stream_app(providers=[notifications_provider()], **FAST)
    async with signed_stream_user(app, db_session) as owner:
        headers = {"Origin": "https://ke-tan-cong.example"}
        async with sse_open(app, PATH, cookies=owner.cookies, headers=headers) as stream:
            assert stream.status == 403
            assert json.loads(stream.body)["code"] == "ORIGIN_MISMATCH"


async def test_notifications_stream_survives_rechecks_without_a_policy(
    stream_app: StreamAppFactory, sse_open: SseOpen, db_session: AsyncSession, event_bus: EventBus
) -> None:
    """Nhà cung cấp thông báo **không** có `policy` → recheck chỉ kiểm phiên, luồng sống tiếp.

    Đây là nhánh còn lại của `_still_allowed` sau khi `upload_progress` bị buộc phải có chính
    sách (SEC-02): chỉ luồng thông báo mới đi qua được nó. `STREAM_RECHECK_S=0.2` nên đợi một
    sự kiện sau vài lượt recheck là đủ chứng minh luồng không bị đóng nhầm.
    """
    app = stream_app(providers=[notifications_provider()], **FAST)
    async with signed_stream_user(app, db_session) as owner, sse_open(app, PATH, cookies=owner.cookies) as stream:
        assert app.state.stream_registry[NOTIFICATIONS].policy is None
        await stream.raw_until(lambda raw: raw.count(PING.encode()) >= RECHECKS_BEFORE_EVENT, WAIT_S)
        published = await publish_notification(event_bus, owner.user.id)
        frames = await stream.next_frames(1, WAIT_S)
        assert [frame.id for frame in frames] == [published]
        assert not stream.closed
