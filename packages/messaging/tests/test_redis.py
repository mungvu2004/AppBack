"""Client Redis: chọn đúng DB, đặt đúng trần, và dịch đúng lỗi phụ thuộc."""

import os
from collections.abc import Callable

import pytest
import redis
from redis.backoff import AbstractBackoff
from redis.exceptions import ClusterDownError, OutOfMemoryError, ReadOnlyError, ResponseError
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError
from redis.retry import Retry

from packages.core.error_codes import DEPENDENCY_UNAVAILABLE
from packages.core.errors import AppError
from packages.messaging.redis import (
    ASYNC_RETRIES,
    BROKER_DB,
    CACHE_DB,
    CONNECT_TIMEOUT_S,
    DEPENDENCY_ERRORS,
    SAFE_DB,
    STREAM_DB,
    STREAM_READ_TIMEOUT_S,
    STREAM_RETRIES,
    SYNC_RETRIES,
    SYNC_TIMEOUT_S,
    AsyncRedis,
    ProcessLocal,
    SyncRedis,
    assert_broker_policy,
    broker_redis,
    broker_redis_sync,
    cache_redis,
    cache_redis_sync,
    redis_errors,
    safe_redis,
    safe_redis_sync,
    streams_redis,
    streams_redis_sync,
    translate_redis_error,
    with_db,
)
from packages.messaging.settings import MessagingSettings
from packages.testing.fixtures.messaging import ephemeral_broker


@pytest.mark.parametrize(
    ("url", "db", "expected"),
    [
        ("redis://host:6379/0", 2, "redis://host:6379/2"),
        ("redis://host:6379", 1, "redis://host:6379/1"),
        ("rediss://user:pw@host:6379/9?ssl_cert_reqs=none", 1, "rediss://user:pw@host:6379/1?ssl_cert_reqs=none"),
    ],
)
def test_with_db_replaces_only_the_database_number(url: str, db: int, expected: str) -> None:
    assert with_db(url, db) == expected


def conf() -> MessagingSettings:
    return MessagingSettings(redis_broker_url="redis://broker:6379/0", redis_cache_url="redis://cache:6379/0")


@pytest.mark.parametrize(
    ("factory", "host", "db"),
    [
        (broker_redis, "broker", BROKER_DB),
        (streams_redis, "broker", STREAM_DB),
        (safe_redis, "broker", SAFE_DB),
        (cache_redis, "cache", CACHE_DB),
    ],
)
def test_async_clients_pick_their_own_instance_and_database(
    factory: Callable[[MessagingSettings], AsyncRedis], host: str, db: int
) -> None:
    kwargs = factory(conf()).connection_pool.connection_kwargs

    assert (kwargs["host"], kwargs["db"]) == (host, db)
    assert kwargs["socket_connect_timeout"] == CONNECT_TIMEOUT_S


def test_stream_client_reads_longer_than_it_blocks() -> None:
    """Trần đọc phải vượt trần chặn của `XREAD`, không thì đọc dài luôn timeout."""
    assert streams_redis(conf()).connection_pool.connection_kwargs["socket_timeout"] == STREAM_READ_TIMEOUT_S


@pytest.mark.parametrize(
    ("factory", "host", "db"),
    [
        (streams_redis_sync, "broker", STREAM_DB),
        (safe_redis_sync, "broker", SAFE_DB),
        (cache_redis_sync, "cache", CACHE_DB),
    ],
)
def test_sync_clients_use_the_half_second_budget(
    factory: Callable[[MessagingSettings], SyncRedis], host: str, db: int
) -> None:
    kwargs = factory(conf()).connection_pool.connection_kwargs

    assert (kwargs["host"], kwargs["db"]) == (host, db)
    assert kwargs["socket_timeout"] == SYNC_TIMEOUT_S
    assert kwargs["socket_connect_timeout"] == SYNC_TIMEOUT_S


@pytest.mark.parametrize(
    ("factory", "retries"),
    [
        (broker_redis, ASYNC_RETRIES),
        (streams_redis, STREAM_RETRIES),
        (safe_redis, ASYNC_RETRIES),
        (cache_redis, ASYNC_RETRIES),
        (broker_redis_sync, SYNC_RETRIES),
        (streams_redis_sync, SYNC_RETRIES),
        (safe_redis_sync, SYNC_RETRIES),
        (cache_redis_sync, SYNC_RETRIES),
    ],
)
def test_every_client_pins_the_retry_budget_of_its_role(
    factory: Callable[[MessagingSettings], AsyncRedis | SyncRedis], retries: int
) -> None:
    """NO-152: số lượt thử lại khai tường minh theo vai, không mượn mặc định của thư viện.

    Mặc định đổi theo từng bản `redis-py` (bump 6.4 → 8.1 đổi cả số lượt lẫn backoff), nên
    trần thời gian của một vai chỉ có nghĩa khi chính ta đặt số lượt (R-24).
    """
    retry = factory(conf()).connection_pool.connection_kwargs["retry"]

    assert retry.get_retries() == retries


class _CountingBackoff(AbstractBackoff):
    """Backoff không chờ, đếm mỗi lượt lùi — `Retry` gọi nó đúng một lần mỗi lượt thử lại."""

    def __init__(self) -> None:
        """Chưa có lượt thử lại nào."""
        self.calls = 0

    def reset(self) -> None:
        """Không giữ trạng thái giữa hai lượt gọi."""

    def compute(self, failures: int) -> float:
        """Đếm lượt rồi trả 0 giây: test đo **số lượt**, không đo thời gian chờ."""
        self.calls += 1
        return 0.0


