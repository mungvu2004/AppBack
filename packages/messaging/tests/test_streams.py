"""Bus sự kiện trên Redis thật: thứ tự, khử trùng, cắt bớt, và lỗi phụ thuộc (S02, S05, J10, C13)."""

import asyncio
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

import pytest

from packages.core.error_codes import DEPENDENCY_UNAVAILABLE
from packages.core.errors import AppError
from packages.core.ids import new_id
from packages.messaging.redis import MAX_BLOCK_MS, AsyncRedis, streams_redis, streams_redis_sync, sync_result
from packages.messaging.settings import get_messaging_settings, reset_messaging_settings_cache
from packages.messaging.streams import (
    FIRST_ID,
    EventBus,
    SyncEventBus,
    _stream_entries,
    event_id_key,
    is_event_id,
    upload_stream,
    user_stream,
)
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.messaging import ephemeral_broker
from packages.testing.fixtures.services import ephemeral_redis, refused_url

DEDUPE_TTL_S = 60


@pytest.fixture
def stream(fake_clock: FakeClock) -> str:
    """Một stream upload riêng cho mỗi test, tên hợp lệ theo BE-00 §7."""
    return upload_stream(new_id("upl", fake_clock))


def test_user_stream_and_upload_stream_use_the_charter_names(fake_clock: FakeClock) -> None:
    user_id = new_id("usr", fake_clock)
    upload_id = new_id("upl", fake_clock)

    assert user_stream(user_id) == f"events:user:{user_id}"
    assert upload_stream(upload_id) == f"events:upload:{upload_id}"


@pytest.mark.parametrize("value", ["", "usr_", "upl_01ARZ3NDEKTSV4RRFFQ69G5FAV", "usr_khong-phai-ulid"])
def test_user_stream_rejects_ids_outside_the_pattern(value: str) -> None:
    with pytest.raises(ValueError, match="usr_"):
        user_stream(value)


def test_upload_stream_rejects_a_user_id(fake_clock: FakeClock) -> None:
    with pytest.raises(ValueError, match="upl_"):
        upload_stream(new_id("usr", fake_clock))


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0-0", True),
        ("1757000000000-12", True),
        ("", False),
        ("1757000000000", False),
        ("a-1", False),
        ("1-2-3", False),
    ],
)
def test_is_event_id(value: str, expected: bool) -> None:
    assert is_event_id(value) is expected


def test_stream_entries_accepts_the_resp2_list_form() -> None:
    """RESP2 thật: `xread` trả `list[(stream, entries)]` với `entries` cũng là list."""
    entries = [("1-0", {"d": "{}"})]
    assert _stream_entries([("events:x", entries)]) == entries


def test_stream_entries_rejects_the_resp3_dict_form() -> None:
    """Client này không đặt `protocol=3`, nên dạng `dict` của RESP3 là lỗi lập trình."""
    with pytest.raises(TypeError, match="XREAD kỳ vọng list"):
        _stream_entries({"events:x": [["1-0", {"d": "{}"}]]})


def test_stream_entries_rejects_entries_that_are_not_a_list() -> None:
    with pytest.raises(TypeError, match="XREAD kỳ vọng entries"):
        _stream_entries([("events:x", {"1-0": {"d": "{}"}})])


def test_event_id_key_orders_ids_by_milliseconds_then_sequence() -> None:
    """NO-157: `event_id_key` là hàm **công khai** — B4-01 nhập lại thay vì chép (R-07)."""
    assert event_id_key("5-2") == (5, 2)
    assert event_id_key("5-2") < event_id_key("5-10") < event_id_key("6-0")


