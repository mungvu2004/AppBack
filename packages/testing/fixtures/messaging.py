"""Fixture hàng đợi và Redis (B0-05).

Fixture async gắn `loop_scope="function"`: client `redis.asyncio` thuộc về vòng sự
kiện tạo ra nó, mà test chạy trên vòng của riêng nó (`asyncio_default_test_loop_scope`).

Dịch vụ là **thật**: Redis của Testcontainers, worker Celery thật chạy trong luồng
(K23 cấm `fakeredis`, `task_always_eager`). Vì broker là fixture phạm vi session và
không tự dọn, test nào khẳng định số thông điệp trên một hàng thì tự `DEL` hàng đó
ở đầu test (BE-00 §12).

`producer_reset` tự áp cho **mọi** test trong repo: URL broker đổi mỗi lượt chạy,
và `DB_AFTER_COMMIT_INLINE` do `create_celery` đặt không được rò sang test sau.
"""

import base64
import json
import logging
import os
import warnings
from collections.abc import AsyncIterator, Callable, Iterator, Sequence
from contextlib import AbstractContextManager, asynccontextmanager, contextmanager, suppress

import pytest
import pytest_asyncio
from celery import Celery
from celery.contrib.testing.worker import start_worker
from celery.signals import setup_logging

from packages.messaging.celery_app import AFTER_COMMIT_INLINE_ENV, QUEUES, create_celery, reset_producer_app
from packages.messaging.redis import (
    BROKER_POLICY,
    AsyncRedis,
    SyncRedis,
    broker_redis_sync,
    cache_redis,
    safe_redis,
    streams_redis,
    sync_result,
)
from packages.messaging.settings import get_messaging_settings, reset_messaging_settings_cache
from packages.messaging.streams import EventBus
from packages.messaging.tasks import reset_delivery_client
from packages.observability.settings import reset_observability_settings_cache
from packages.testing.fixtures.services import ephemeral_redis

WORKER_SHUTDOWN_TIMEOUT_S = 20.0


def queued_payloads(client: SyncRedis, queue: str) -> list[dict[str, object]]:
    """Thân task của mọi thông điệp đang nằm trên một hàng, đã bóc vỏ kombu.

    kombu gói thân trong một phong bì JSON và mã hoá base64, nên so chuỗi thô trên
    `LRANGE` là so nhầm; test đếm và soi payload qua hàm này.
    """
    payloads: list[dict[str, object]] = []
    for raw in sync_result(client.lrange(queue, 0, -1), list):
        envelope = json.loads(raw)
        args, _kwargs, _embed = json.loads(base64.b64decode(envelope["body"]))
        payloads.append(args[0])
    return payloads


