"""Redis streams chết — lúc mở và giữa luồng (B4-01 [6] "Redis streams hỏng giữa chừng").

Hai nhánh phòng thủ của `sse.py` chỉ dựng được bằng một Redis **thật** bị dừng hẳn: K23 cấm
mock, và một cổng đóng sẵn không tái hiện được "đang chạy rồi chết" — đó mới là tình huống
làm `XREAD BLOCK` đang chờ bị cắt giữa chừng. `ephemeral_redis` cho mỗi test một instance
riêng, `container.stop()` cắt nó đúng lúc test muốn.

Chỉ `REDIS_BROKER_URL` bị trỏ sang instance tạm — `redis-cache` giữ nguyên, nên lượt đăng
nhập và ZSET giữ chỗ vẫn sống để test khẳng định được chỗ giữ đã thật sự được trả lại.
"""

import json
import logging
from collections.abc import Iterator
from contextlib import suppress
from typing import Final

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from testcontainers.redis import RedisContainer  # type: ignore[import-untyped]

from apps.api.streams.connections import conn_key
from apps.api.streams.sse import DEPENDENCY_ERROR, REDIS_ERROR, RETRY_AFTER_S
from apps.api.streams.tests.fakes import FakePolicy, progress_provider
from apps.api.streams.tests.test_streams_open_progress import FAST, WAIT_S, progress_path
from packages.core.error_codes import DEPENDENCY_UNAVAILABLE
from packages.core.logging import JsonFormatter
from packages.messaging.redis import BROKER_POLICY, AsyncRedis
from packages.messaging.settings import reset_messaging_settings_cache
from packages.testing.fixtures.services import ephemeral_redis
from packages.testing.fixtures.streams import SseOpen, StreamAppFactory, signed_stream_user

SSE_LOGGER: Final = "apps.api.streams.sse"

REDIS_DOWN_WAIT_S: Final = 30.0
"""Trần rộng: redis-py lùi dần vài lượt trước khi bỏ cuộc; test vẫn đỏ chứ không treo."""

ONE_SLOT: Final = {"stream_max_global": "1"}
"""`STREAM_MAX_GLOBAL=1`: `stream_slots.locked()` trả lời thẳng "chỗ đã được trả chưa"."""


class LogCollector(logging.Handler):
    """Gói từng bản ghi bằng `JsonFormatter` **ngay lúc emit**.

    `bind_log_context` để lý do đóng luồng trong một `ContextVar`, không trên `LogRecord`;
    `caplog` giữ record thô và đọc lại sau khi ngữ cảnh đã được gỡ, nên chỉ cách này mới
    thấy được dòng log thật mà sản phẩm ghi ra.
    """

    def __init__(self) -> None:
        """Nhận từ mức INFO (`stream_closed`) trở lên."""
        super().__init__(logging.INFO)
        self.payloads: list[dict[str, object]] = []
        self._formatter = JsonFormatter()

    def emit(self, record: logging.LogRecord) -> None:
        """Ghi lại payload đã gộp ngữ cảnh."""
        self.payloads.append(self._formatter.payload(record))

    def messages(self) -> list[object]:
        """Trường `msg` của mọi dòng đã bắt."""
        return [payload["msg"] for payload in self.payloads]


@pytest.fixture
def sse_log() -> Iterator[LogCollector]:
    """Gắn `LogCollector` vào logger của `apps.api.streams.sse` trong một test."""
    collector = LogCollector()
    logger = logging.getLogger(SSE_LOGGER)
    level = logger.level
    logger.addHandler(collector)
    logger.setLevel(logging.INFO)
    try:
        yield collector
    finally:
        logger.removeHandler(collector)
        logger.setLevel(level)


@pytest.fixture
def dead_broker(monkeypatch: pytest.MonkeyPatch) -> Iterator[RedisContainer]:
    """Một `redis-broker` thật của riêng test, đã trỏ `REDIS_BROKER_URL` vào; test tự `stop()`.

    Trả chính container để test chọn **thời điểm** cắt: trước khi mở luồng, hay giữa luồng.
    `REDIS_CACHE_URL` để nguyên — chỉ DB streams mới được phép chết ở đây.
    """
    container = ephemeral_redis(BROKER_POLICY)
    url = f"redis://{container.get_container_host_ip()}:{container.get_exposed_port(6379)}/0"
    monkeypatch.setenv("REDIS_BROKER_URL", url)
    reset_messaging_settings_cache()
    try:
        yield container
    finally:
        with suppress(Exception):  # test có thể đã tự dừng container
            container.stop()
        reset_messaging_settings_cache()


