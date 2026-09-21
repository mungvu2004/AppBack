"""Client Redis theo vai (BE-00 §1, §7).

Một instance `redis-broker` mang ba DB tách nhau — broker Celery (0), Streams sự
kiện (1), trạng thái an toàn như khoá đăng nhập và khoá GPU (2) — và instance
`redis-cache` mang cache/rate-limit (0). Tách bằng số hiệu DB chứ không bằng tiền
tố khoá để `FLUSHDB` của một vai không xoá vai khác.

Mọi client đặt **trần kết nối và trần đọc tường minh** (R-24): mặc định của
`redis-py` là chờ vô hạn, đủ để một Redis treo giữ luôn worker hay tiến trình API.
Bản đồng bộ dùng trần 0,5 s vì nó chạy trong callback sau commit, ngay trên đường
trả response.
"""

import os
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, Final
from urllib.parse import urlsplit, urlunsplit

import redis
import redis.asyncio
from redis.exceptions import ClusterDownError, OutOfMemoryError, ReadOnlyError
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from packages.core.error_codes import DEPENDENCY_UNAVAILABLE
from packages.core.errors import AppError
from packages.messaging.settings import MessagingSettings, get_messaging_settings

BROKER_DB: Final = 0
STREAM_DB: Final = 1
SAFE_DB: Final = 2
CACHE_DB: Final = 0

CONNECT_TIMEOUT_S: Final = 2.0
READ_TIMEOUT_S: Final = 5.0
# `XREAD BLOCK` giữ socket đúng bằng thời gian chặn, nên client Streams cần trần đọc
# lớn hơn trần chặn; `EventBus.read_after` từ chối block_ms vượt MAX_BLOCK_MS.
STREAM_READ_TIMEOUT_S: Final = 30.0
MAX_BLOCK_MS: Final = 25_000
SYNC_TIMEOUT_S: Final = 0.5

BROKER_POLICY: Final = "noeviction"
DEPENDENCY_RETRY_AFTER: Final = 5

# Lỗi "Redis không phục vụ được", tách khỏi lỗi "người gọi sai lệnh".
# `OutOfMemoryError` và `ReadOnlyError` kế thừa `ResponseError` nên **trông** như lỗi
# lệnh, nhưng chúng là trạng thái của máy chủ: broker `noeviction` chạm `maxmemory` từ
# chối mọi lệnh ghi, và replica từ chối ghi khi đang chuyển vai. Xếp nhầm chúng vào
# lỗi người gọi là biến mất việc: task bị đánh `INTERNAL` rồi ack thay vì thử lại.
DEPENDENCY_ERRORS: Final = (
    RedisConnectionError,  # gồm cả BusyLoadingError
    RedisTimeoutError,
    OutOfMemoryError,
    ReadOnlyError,
    ClusterDownError,
)

type AsyncRedis = redis.asyncio.Redis
type SyncRedis = redis.Redis


class ProcessLocal[ResourceT]:
    """Giữ một tài nguyên nặng (socket, app Celery) dùng lại trong cùng tiến trình.

    Kết nối mở trước `fork` không dùng được ở tiến trình con (hai bên cùng đọc một
    socket), nên tài nguyên được dựng lại khi PID đổi. Có khoá vì uvicorn và Celery
    đều gọi từ nhiều luồng.
    """

    def __init__(self, factory: Callable[[], ResourceT]) -> None:
        self._factory = factory
        self._lock = threading.Lock()
        self._value: ResourceT | None = None
        self._pid: int | None = None

    def get(self) -> ResourceT:
        """Tài nguyên của tiến trình hiện tại, dựng lười ở lần gọi đầu."""
        pid = os.getpid()
        with self._lock:
            if self._value is None or self._pid != pid:
                self._value, self._pid = self._factory(), pid
            return self._value

    def reset(self) -> ResourceT | None:
        """Quên tài nguyên đang giữ, lần sau dựng lại; trả nó để người gọi đóng nếu cần.

        Tài nguyên dựng trước `fork` (PID khác) bị quên nhưng **không** trả: đóng nó ở
        tiến trình con là đụng vào socket/vòng sự kiện của tiến trình cha.
        """
        with self._lock:
            value = self._value if self._pid == os.getpid() else None
            self._value, self._pid = None, None
            return value


