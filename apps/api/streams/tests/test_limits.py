"""Trần kết nối SSE: theo người dùng, theo tiến trình, và khi `redis-cache` chết (B4-01 [8]).

Ba hàng rào khác nhau, đừng lẫn: ZSET `streams:conn:{user}` chặn một người mở quá nhiều
thẻ (`STREAM_MAX_PER_USER`), bộ đếm chỗ của tiến trình chặn cả máy chủ giữ quá nhiều
socket `XREAD BLOCK` (`STREAM_MAX_GLOBAL`), còn `redis-cache` chết thì **không** được
chặn ai cả — hạn mức là chống lạm dụng, quyền nằm ở `check_session`.
"""

import json
from contextlib import AsyncExitStack, suppress
from typing import Final

import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.streams.connections import conn_key
from apps.api.streams.sse import RETRY_AFTER_S
from apps.api.streams.tests.fakes import progress_provider
from apps.api.streams.tests.test_streams_open_progress import FAST, WAIT_S, progress_path
from packages.messaging.redis import AsyncRedis
from packages.testing.fixtures.streams import SseOpen, StreamAppFactory, signed_stream_user

MAX_PER_USER: Final = 6
MAX_GLOBAL: Final = 3
DEAD_PORT: Final = 1
"""Cổng không ai nghe: dựng "`redis-cache` chết" bằng máy chủ thật vắng mặt, không mock (K23)."""

CLEANUP_SLOTS: Final = 2
SLOT_ROUNDS: Final = 5
"""Nhiều hơn số chỗ: rò một chỗ hay một kết nối pool là lượt thứ ba đã hỏng."""


async def test_seventh_connection_of_one_user_is_rate_limited(
    stream_app: StreamAppFactory, sse_open: SseOpen, db_session: AsyncSession, cache_client: AsyncRedis
) -> None:
    """Sáu luồng cùng người đều mở được; cái thứ bảy 429 + `Retry-After: 5`, đóng một cái thì lại mở được."""
    app = stream_app(providers=[progress_provider()], stream_max_per_user=str(MAX_PER_USER), **FAST)
    async with signed_stream_user(app, db_session) as owner, AsyncExitStack() as opened:
        streams = [
            await opened.enter_async_context(sse_open(app, progress_path(), cookies=owner.cookies))
            for _ in range(MAX_PER_USER)
        ]
        for stream in streams:
            assert stream.status == 200
        assert await cache_client.zcard(conn_key(owner.user.id)) == MAX_PER_USER

        async with sse_open(app, progress_path(), cookies=owner.cookies) as seventh:
            assert seventh.status == 429
            assert json.loads(seventh.body)["code"] == "RATE_LIMITED"
            assert seventh.headers["retry-after"] == str(RETRY_AFTER_S)
        assert await cache_client.zcard(conn_key(owner.user.id)) == MAX_PER_USER, "lượt bị từ chối không để lại chỗ ma"

        await streams[0].disconnect()
        async with sse_open(app, progress_path(), cookies=owner.cookies) as again:
            assert again.status == 200
            await again.next_frames(1, WAIT_S)


async def test_global_slot_exhaustion_returns_429(
    stream_app: StreamAppFactory, sse_open: SseOpen, db_session: AsyncSession
) -> None:
    """`STREAM_MAX_GLOBAL=3`: ba người mở được, người thứ tư nhận 429 **trước** khi luồng mở."""
    app = stream_app(providers=[progress_provider()], stream_max_global=str(MAX_GLOBAL), **FAST)
    async with AsyncExitStack() as stack:
        owners = [await stack.enter_async_context(signed_stream_user(app, db_session)) for _ in range(MAX_GLOBAL + 1)]
        for owner in owners[:MAX_GLOBAL]:
            stream = await stack.enter_async_context(sse_open(app, progress_path(), cookies=owner.cookies))
            assert stream.status == 200
        async with sse_open(app, progress_path(), cookies=owners[MAX_GLOBAL].cookies) as extra:
            assert extra.status == 429
            assert json.loads(extra.body)["code"] == "RATE_LIMITED"
            assert extra.headers["retry-after"] == str(RETRY_AFTER_S)


