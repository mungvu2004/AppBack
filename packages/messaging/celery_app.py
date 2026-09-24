"""App Celery dùng chung và đường gửi task (BE-00 §7, K34).

Hàng đợi suy từ **tiền tố tên task**, nên `apps/api` gửi việc bằng tên chuỗi và
không phải nhập mã worker (cũng không phải biết task chạy ở ảnh nào).

Tiến trình gửi (API) dùng `producer_app()`: app dựng lười, trần socket 1 giây,
không thử lại kết nối — broker treo thì lỗi ngay chứ không giữ luồng của request.
Tiến trình chạy (worker) dùng `create_celery()`.
"""

import logging
import os
from collections.abc import Mapping
from typing import Any, Final

import kombu.exceptions
from celery import Celery
from celery.signals import worker_process_init
from pydantic import BaseModel

from packages.core.error_codes import DEPENDENCY_UNAVAILABLE
from packages.messaging.redis import DEPENDENCY_ERRORS, DEPENDENCY_RETRY_AFTER, ProcessLocal
from packages.messaging.settings import MessagingSettings, get_messaging_settings
from packages.observability.exporter import start_exporter
from packages.observability.settings import get_observability_settings

_log: Final = logging.getLogger(__name__)

DEFAULT_QUEUE: Final = "default"
QUEUES: Final = (DEFAULT_QUEUE, "pipeline.cpu", "ml.infer", "ml.training")
# Tiền tố dài trước tiền tố ngắn: `ml.infer.` phải thắng khi cả hai cùng khớp.
_QUEUE_BY_PREFIX: Final[tuple[tuple[str, str], ...]] = (
    ("pipeline.", "pipeline.cpu"),
    ("ml.infer.", "ml.infer"),
    ("ml.training.", "ml.training"),
)
AFTER_COMMIT_INLINE_ENV: Final = "DB_AFTER_COMMIT_INLINE"
PRODUCER_SOCKET_TIMEOUT_S: Final = 1

# Lớp thật mà kombu/redis ném khi broker không phục vụ được. Liệt kê tường minh để lỗi
# lệnh (sai tên hàng, payload hỏng) vẫn nổi lên nguyên trạng (R-16). Dùng chung
# `DEPENDENCY_ERRORS` để hai đường — gửi task và đọc/ghi Redis — không lệch nhau (R-07).
BROKER_CONNECTION_ERRORS: Final = (kombu.exceptions.OperationalError, *DEPENDENCY_ERRORS)


def queue_for(name: str) -> str:
    """Hàng đợi của một task, suy từ tiền tố tên (BE-00 §7)."""
    for prefix, queue in _QUEUE_BY_PREFIX:
        if name.startswith(prefix):
            return queue
    return DEFAULT_QUEUE


def route_task(name: str, args: object, kwargs: object, options: object, **_: object) -> dict[str, str]:
    """`task_routes` của Celery: một hàm thay cho bảng, để tên mới không phải khai lại."""
    return {"queue": queue_for(name)}


def _base_conf(settings: MessagingSettings) -> dict[str, Any]:
    """Cấu hình chung của mọi app Celery trong repo (BE-00 §7).

    Không `result_backend`: pipeline điều phối bằng trạng thái trong DB, không bằng
    kết quả task, nên chord/group/chain đều bị cấm (K34).
    """
    return {
        "task_serializer": "json",
        "result_serializer": "json",
        "accept_content": ["json"],
        "result_accept_content": ["json"],
        "task_ignore_result": True,
        "task_acks_late": True,
        "task_reject_on_worker_lost": True,
        "worker_prefetch_multiplier": 1,
        "task_routes": (route_task,),
        "task_default_queue": DEFAULT_QUEUE,
        "timezone": "UTC",
        "enable_utc": True,
    }