async def test_streams_client_pins_the_legacy_list_form_of_xread(streams_client: AsyncRedis) -> None:
    """NO-151: dây là RESP3 từ redis-py 8.1; dạng list của `xread` chỉ còn nhờ `legacy_responses`.

    Ghim tường minh chứ không dựa mặc định: upstream ghi `legacy_responses=False` là đích
    di trú, và ngày nó đổi thì `_stream_entries` ném `TypeError` trên mọi luồng SSE.
    """
    assert streams_client.connection_pool.connection_kwargs["legacy_responses"] is True
    # `ConnectionPool.make_connection` chưa có kiểu trong stub redis-py 8 (`no-untyped-call`).
    pool: Any = streams_client.connection_pool
    assert pool.make_connection().protocol == 3


async def test_read_after_returns_new_events_in_order_without_repeats(event_bus: EventBus, stream: str) -> None:
    """S02: nối lại bằng id cuối đã nhận thì không thấy lại sự kiện cũ."""
    first = await event_bus.publish(stream, {"n": 1})
    second = await event_bus.publish(stream, {"n": 2})
    await event_bus.publish(stream, {"n": 3})

    from_start = await event_bus.read_after(stream, FIRST_ID)
    assert [event.data["n"] for event in from_start] == [1, 2, 3]
    assert [event.id for event in from_start][:2] == [first, second]

    assert [event.data["n"] for event in await event_bus.read_after(stream, second)] == [3]
    assert await event_bus.read_after(stream, from_start[-1].id) == []


async def test_read_after_honours_count(event_bus: EventBus, stream: str) -> None:
    for n in range(5):
        await event_bus.publish(stream, {"n": n})

    assert len(await event_bus.read_after(stream, FIRST_ID, count=2)) == 2


async def test_read_after_can_block_until_an_event_arrives(event_bus: EventBus, stream: str) -> None:
    reader = asyncio.create_task(event_bus.read_after(stream, FIRST_ID, block_ms=MAX_BLOCK_MS))
    await asyncio.sleep(0.05)
    await event_bus.publish(stream, {"n": 1})

    assert [event.data["n"] for event in await reader] == [1]


async def test_read_after_blocking_gives_up_and_returns_nothing(event_bus: EventBus, stream: str) -> None:
    assert await event_bus.read_after(stream, FIRST_ID, block_ms=50) == []


@pytest.mark.parametrize("last_id", ["", "khong-phai-id", "12"])
async def test_read_after_rejects_a_malformed_last_id(event_bus: EventBus, stream: str, last_id: str) -> None:
    with pytest.raises(ValueError, match="id sự kiện"):
        await event_bus.read_after(stream, last_id)


@pytest.mark.parametrize("block_ms", [-1, MAX_BLOCK_MS + 1])
async def test_read_after_rejects_a_block_longer_than_the_socket_budget(
    event_bus: EventBus, stream: str, block_ms: int
) -> None:
    with pytest.raises(ValueError, match="block_ms"):
        await event_bus.read_after(stream, FIRST_ID, block_ms=block_ms)


@pytest.mark.parametrize("data", [{"at": datetime.now(UTC)}, {"blob": b"x"}])
async def test_publish_rejects_raw_types_the_wire_has_no_form_for(
    event_bus: EventBus, stream: str, data: dict[str, object]
) -> None:
    """Người gọi phải đổi sang dạng dây trước; lỗi phải nổ ở nơi sinh dữ liệu."""
    with pytest.raises(TypeError, match=r"(?i)json serializable"):
        await event_bus.publish(stream, data)


async def test_publish_rejects_nan(event_bus: EventBus, stream: str) -> None:
    """`NaN` không phải JSON hợp lệ; để lọt thì người đọc nhận một giá trị không so được."""
    with pytest.raises(ValueError, match=r"(?i)json compliant"):
        await event_bus.publish(stream, {"n": float("nan")})


async def test_publish_once_adds_the_event_exactly_once(event_bus: EventBus, stream: str) -> None:
    """J10/K32: task được giao lại thì thông báo vẫn chỉ vào stream một lần."""
    first = await event_bus.publish_once(stream, "ntf-1", {"n": 1}, DEDUPE_TTL_S)
    again = await event_bus.publish_once(stream, "ntf-1", {"n": 2}, DEDUPE_TTL_S)

    assert again == first
    assert [event.data["n"] for event in await event_bus.read_after(stream, FIRST_ID)] == [1]


