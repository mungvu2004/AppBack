"""Client Redis theo vai (BE-00 §1, §7).

Một instance `redis-broker` mang ba DB tách nhau — broker Celery (0), Streams sự
kiện (1), trạng thái an toàn như khoá đăng nhập và khoá GPU (2) — và instance
`redis-cache` mang cache/rate-limit (0). Tách bằng số hiệu DB chứ không bằng tiền
tố khoá để `FLUSHDB` của một vai không xoá vai khác. Số vai là độ lệch trên DB gốc
của URL (`with_db`), URL `/0` thì trùng số tuyệt đối ở trên.

Mọi client đặt **trần kết nối, trần đọc và ngân sách thử lại tường minh** (R-24): mặc
định của `redis-py` là chờ vô hạn, đủ để một Redis treo giữ luôn worker hay tiến trình
API, còn số lượt thử lại mặc định đổi theo từng bản thư viện (NO-152). Bản đồng bộ dùng
trần 0,5 s vì nó chạy trong callback sau commit, ngay trên đường trả response.
"""

import os
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, Final
from urllib.parse import urlsplit, urlunsplit

import redis
import redis.asyncio
from redis.backoff import ExponentialBackoff
from redis.exceptions import ClusterDownError, OutOfMemoryError, ReadOnlyError
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError
from redis.retry import Retry

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

# Ngân sách thử lại khai **tường minh** theo vai (R-24, NO-152). Mặc định của `redis-py`
# đổi theo từng bản (8.1 dựng `Retry(NoBackoff(), 0)` cho client không khai `retry`, còn
# một bản trước đó thử tới 10 lượt), nên trần thời gian của một vai chỉ có nghĩa khi chính
# ta đặt số lượt. Chỉ thử lại lỗi **kết nối/timeout**: lỗi lệnh và `OutOfMemoryError` thử
# lại chỉ tốn thêm trần thời gian mà kết quả không đổi.
RETRY_BASE_S: Final = 0.05
RETRY_CAP_S: Final = 0.2
ASYNC_RETRIES: Final = 2
"""Hai lượt lại cho vai có trần đọc 5 s — chờ thêm tối đa ~0,25 s, vẫn xa trần."""
STREAM_RETRIES: Final = 1
"""Một lượt: `XREAD BLOCK` hỏng chỉ đóng một luồng SSE, và FE tự nối lại (S05)."""
SYNC_RETRIES: Final = 1
"""Một lượt: đường đồng bộ nằm ngay trên đường trả response, trần cả thảy 0,5 s."""
RETRYABLE_ERRORS: Final = (RedisConnectionError, RedisTimeoutError)
WRITE_RETRYABLE_ERRORS: Final = (RedisConnectionError, TimeoutError)
"""Vai Streams (client của `XADD` trong `EventBus.publish`): hết giờ **đọc** không thử lại (NO-187).

Lệnh hết giờ đọc có thể đã chạy ở máy chủ, và `XADD` không idempotent — lượt lại ghi thêm một mục
id mới, FE thấy sự kiện hai lần. `TimeoutError` dựng sẵn là hết giờ **nối** (`socket.timeout` thô trong
`connect_check_health`, chưa gửi gì) nên vẫn thử lại; hết giờ đọc là `redis.exceptions.TimeoutError`, không
kế thừa nó. Còn `ConnectionError` khi đọc phản hồi (máy chủ đóng socket sau khi đã chạy) vẫn thử lại:
redis-py không tách pha gửi/đọc, nên đây là **giảm** chứ không hết trùng. Các lượt đọc qua vai này
(quét hết hạn, `XREVRANGE` của `pipeline_quality`) mất lượt thử lại khi hết giờ đọc — đều tự chịu được lỗi;
đọc SSE đi pool riêng (`apps/api/streams/router.py`).
"""

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
        """Ghi nhớ `factory`; tài nguyên chưa dựng tới lần `get()` đầu."""
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

    @contextmanager
    def override(self, factory: Callable[[], ResourceT]) -> Iterator[None]:
        """Chỉ cho test: thay `factory` trong khối `with`, trả lại bản cũ khi thoát (kể cả khi thân ném).

        Tài nguyên đang giữ bị quên ở cả hai đầu khối, nên bản dựng bằng factory thay thế không
        sống sót sang test sau và bản dựng trước đó không lọt vào khối.
        """
        with self._lock:
            previous = self._factory
            self._factory, self._value, self._pid = factory, None, None
        try:
            yield
        finally:
            with self._lock:
                self._factory, self._value, self._pid = previous, None, None