@pytest.fixture(autouse=True)
def producer_reset(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Bỏ app gửi đang nhớ và cô lập `DB_AFTER_COMMIT_INLINE` quanh **mọi** test.

    `monkeypatch.delenv` nhớ giá trị cũ và tự trả lại, nên cờ do `create_celery` đặt
    trong một test không rò sang test sau (BE-00 §7) — và mỗi test bắt đầu với cờ
    vắng mặt, đúng như tiến trình API.
    """
    monkeypatch.delenv(AFTER_COMMIT_INLINE_ENV, raising=False)
    _forget_process_clients()
    yield
    _forget_process_clients()


def _forget_process_clients() -> None:
    """Bỏ mọi tài nguyên nhớ theo tiến trình — URL Redis đổi giữa các lượt test."""
    reset_producer_app()
    reset_delivery_client()


@pytest.fixture
def messaging_env(redis_broker_url: str, redis_cache_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Trỏ cấu hình vào hai Redis thật; `TASK_RETRY_BACKOFF_S=0,0,0` để test không phải chờ.

    `METRICS_PORT=0` như `api_env` (NO-159): pool `solo` của `celery_worker_factory` bắn
    `worker_process_init` **trong tiến trình pytest** (`celery/concurrency/solo.py`) và không
    bắn tín hiệu tắt nào, nên không đặt cổng về 0 là tiến trình test giữ một exporter thật
    sống trên 9464 tới hết lượt chạy — làm đỏ teardown của `packages/observability/tests`
    (review DEBT-01 finding 1). Test nào cần exporter thật tự đặt cổng của nó.
    """
    monkeypatch.setenv("METRICS_PORT", "0")
    monkeypatch.setenv("REDIS_BROKER_URL", redis_broker_url)
    monkeypatch.setenv("REDIS_CACHE_URL", redis_cache_url)
    monkeypatch.setenv("TASK_RETRY_BACKOFF_S", "0,0,0")
    reset_messaging_settings_cache()
    # `ObservabilitySettings` là `@cache` theo tiến trình: một test chạy trước đã đọc 9464
    # thì `setenv` ở trên không tới được exporter nếu không xoá cache hai đầu.
    reset_observability_settings_cache()
    yield
    reset_messaging_settings_cache()
    reset_observability_settings_cache()


@asynccontextmanager
async def _flushed(client: AsyncRedis) -> AsyncIterator[AsyncRedis]:
    """Trao client rồi `FLUSHDB` + đóng kết nối — mỗi test bắt đầu trên DB sạch."""
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()


@pytest_asyncio.fixture(loop_scope="function")
async def streams_client(messaging_env: None) -> AsyncIterator[AsyncRedis]:
    async with _flushed(streams_redis()) as client:
        yield client


@pytest_asyncio.fixture(loop_scope="function")
async def safe_client(messaging_env: None) -> AsyncIterator[AsyncRedis]:
    async with _flushed(safe_redis()) as client:
        yield client


@pytest_asyncio.fixture(loop_scope="function")
async def cache_client(messaging_env: None) -> AsyncIterator[AsyncRedis]:
    async with _flushed(cache_redis()) as client:
        yield client


@pytest.fixture
def event_bus(streams_client: AsyncRedis) -> EventBus:
    return EventBus(streams_client)


@pytest.fixture
def celery_test_app(messaging_env: None) -> Celery:
    """App Celery trên broker Redis thật.

    Cờ `DB_AFTER_COMMIT_INLINE` mà `create_celery` đặt do `producer_reset` (autouse)
    trả lại, nên ở đây không lặp lại việc đó.
    """
    return create_celery("test", get_messaging_settings())


type WorkerFactory = Callable[[Sequence[str]], AbstractContextManager[None]]


@pytest.fixture
def celery_worker_factory(celery_test_app: Celery) -> WorkerFactory:
    """Dựng worker thật nghe **đúng** các hàng được nêu (BE-00 §7 "Test task").

    Worker không được nghe hàng mà task đang kiểm gửi tới, không thì nó nuốt mất
    thông điệp mà test muốn đếm. `pool="solo"` để task chạy trong luồng của
    `start_worker`, `perform_ping_check=False` vì app thử không đăng ký task `ping`.
    """

    @contextmanager
    def factory(queues: Sequence[str]) -> Iterator[None]:
        unknown = set(queues) - set(QUEUES)
        if unknown:
            raise ValueError(f"hàng lạ: {sorted(unknown)}")
        setup_logging.connect(_keep_root_logger)
        try:
            with (
                _restoring_process_logging(),
                start_worker(
                    celery_test_app,
                    queues=list(queues),
                    pool="solo",
                    concurrency=1,
                    perform_ping_check=False,
                    shutdown_timeout=WORKER_SHUTDOWN_TIMEOUT_S,
                ),
            ):
                yield
        finally:
            setup_logging.disconnect(_keep_root_logger)

    return factory


def _keep_root_logger(**_kwargs: object) -> None:
    """Receiver `setup_logging` chỉ nối trong lúc dựng worker thử: logger gốc để nguyên cho pytest (NO-078).

    `start_worker` gọi `app.log.setup`; không có receiver nào thì Celery 5.6 thay handler của logger gốc
    (gỡ cả handler bắt log của pytest) và đặt mức ERROR mà không trả lại — `WARNING` của mọi test sau
    không vào báo cáo đỏ. `worker_hijack_root_logger=False` không đủ: mức vẫn bị đặt. Có receiver thì
    Celery bỏ hẳn phần cấu hình logger. Hàm cấp module: `Signal.connect` giữ tham chiếu yếu.
    """


CELERY_PROCESS_ENV = (
    "CELERY_LOG_LEVEL",
    "CELERY_LOG_FILE",
    "_MP_FORK_LOGLEVEL_",
    "_MP_FORK_LOGFILE_",
    "_MP_FORK_LOGFORMAT_",
)
"""Biến môi trường `app.log.setup` của Celery 5.6 đặt cho cả tiến trình, có receiver `setup_logging` hay không."""


@contextmanager
def _restoring_process_logging() -> Iterator[None]:
    """Trả lại dấu cấp tiến trình mà `app.log.setup` để lại khi worker thử dừng (NO-087).

    Các dòng này chạy ngoài nhánh `if not receivers` nên `_keep_root_logger` không chặn được: `os.environ`
    (`CELERY_PROCESS_ENV`), `warnings.filterwarnings('always', …)`, `logging.captureWarnings(True)`.
    `catch_warnings` trả bộ lọc và `showwarning`; `captureWarnings(False)` còn xoá hàm cũ mà `logging` giữ,
    và chỉ gọi khi chính worker bật capture (`showwarning` đã đổi) — capture ai bật từ trước thì để nguyên.
    """
    saved_env = {key: os.environ[key] for key in CELERY_PROCESS_ENV if key in os.environ}
    showwarning = warnings.showwarning
    with warnings.catch_warnings():
        try:
            yield
        finally:
            if warnings.showwarning is not showwarning:
                logging.captureWarnings(False)
            for key in CELERY_PROCESS_ENV:
                os.environ.pop(key, None)
            os.environ.update(saved_env)


@pytest.fixture
def celery_worker(celery_worker_factory: WorkerFactory) -> Iterator[None]:
    """Worker nghe cả bốn hàng — chỉ dùng khi test **không** đếm thông điệp gửi đi."""
    with celery_worker_factory(QUEUES):
        yield


@contextmanager
def ephemeral_broker(monkeypatch: pytest.MonkeyPatch) -> Iterator[SyncRedis]:
    """Một Redis `noeviction` **thật** của riêng một test, cấu hình đã trỏ vào nó.

    Dùng cho những hỏng hóc chỉ dựng được trên máy chủ thật — K23 cấm mock chính Redis.
    Trả một client quản trị: `config_set("maxmemory", "1")` để ép instance chạm trần và
    từ chối mọi lệnh ghi (`OutOfMemoryError`), `stop()` container để cắt kết nối.
    """
    container = ephemeral_redis(BROKER_POLICY)
    url = f"redis://{container.get_container_host_ip()}:{container.get_exposed_port(6379)}/0"
    monkeypatch.setenv("REDIS_BROKER_URL", url)
    monkeypatch.setenv("REDIS_CACHE_URL", url)
    reset_messaging_settings_cache()
    _forget_process_clients()
    admin = broker_redis_sync()
    try:
        yield admin
    finally:
        admin.close()
        # Test có thể đã tự dừng container để dựng lỗi; lượt dừng thứ hai ném `NotFound`.
        with suppress(Exception):
            container.stop()
        reset_messaging_settings_cache()
        _forget_process_clients()