def with_db(url: str, db: int) -> str:
    """Đổi số hiệu DB trong URL Redis; giữ nguyên scheme, thông tin đăng nhập và query."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{db}", parts.query, parts.fragment))


def sync_result[ResultT](result: Any, kind: Callable[[Any], ResultT]) -> ResultT:
    """Kết quả của một lệnh Redis **đồng bộ**, chốt về kiểu thật.

    `redis-py` khai kiểu trả của mọi lệnh là `Awaitable | Any` vì một lớp lệnh dùng
    chung cho cả bản sync và bản async; mã đồng bộ phải tự nói mình chờ kiểu gì.
    """
    return kind(result)


def _async_client(url: str, db: int, read_timeout_s: float) -> AsyncRedis:
    client: AsyncRedis = redis.asyncio.Redis.from_url(
        with_db(url, db),
        decode_responses=True,
        socket_connect_timeout=CONNECT_TIMEOUT_S,
        socket_timeout=read_timeout_s,
    )
    return client


def _sync_client(url: str, db: int) -> SyncRedis:
    return redis.Redis.from_url(
        with_db(url, db),
        decode_responses=True,
        socket_connect_timeout=SYNC_TIMEOUT_S,
        socket_timeout=SYNC_TIMEOUT_S,
    )


def broker_redis(settings: MessagingSettings | None = None) -> AsyncRedis:
    """Client tới DB broker — chỉ để quan sát hàng đợi; Celery tự mở kết nối của nó."""
    return _async_client((settings or get_messaging_settings()).redis_broker_url, BROKER_DB, READ_TIMEOUT_S)


def streams_redis(settings: MessagingSettings | None = None) -> AsyncRedis:
    return _async_client((settings or get_messaging_settings()).redis_broker_url, STREAM_DB, STREAM_READ_TIMEOUT_S)


def safe_redis(settings: MessagingSettings | None = None) -> AsyncRedis:
    return _async_client((settings or get_messaging_settings()).redis_broker_url, SAFE_DB, READ_TIMEOUT_S)


def cache_redis(settings: MessagingSettings | None = None) -> AsyncRedis:
    return _async_client((settings or get_messaging_settings()).redis_cache_url, CACHE_DB, READ_TIMEOUT_S)


def broker_redis_sync(settings: MessagingSettings | None = None) -> SyncRedis:
    return _sync_client((settings or get_messaging_settings()).redis_broker_url, BROKER_DB)


def streams_redis_sync(settings: MessagingSettings | None = None) -> SyncRedis:
    return _sync_client((settings or get_messaging_settings()).redis_broker_url, STREAM_DB)


def safe_redis_sync(settings: MessagingSettings | None = None) -> SyncRedis:
    return _sync_client((settings or get_messaging_settings()).redis_broker_url, SAFE_DB)


def cache_redis_sync(settings: MessagingSettings | None = None) -> SyncRedis:
    return _sync_client((settings or get_messaging_settings()).redis_cache_url, CACHE_DB)


def assert_broker_policy(client: SyncRedis) -> None:
    """Hỏng nếu instance broker được phép đuổi khoá: `allkeys-lru` ở đây là mất việc.

    Gọi lúc khởi động worker (`worker_init`) và API. Dùng client đồng bộ để chạy
    được trong tín hiệu Celery, nơi chưa có vòng sự kiện nào.
    """
    policy = sync_result(client.config_get("maxmemory-policy"), dict).get("maxmemory-policy")
    if policy != BROKER_POLICY:
        raise RuntimeError(f"redis-broker phải chạy maxmemory-policy={BROKER_POLICY}, đang là {policy!r}")


def translate_redis_error(exc: BaseException) -> AppError | None:
    """Lỗi kết nối/timeout của Redis → 503 `DEPENDENCY_UNAVAILABLE`; lỗi khác trả `None`.

    Lỗi lệnh (sai kiểu khoá, script Lua hỏng) là lỗi của người gọi, phải nổi lên
    nguyên trạng chứ không hoá thành 503 (R-16). Danh sách ở `DEPENDENCY_ERRORS`.
    """
    if isinstance(exc, DEPENDENCY_ERRORS):
        return DEPENDENCY_UNAVAILABLE.error(retry_after=DEPENDENCY_RETRY_AFTER)
    return None


@contextmanager
def redis_errors() -> Iterator[None]:
    """Bọc một lời gọi Redis: lỗi phụ thuộc thành `AppError` 503, lỗi khác giữ nguyên."""
    try:
        yield
    except Exception as exc:
        app_error = translate_redis_error(exc)
        if app_error is None:
            raise
        raise app_error from exc