async def test_publish_once_publishes_again_after_the_key_expires(event_bus: EventBus, stream: str) -> None:
    await event_bus.publish_once(stream, "ntf-ttl", {"n": 1}, 1)
    await asyncio.sleep(1.1)
    second = await event_bus.publish_once(stream, "ntf-ttl", {"n": 2}, DEDUPE_TTL_S)

    events = await event_bus.read_after(stream, FIRST_ID)
    assert [event.data["n"] for event in events] == [1, 2]
    assert events[-1].id == second


async def test_publish_once_separates_different_keys(event_bus: EventBus, stream: str) -> None:
    await event_bus.publish_once(stream, "a", {"n": 1}, DEDUPE_TTL_S)
    await event_bus.publish_once(stream, "b", {"n": 2}, DEDUPE_TTL_S)

    assert len(await event_bus.read_after(stream, FIRST_ID)) == 2


@pytest.mark.parametrize(("dedupe_key", "ttl_s"), [("", DEDUPE_TTL_S), ("a", 0), ("a", -1)])
async def test_publish_once_rejects_an_empty_key_or_a_dead_ttl(
    event_bus: EventBus, stream: str, dedupe_key: str, ttl_s: int
) -> None:
    with pytest.raises(ValueError, match=r"dedupe_key|ttl_s"):
        await event_bus.publish_once(stream, dedupe_key, {"n": 1}, ttl_s)


async def test_tail_id_is_none_for_an_empty_stream(event_bus: EventBus, stream: str) -> None:
    assert await event_bus.tail_id(stream) is None

    last = await event_bus.publish(stream, {"n": 1})
    assert await event_bus.tail_id(stream) == last


async def test_is_trimmed_tells_a_lost_position_from_a_live_one(
    event_bus: EventBus, streams_client: AsyncRedis, stream: str
) -> None:
    first = await event_bus.publish(stream, {"n": 1})
    await event_bus.publish(stream, {"n": 2})
    last = await event_bus.publish(stream, {"n": 3})

    assert await event_bus.is_trimmed(stream, first) is False

    await streams_client.xtrim(stream, maxlen=1, approximate=False)
    assert await event_bus.is_trimmed(stream, first) is True
    assert await event_bus.is_trimmed(stream, last) is False


async def test_is_trimmed_is_true_for_an_empty_stream(event_bus: EventBus, stream: str) -> None:
    assert await event_bus.is_trimmed(stream, "1-0") is True


async def test_is_trimmed_rejects_a_malformed_id(event_bus: EventBus, stream: str) -> None:
    with pytest.raises(ValueError, match="id sự kiện"):
        await event_bus.is_trimmed(stream, "moi-mo")


async def test_publish_caps_the_stream_at_maxlen(streams_client: AsyncRedis, stream: str) -> None:
    """`MAXLEN ~` cắt theo nút, nên chỉ khẳng định "có cắt", không khẳng định số mục."""
    bus = EventBus(streams_client, maxlen=1)
    for n in range(300):
        await bus.publish(stream, {"n": n})

    assert await streams_client.xlen(stream) < 300


async def test_maxlen_defaults_to_the_configured_value(streams_client: AsyncRedis, stream: str) -> None:
    bus = EventBus(streams_client)
    await bus.publish(stream, {"n": 1})

    assert get_messaging_settings().stream_maxlen == 1000
    assert await streams_client.xlen(stream) == 1


async def test_expire_sets_a_deadline_on_the_whole_stream(
    event_bus: EventBus, streams_client: AsyncRedis, stream: str
) -> None:
    await event_bus.publish(stream, {"n": 1})
    await event_bus.expire(stream, 3600)

    assert 0 < await streams_client.ttl(stream) <= 3600


