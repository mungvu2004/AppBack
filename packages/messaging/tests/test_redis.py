"""Client Redis: chọn đúng DB, đặt đúng trần, và dịch đúng lỗi phụ thuộc."""

import os
import subprocess
import sys
from collections.abc import Callable
from typing import Final

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
    sync_result,
    translate_redis_error,
    with_db,
)
from packages.messaging.settings import MessagingSettings
from packages.testing.fixtures.messaging import ephemeral_broker
from packages.testing.fixtures.services import ephemeral_redis


@pytest.mark.parametrize(
    ("url", "db", "expected"),
    [
        ("redis://host:6379/0", 2, "redis://host:6379/2"),
        ("redis://host:6379", 1, "redis://host:6379/1"),
        ("redis://host:6379/", 2, "redis://host:6379/2"),
        ("rediss://user:pw@host:6379/9?ssl_cert_reqs=none", 1, "rediss://user:pw@host:6379/10?ssl_cert_reqs=none"),
    ],
)
def test_with_db_offsets_the_url_database_by_the_role(url: str, db: int, expected: str) -> None:
    """Số vai cộng lên DB gốc của URL (vắng = 0); scheme, đăng nhập, query giữ nguyên (NO-270)."""
    assert with_db(url, db) == expected


def conf() -> MessagingSettings:
    """Cấu hình hai instance giả `broker`/`cache` ở DB 0 — chỉ để soi tham số client, không nối."""
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
    """Mỗi client async trỏ đúng instance và đúng DB vai, với trần nối tường minh."""
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
    """Client đồng bộ trỏ đúng instance/DB và dùng trần 0,5 s cho cả nối lẫn đọc."""
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
        """Ghi một lần gọi, trả số lần đã gọi — mỗi lần dựng cho một giá trị mới."""
        calls.append(1)
        return len(calls)

    return ProcessLocal[int](factory)


def test_process_local_builds_once_per_process(monkeypatch: pytest.MonkeyPatch) -> None:
    """`ProcessLocal` dựng tài nguyên một lần rồi trả lại đúng bản đó trong cùng tiến trình."""
    local = counting_local()

    assert local.get() == 1
    assert local.get() == 1

    monkeypatch.setattr(os, "getpid", lambda: 999_999)
    assert local.get() == 2


def test_process_local_reset_forgets_the_value() -> None:
    """`reset()` trả tài nguyên đang giữ và lần `get()` sau dựng bản mới."""
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
    """Lỗi lệnh (`ResponseError`) là lỗi người gọi, không thành 503."""
    assert translate_redis_error(ResponseError("WRONGTYPE")) is None


def test_redis_errors_passes_through_when_nothing_fails() -> None:
    """Không lỗi thì `redis_errors()` không đổi gì."""
    with redis_errors():
        value = 1

    assert value == 1


def test_redis_errors_wraps_connection_failures() -> None:
    """Lỗi kết nối Redis → `AppError` `DEPENDENCY_UNAVAILABLE`."""
    with pytest.raises(AppError) as caught, redis_errors():
        raise RedisConnectionError("nối hỏng")

    assert caught.value.code is DEPENDENCY_UNAVAILABLE


def test_redis_errors_reraises_other_failures() -> None:
    """Lỗi không phải lỗi phụ thuộc nổi lên nguyên trạng."""
    with pytest.raises(ResponseError), redis_errors():
        raise ResponseError("WRONGTYPE")


def test_broker_policy_is_accepted_when_noeviction(redis_broker_url: str) -> None:
    """Instance broker `noeviction` qua được kiểm chính sách lúc khởi động."""
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


def test_with_db__two_processes_on_one_redis_keep_their_own_roles() -> None:
    """NO-270: hai tiến trình chung **một** Redis, URL khác số DB gốc, không `FLUSHDB` lên nhau.

    Đây là điều kiện để mọi tiến trình `pytest -n` dùng chung một container Redis (như Postgres/MinIO):
    vai (`STREAM_DB`…) phải là độ lệch **trên** số DB của URL, không phải số DB tuyệt đối. Tiến trình
    thứ hai là tiến trình Python thật, chỉ biết `REDIS_BROKER_URL` của nó.
    """
    container = ephemeral_redis("noeviction")
    try:
        base = f"redis://{container.get_container_host_ip()}:{container.get_exposed_port(6379)}"
        mine = streams_redis_sync(MessagingSettings(redis_broker_url=f"{base}/0"))
        try:
            mine.set("NO-270", "của tiến trình 0")
            other = "from packages.messaging.redis import streams_redis_sync; streams_redis_sync().flushdb()"
            env = os.environ | {"REDIS_BROKER_URL": f"{base}/{SAFE_DB + 1}"}
            subprocess.run(  # noqa: S603 — trình thông dịch của chính tiến trình test, mã cố định
                [sys.executable, "-c", other], env=env, check=True, timeout=60
            )

            assert mine.get("NO-270") == "của tiến trình 0"
        finally:
            mine.close()
    finally:
        container.stop()


PAUSE_MS: Final = 10_000
"""Trần của `CLIENT PAUSE`: dài hơn mọi lượt thử lại, test tự `UNPAUSE` ở `finally` nên không phải chờ."""


def _connections_received(admin: SyncRedis) -> int:
    """Số kết nối máy chủ đã nhận — mỗi lượt thử lại của redis-py mở lại kết nối đúng một lần."""
    return int(sync_result(admin.info("stats"), dict)["total_connections_received"])


def test_streams_redis_sync__a_timed_out_write_is_not_sent_again(monkeypatch: pytest.MonkeyPatch) -> None:
    """NO-187: `XADD` hết giờ đọc có thể đã chạy ở máy chủ — thử lại là sự kiện trùng, nên không thử lại.

    Redis **thật** bị `CLIENT PAUSE WRITE`: lệnh ghi treo ở máy chủ quá trần đọc 0,5 s, còn lệnh
    bắt tay của kết nối mới vẫn chạy — đúng cảnh một lượt thử lại gửi được `XADD` lần hai.
    """
    with ephemeral_broker(monkeypatch) as admin:
        client = streams_redis_sync()
        try:
            client.ping()
            before = _connections_received(admin)
            admin.client_pause(PAUSE_MS, all=False)
            try:
                with pytest.raises(RedisTimeoutError):
                    client.xadd("s:no-187", {"k": "v"})
                reconnects = _connections_received(admin) - before
            finally:
                admin.client_unpause()
        finally:
            client.close()

    assert reconnects == 0


@pytest.mark.parametrize("factory", [streams_redis, streams_redis_sync])
def test_streams_clients__retry_only_connection_failures(
    factory: Callable[[MessagingSettings], AsyncRedis | SyncRedis],
) -> None:
    """NO-187: vai Streams (đường `XADD`) chỉ thử lại lỗi kết nối, không thử lại hết giờ đọc."""
    kwargs = factory(conf()).connection_pool.connection_kwargs

    assert kwargs["retry_on_error"] == [RedisConnectionError, TimeoutError]
    assert not issubclass(RedisTimeoutError, TimeoutError), "hết giờ đọc không được lọt vào danh sách thử lại"
    assert kwargs["retry"].get_retries() == (STREAM_RETRIES if factory is streams_redis else SYNC_RETRIES)