async def test_stream_opens_when_connection_cache_is_down(
    stream_app: StreamAppFactory, sse_open: SseOpen, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`redis-cache` chết → vẫn mở được luồng (fail-open), vì quyền không nằm ở cache."""
    app = stream_app(providers=[progress_provider()], **FAST)
    async with signed_stream_user(app, db_session) as owner:
        dead: AsyncRedis = Redis.from_url(
            f"redis://127.0.0.1:{DEAD_PORT}/0", decode_responses=True, socket_connect_timeout=0.2, socket_timeout=0.2
        )
        monkeypatch.setattr(app.state, "cache_redis", dead)
        try:
            async with sse_open(app, progress_path(), cookies=owner.cookies) as stream:
                assert stream.status == 200
                await stream.next_frames(1, WAIT_S)
        finally:
            await dead.aclose()


async def test_cleanup_returns_the_slot_when_the_cache_is_down(
    stream_app: StreamAppFactory, sse_open: SseOpen, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`redis-cache` chết → `ZREM` lúc dọn hỏng, nhưng chỗ toàn cục và kết nối pool vẫn phải về.

    Dọn luồng có hai việc: một lời gọi **mạng** tới `redis-cache` (có trần 1 giây) và một thao
    tác cục bộ trả kết nối về pool SSE. Gói chung một trần thì lượt hỏng ở việc thứ nhất cuốn
    luôn việc thứ hai, và pool cạn dần trong khi bộ đếm chỗ vẫn báo còn trống. Năm lượt mở-đóng
    liên tiếp với `STREAM_MAX_GLOBAL=2` bắt đúng hồi quy đó: lượt thứ ba trở đi sẽ 429 hoặc 503.
    """
    app = stream_app(providers=[progress_provider()], stream_max_global=str(CLEANUP_SLOTS), **FAST)
    async with signed_stream_user(app, db_session) as owner:
        dead: AsyncRedis = Redis.from_url(
            f"redis://127.0.0.1:{DEAD_PORT}/0", decode_responses=True, socket_connect_timeout=0.2, socket_timeout=0.2
        )
        monkeypatch.setattr(app.state, "cache_redis", dead)
        try:
            for round_number in range(SLOT_ROUNDS):
                async with sse_open(app, progress_path(), cookies=owner.cookies) as stream:
                    assert stream.status == 200, f"lượt {round_number}: {stream.body!r}"
                    await stream.next_frames(1, WAIT_S)
                    await stream.disconnect()
                assert not app.state.stream_slots.locked(), f"lượt {round_number} không trả chỗ"
        finally:
            await dead.aclose()


async def test_cleanup_returns_the_slot_when_the_pool_release_fails(
    stream_app: StreamAppFactory, sse_open: SseOpen, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bước trả kết nối **ném** → chỗ toàn cục vẫn phải về (RES-02).

    `ConnectionPool.release` ném được thật khi pool đang đóng lúc app dừng. Chỗ toàn cục rò ở
    đây là rò **vĩnh viễn** trong cả đời tiến trình: không có TTL nào nhặt lại như mục ZSET,
    nên mỗi lượt rò là một luồng nữa không ai mở được. Lỗi dọn cứ việc nổi lên cho khung ghi
    log — test này chỉ đo chỗ giữ.
    """
    app = stream_app(providers=[progress_provider()], stream_max_global="1", **FAST)
    async with signed_stream_user(app, db_session) as owner:
        async with sse_open(app, progress_path(), cookies=owner.cookies) as stream:
            await stream.next_frames(1, WAIT_S)
            assert app.state.stream_slots.locked()

            async def boom(connection: object) -> None:
                """Pool đã đóng: trả kết nối ném thay vì im lặng."""
                raise RuntimeError("pool đã đóng")

            monkeypatch.setattr(app.state.stream_pool, "release", boom)
            with suppress(Exception):  # lỗi dọn là việc của khung; test đo chỗ giữ
                await stream.disconnect()
        assert not app.state.stream_slots.locked(), "chỗ toàn cục phải được trả dù bước dọn ném"