def test_sync_bus_writes_the_same_stream(messaging_env: None, stream: str) -> None:
    """Đường sau commit dùng bản đồng bộ; nó phải ghi vào đúng DB Streams của bản async."""
    client = streams_redis_sync()
    try:
        bus = SyncEventBus(client)
        first = bus.publish(stream, {"n": 1})
        once = bus.publish_once(stream, "sync-1", {"n": 2}, DEDUPE_TTL_S)

        assert bus.publish_once(stream, "sync-1", {"n": 3}, DEDUPE_TTL_S) == once
        assert [entry_id for entry_id, _ in sync_result(client.xrange(stream), list)] == [first, once]

        bus.expire(stream, 3600)
        assert 0 < sync_result(client.ttl(stream), int) <= 3600
    finally:
        client.flushdb()
        client.close()


async def test_a_dropped_reader_does_not_leak_a_redis_connection(
    event_bus: EventBus, streams_client: AsyncRedis, stream: str
) -> None:
    """S05: client rớt giữa lúc chặn thì kết nối phải được dọn."""
    before = len(await streams_client.client_list())
    reader = streams_redis()
    blocked = asyncio.create_task(EventBus(reader).read_after(stream, FIRST_ID, block_ms=MAX_BLOCK_MS))
    await asyncio.sleep(0.2)
    assert len(await streams_client.client_list()) == before + 1

    blocked.cancel()
    with suppress(asyncio.CancelledError):
        await blocked
    await reader.aclose()
    await asyncio.sleep(0.2)

    assert len(await streams_client.client_list()) == before


async def test_publish_reports_a_stopped_redis_as_dependency_unavailable(
    monkeypatch: pytest.MonkeyPatch, stream: str
) -> None:
    """C13: Redis đang có kết nối rồi tắt → 503, không phải 500."""
    container = ephemeral_redis("noeviction")
    url = f"redis://{container.get_container_host_ip()}:{container.get_exposed_port(6379)}/0"
    monkeypatch.setenv("REDIS_BROKER_URL", url)
    monkeypatch.setenv("REDIS_CACHE_URL", url)
    reset_messaging_settings_cache()
    client = streams_redis()
    stopped = False
    try:
        bus = EventBus(client)
        await bus.publish(stream, {"n": 1})
        container.stop()
        stopped = True
        with pytest.raises(AppError) as caught:
            await bus.publish(stream, {"n": 2})
    finally:
        if not stopped:
            container.stop()
        await client.aclose()
        reset_messaging_settings_cache()

    assert caught.value.code is DEPENDENCY_UNAVAILABLE
    assert caught.value.retry_after == 5


async def test_publish_to_a_closed_port_is_dependency_unavailable(monkeypatch: pytest.MonkeyPatch, stream: str) -> None:
    monkeypatch.setenv("REDIS_BROKER_URL", refused_url("redis"))
    monkeypatch.setenv("REDIS_CACHE_URL", refused_url("redis"))
    reset_messaging_settings_cache()
    client = streams_redis()
    try:
        with pytest.raises(AppError) as caught:
            await EventBus(client).publish(stream, {"n": 1})
    finally:
        await client.aclose()
        reset_messaging_settings_cache()

    assert caught.value.code is DEPENDENCY_UNAVAILABLE


async def test_publish_reports_a_full_noeviction_broker_as_dependency_unavailable(
    monkeypatch: pytest.MonkeyPatch, stream: str
) -> None:
    """Broker `noeviction` chạm `maxmemory` từ chối mọi lệnh ghi: đó là 503, không phải 500."""
    with ephemeral_broker(monkeypatch) as admin:
        admin.config_set("maxmemory", "1")
        client = streams_redis()
        try:
            with pytest.raises(AppError) as caught:
                await EventBus(client).publish(stream, {"n": 1})
        finally:
            await client.aclose()

    assert caught.value.code is DEPENDENCY_UNAVAILABLE
    assert caught.value.retry_after == 5