async def test_stream_closes_when_redis_streams_dies(
    stream_app: StreamAppFactory,
    sse_open: SseOpen,
    db_session: AsyncSession,
    cache_client: AsyncRedis,
    dead_broker: RedisContainer,
    sse_log: LogCollector,
) -> None:
    """Redis streams chết giữa luồng → log rồi kết thúc luồng; chỗ ZSET và chỗ pool được trả.

    Không gửi sự kiện lỗi ra dây: FE chỉ thấy luồng đóng và tự nối lại (W15, `backoff.ts`).
    """
    app = stream_app(providers=[progress_provider()], **ONE_SLOT, **FAST)
    async with signed_stream_user(app, db_session) as owner:
        key = conn_key(owner.user.id)
        async with sse_open(app, progress_path(), cookies=owner.cookies) as stream:
            await stream.next_frames(1, WAIT_S)
            assert await cache_client.zcard(key) == 1
            assert app.state.stream_slots.locked()
            dead_broker.stop()
            await stream.wait_closed(REDIS_DOWN_WAIT_S)
            assert b"data:" not in stream._raw.split(b"\n\n", 1)[-1], "không gửi sự kiện lỗi ra dây"
        assert await cache_client.zcard(key) == 0
        assert not app.state.stream_slots.locked(), "chỗ toàn cục phải được trả lại"
    assert "stream_redis_error" in sse_log.messages()
    closed = [payload for payload in sse_log.payloads if payload["msg"] == "stream_closed"]
    assert closed, "phải có dòng stream_closed"
    assert closed[-1]["reason"] == REDIS_ERROR


async def test_open_reports_dependency_unavailable_when_redis_streams_is_down(
    stream_app: StreamAppFactory,
    sse_open: SseOpen,
    db_session: AsyncSession,
    cache_client: AsyncRedis,
    dead_broker: RedisContainer,
) -> None:
    """Redis streams đã chết **trước** khi mở → 503 `DEPENDENCY_UNAVAILABLE` (C13), không 500.

    Chỗ giữ của người dùng và chỗ toàn cục phải được trả ngay: nếu không, mỗi lượt 503 ăn mất
    một chỗ cho tới khi TTL khoá ZSET hết, và người dùng bị 429 oan khi Redis sống lại.
    """
    app = stream_app(providers=[progress_provider()], **ONE_SLOT, **FAST)
    async with signed_stream_user(app, db_session) as owner:
        dead_broker.stop()
        async with sse_open(app, progress_path(), cookies=owner.cookies) as stream:
            assert stream.status == 503
            assert json.loads(stream.body)["code"] == "DEPENDENCY_UNAVAILABLE"
            assert stream.headers["retry-after"]
        assert await cache_client.zcard(conn_key(owner.user.id)) == 0
        assert not app.state.stream_slots.locked(), "chỗ toàn cục phải được trả lại"


async def test_infrastructure_failure_closes_with_its_own_reason(
    stream_app: StreamAppFactory,
    sse_open: SseOpen,
    db_session: AsyncSession,
    sse_log: LogCollector,
) -> None:
    """Lỗi hạ tầng lúc recheck → `stream_closed` lý do `dependency_error`, không `revoked` (OBS-04).

    Một sự cố Postgres/Redis hiện lên log y hệt một lượt thu hồi quyền thì lúc truy vết không
    ai phân biệt được "hệ thống hỏng" với "người dùng bị đuổi".
    """
    policy = FakePolicy(error=DEPENDENCY_UNAVAILABLE.error(retry_after=RETRY_AFTER_S))
    app = stream_app(providers=[progress_provider(policy=policy)], **FAST)
    async with (
        signed_stream_user(app, db_session) as owner,
        sse_open(app, progress_path(), cookies=owner.cookies) as stream,
    ):
        await stream.next_frames(1, WAIT_S)
        policy.allowed = False
        await stream.wait_closed(WAIT_S)
    closed = [payload for payload in sse_log.payloads if payload["msg"] == "stream_closed"]
    assert closed, "phải có dòng stream_closed"
    assert closed[-1]["reason"] == DEPENDENCY_ERROR