def with_db(url: str, db: int) -> str:
    """URL tới DB của vai `db`: số DB **gốc** trong URL (vắng = 0) cộng độ lệch vai; giữ scheme, đăng nhập, query.

    URL triển khai luôn là `/0` (`deploy/compose/env.example`), nên kết quả vẫn đúng số vai như trước.
    URL `/<n>` dời cả khối vai lên `n`: Celery (dùng `REDIS_BROKER_URL` nguyên trạng, `celery_app.py`) và
    `broker_redis()` cùng thấy một DB, và nhiều tiến trình test chung một Redis, mỗi tiến trình một khối DB,
    không `FLUSHDB` lên nhau (NO-270).
    """
    parts = urlsplit(url)
    base = int(parts.path.strip("/") or 0)
    return urlunsplit((parts.scheme, parts.netloc, f"/{base + db}", parts.query, parts.fragment))


def sync_result[ResultT](result: Any, kind: Callable[[Any], ResultT]) -> ResultT:
    """Kết quả của một lệnh Redis **đồng bộ**, chốt về kiểu thật.

    `redis-py` khai kiểu trả của mọi lệnh là `Awaitable | Any` vì một lớp lệnh dùng
    chung cho cả bản sync và bản async; mã đồng bộ phải tự nói mình chờ kiểu gì.
    """
    return kind(result)


def _retry(retries: int, errors: tuple[type[Exception], ...]) -> Retry:
    """Chính sách thử lại của một vai: backoff nhân đôi từ `RETRY_BASE_S`, trần `RETRY_CAP_S`, chỉ cho `errors`.

    `errors` phải truyền tường minh: mặc định `supported_errors` của `Retry` (redis-py 8.1) đã gồm
    cả `TimeoutError`, và `retry_on_error` chỉ **thêm** vào danh sách đó chứ không thay.
    """
    return Retry(ExponentialBackoff(base=RETRY_BASE_S, cap=RETRY_CAP_S), retries, supported_errors=errors)


# Ghim `legacy_responses=True` (NO-151): redis-py 8.1 nói RESP3 trên dây dù ta không đặt
# `protocol=3`, và dạng list của `xread` mà `packages.messaging.streams` đọc chỉ còn nhờ cờ
# này. Upstream ghi `legacy_responses=False` là đích di trú, nên dựa mặc định là để một
# lượt bump thư viện đổi hình dạng dữ liệu của mọi luồng SSE mà không ai thấy.
def _async_client(
    url: str, db: int, read_timeout_s: float, retries: int, errors: tuple[type[Exception], ...] = RETRYABLE_ERRORS
) -> AsyncRedis:
    """Client async của một vai: DB `db` trên URL, trần đọc, ngân sách và loại lỗi thử lại của vai."""
    client: AsyncRedis = redis.asyncio.Redis.from_url(
        with_db(url, db),
        socket_connect_timeout=CONNECT_TIMEOUT_S,
        socket_timeout=read_timeout_s,
        retry=_retry(retries, errors),
        retry_on_error=list(errors),
        decode_responses=True,
        legacy_responses=True,
    )
    return client