def test_a_dead_redis_costs_exactly_the_configured_number_of_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Redis **thật** bị giết giữa chừng: client bỏ cuộc sau đúng `SYNC_RETRIES` lượt lại (NO-152).

    Giữ nguyên số lượt đã cấu hình, chỉ thay backoff bằng bản đếm: thứ đo được là ngân sách
    thật của vai, không phải một con số test tự đặt.
    """
    with ephemeral_broker(monkeypatch) as admin:
        client = safe_redis_sync()
        backoff = _CountingBackoff()
        try:
            client.ping()
            configured = client.get_retry()
            assert configured is not None
            client.set_retry(Retry(backoff, configured.get_retries()))
            admin.shutdown(nosave=True)
            with pytest.raises(RedisConnectionError):
                client.ping()
        finally:
            client.close()

    assert backoff.calls == SYNC_RETRIES


def test_cache_clients_refuse_a_process_without_the_cache_instance() -> None:
    """NO-085: `ml` không tới được `redis-cache`, nên `REDIS_CACHE_URL` là tuỳ chọn.

    Tiến trình nào thật sự cần cache mà thiếu biến phải hỏng **ở chỗ gọi**, với tên biến
    trong thông báo — chứ không hỏng lúc nạp cấu hình của mọi tiến trình (fail-closed, R-17).
    """
    without_cache = MessagingSettings(redis_broker_url="redis://broker:6379/0", redis_cache_url=None)

    with pytest.raises(RuntimeError, match="REDIS_CACHE_URL"):
        cache_redis(without_cache)
    with pytest.raises(RuntimeError, match="REDIS_CACHE_URL"):
        cache_redis_sync(without_cache)


def counting_local() -> ProcessLocal[int]:
    """`ProcessLocal` trả 1, 2, 3… — số lần dựng lại đếm được ngay trong assert."""
    calls: list[int] = []

    def factory() -> int:
        calls.append(1)
        return len(calls)

    return ProcessLocal[int](factory)


def test_process_local_builds_once_per_process(monkeypatch: pytest.MonkeyPatch) -> None:
    local = counting_local()

    assert local.get() == 1
    assert local.get() == 1

    monkeypatch.setattr(os, "getpid", lambda: 999_999)
    assert local.get() == 2


def test_process_local_reset_forgets_the_value() -> None:
    local = counting_local()

    assert local.get() == 1
    assert local.reset() == 1
    assert local.get() == 2


def test_process_local_reset_never_hands_back_a_resource_of_the_parent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tài nguyên dựng trước `fork` là của tiến trình cha: `reset` quên nó nhưng không trả để đóng (NO-024)."""
    local = counting_local()
    assert local.get() == 1

    monkeypatch.setattr(os, "getpid", lambda: 999_999)
    assert local.reset() is None
    assert local.reset() is None


@pytest.mark.parametrize(
    "exc",
    [
        RedisConnectionError("nối hỏng"),
        RedisTimeoutError("quá hạn"),
        OutOfMemoryError("OOM command not allowed"),
        ReadOnlyError("READONLY You can't write against a read only replica"),
    ],
)
def test_server_failures_become_dependency_unavailable(exc: Exception) -> None:
    """`OutOfMemoryError` và `ReadOnlyError` là `ResponseError` nhưng vẫn là phụ thuộc hỏng.

    Xếp chúng vào lỗi người gọi là mất việc: task bị đánh `INTERNAL` rồi ack thay vì
    thử lại (BE-00 §7)."""
    error = translate_redis_error(exc)

    assert error is not None
    assert error.code is DEPENDENCY_UNAVAILABLE
    assert error.retry_after == 5


def test_cluster_down_stays_in_the_dependency_list() -> None:
    """Chốt bằng danh sách, không dựng thể hiện: `redis-py` khai `ClusterDownError.__init__`
    không kiểu, và lớp này chỉ xảy ra với client cluster (v1 chạy Redis đơn lẻ, BE-00 §1).
    Kiểm kiểu này giữ nó khỏi rơi ra khỏi phân loại khi ai đó dọn danh sách."""
    assert ClusterDownError in DEPENDENCY_ERRORS


def test_command_errors_are_not_dependency_failures() -> None:
    assert translate_redis_error(ResponseError("WRONGTYPE")) is None


def test_redis_errors_passes_through_when_nothing_fails() -> None:
    with redis_errors():
        value = 1

    assert value == 1


def test_redis_errors_wraps_connection_failures() -> None:
    with pytest.raises(AppError) as caught, redis_errors():
        raise RedisConnectionError("nối hỏng")

    assert caught.value.code is DEPENDENCY_UNAVAILABLE


def test_redis_errors_reraises_other_failures() -> None:
    with pytest.raises(ResponseError), redis_errors():
        raise ResponseError("WRONGTYPE")


def test_broker_policy_is_accepted_when_noeviction(redis_broker_url: str) -> None:
    client = redis.Redis.from_url(redis_broker_url, decode_responses=True)
    try:
        assert_broker_policy(client)
    finally:
        client.close()


def test_broker_policy_rejects_an_evicting_instance(redis_cache_url: str) -> None:
    """`redis-cache` chạy `allkeys-lru`: dùng nó làm broker là chấp nhận mất thông điệp."""
    client = redis.Redis.from_url(redis_cache_url, decode_responses=True)
    try:
        with pytest.raises(RuntimeError, match="noeviction"):
            assert_broker_policy(client)
    finally:
        client.close()