def create_celery(name: str, settings: MessagingSettings | None = None) -> Celery:
    """App Celery của một tiến trình **chạy** task (worker, beat).

    Đặt `DB_AFTER_COMMIT_INLINE=1`: trong worker, callback sau commit chạy tại chỗ,
    tuần tự, xong trước khi `commit` trả (BE-00 §7) — worker không có `AppRoute` để
    chờ executor riêng như API.
    """
    conf = settings or get_messaging_settings()
    app = Celery(name, broker=conf.redis_broker_url)
    app.conf.update(
        **_base_conf(conf),
        # Một giá trị cho cả DB Redis: kombu không đặt visibility_timeout theo hàng.
        broker_transport_options={"visibility_timeout": conf.celery_visibility_timeout_s},
        task_time_limit=conf.task_time_limit_s,
        task_soft_time_limit=conf.task_soft_time_limit_s,
        worker_cancel_long_running_tasks_on_connection_loss=True,
        broker_connection_retry_on_startup=True,
    )
    os.environ[AFTER_COMMIT_INLINE_ENV] = "1"
    return app


@worker_process_init.connect
def start_metrics_exporter(**_: object) -> None:
    """Mở exporter `/metrics` của **tiến trình con Celery** (BE-00 §11, NO-161).

    Gắn ở đây chứ không ở từng điểm vào: `apps/worker` và `apps/ml` đều dựng app bằng
    `create_celery`, nên nhập module này là cả hai ảnh có exporter — một cài đặt, không
    bản chép (R-07). `worker_process_init` chứ không `worker_init`: pool prefork fork sau
    khi tiến trình chính đã lên, mà một socket mở trước `fork` không dùng chung được.

    `METRICS_PORT <= 0` là tắt (mặc định của test, NO-159); cổng bận chỉ là một `WARNING`
    — không có metric thì vẫn phải chạy được việc.
    """
    settings = get_observability_settings()
    if settings.metrics_port <= 0:
        return
    try:
        start_exporter(host=settings.metrics_host, port=settings.metrics_port)
    except OSError as exc:
        _log.warning("metrics_exporter_unavailable", extra={"error": repr(exc)})


def _build_producer() -> Celery:
    """App chỉ để **gửi** task.

    Không `set_as_current`: tiến trình API không có app Celery "hiện hành", nên một
    `shared_task` nhập nhầm vào API cũng không tự gắn vào app này. Không thử lại kết
    nối: `send_task` chạy trên đường trả response, broker treo phải hỏng ngay.
    """
    conf = get_messaging_settings()
    app = Celery("producer", broker=conf.redis_broker_url, set_as_current=False)
    app.conf.update(
        **_base_conf(conf),
        broker_transport_options={
            "visibility_timeout": conf.celery_visibility_timeout_s,
            "socket_timeout": PRODUCER_SOCKET_TIMEOUT_S,
            "socket_connect_timeout": PRODUCER_SOCKET_TIMEOUT_S,
        },
        broker_connection_retry=False,
        broker_connection_retry_on_startup=False,
        broker_connection_max_retries=0,
    )
    return app


_producer: Final = ProcessLocal[Celery](_build_producer)


def producer_app() -> Celery:
    """App gửi task của tiến trình hiện tại, dựng lười và dựng lại sau `fork`."""
    return _producer.get()


def reset_producer_app() -> None:
    """Chỉ cho test và CLI: bỏ app gửi đang nhớ (URL broker đổi giữa các lượt test)."""
    _producer.reset()


def send_task(name: str, payload: BaseModel) -> None:
    """Gửi một task theo tên; hàng đợi suy từ tiền tố (BE-00 §7).

    Gọi **sau khi commit** (`on_after_commit`, K17): worker có thể nhận thông điệp
    trước khi giao dịch của người gửi kết thúc. Broker không nối được → 503
    `DEPENDENCY_UNAVAILABLE`, task gọi nó thử lại như lỗi tạm (J02).
    """
    body: Mapping[str, object] = payload.model_dump(mode="json")
    try:
        producer_app().send_task(name, args=[body], queue=queue_for(name), retry=False)
    except BROKER_CONNECTION_ERRORS as exc:
        raise DEPENDENCY_UNAVAILABLE.error(retry_after=DEPENDENCY_RETRY_AFTER) from exc