def _sync_client(url: str, db: int, errors: tuple[type[Exception], ...] = RETRYABLE_ERRORS) -> SyncRedis:
    """Client đồng bộ của một vai: DB `db` trên URL, trần 0,5 s cho cả nối lẫn đọc, thử lại chỉ cho `errors`."""
    return redis.Redis.from_url(
        with_db(url, db),
        socket_connect_timeout=SYNC_TIMEOUT_S,
        socket_timeout=SYNC_TIMEOUT_S,
        retry=_retry(SYNC_RETRIES, errors),
        retry_on_error=list(errors),
        decode_responses=True,
        legacy_responses=True,
    )


def _cache_url(settings: MessagingSettings) -> str:
    """DSN `redis-cache`, hay `RuntimeError` nếu tiến trình này không được cấu hình cho nó.

    `REDIS_CACHE_URL` tuỳ chọn để worker `ml` nạp được cấu hình (NO-085); tiến trình nào
    thật sự chạm cache mà thiếu biến phải hỏng ngay ở đây, với tên biến trong thông báo.
    """
    url = settings.redis_cache_url
    if url is None:
        raise RuntimeError("REDIS_CACHE_URL chưa đặt: tiến trình này không được cấu hình để dùng redis-cache")
    return url


def broker_redis(settings: MessagingSettings | None = None) -> AsyncRedis:
    """Client tới DB broker — chỉ để quan sát hàng đợi; Celery tự mở kết nối của nó."""
    return _async_client(
        (settings or get_messaging_settings()).redis_broker_url, BROKER_DB, READ_TIMEOUT_S, ASYNC_RETRIES
    )


def streams_redis(settings: MessagingSettings | None = None) -> AsyncRedis:
    """Client async tới DB Streams sự kiện; trần đọc dài hơn trần chặn `XREAD`; hết giờ không thử lại (NO-187)."""
    return _async_client(
        (settings or get_messaging_settings()).redis_broker_url,
        STREAM_DB,
        STREAM_READ_TIMEOUT_S,
        STREAM_RETRIES,
        WRITE_RETRYABLE_ERRORS,
    )


def safe_redis(settings: MessagingSettings | None = None) -> AsyncRedis:
    """Client async tới DB an toàn (khoá đăng nhập, khoá GPU, hạn mức `store="safe"`)."""
    return _async_client(
        (settings or get_messaging_settings()).redis_broker_url, SAFE_DB, READ_TIMEOUT_S, ASYNC_RETRIES
    )


def cache_redis(settings: MessagingSettings | None = None) -> AsyncRedis:
    """Client async tới `redis-cache` (cache, rate limit); thiếu `REDIS_CACHE_URL` → `RuntimeError`."""
    return _async_client(_cache_url(settings or get_messaging_settings()), CACHE_DB, READ_TIMEOUT_S, ASYNC_RETRIES)


def broker_redis_sync(settings: MessagingSettings | None = None) -> SyncRedis:
    """Bản đồng bộ của `broker_redis` — cho tín hiệu Celery và callback sau commit."""
    return _sync_client((settings or get_messaging_settings()).redis_broker_url, BROKER_DB)


def streams_redis_sync(settings: MessagingSettings | None = None) -> SyncRedis:
    """Bản đồng bộ của `streams_redis` — đường ghi sự kiện sau commit; hết giờ không thử lại (NO-187)."""
    return _sync_client((settings or get_messaging_settings()).redis_broker_url, STREAM_DB, WRITE_RETRYABLE_ERRORS)


def safe_redis_sync(settings: MessagingSettings | None = None) -> SyncRedis:
    """Bản đồng bộ của `safe_redis`."""
    return _sync_client((settings or get_messaging_settings()).redis_broker_url, SAFE_DB)


def cache_redis_sync(settings: MessagingSettings | None = None) -> SyncRedis:
    """Bản đồng bộ của `cache_redis`; thiếu `REDIS_CACHE_URL` → `RuntimeError`."""
    return _sync_client(_cache_url(settings or get_messaging_settings()), CACHE_DB)


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
