"""App Celery: định tuyến theo tiền tố, cấu hình theo hiến chương, và đường gửi task."""

import os

import pytest
from celery import _state as celery_state

from packages.core.error_codes import DEPENDENCY_UNAVAILABLE
from packages.core.errors import AppError
from packages.messaging.celery_app import (
    AFTER_COMMIT_INLINE_ENV,
    DEFAULT_QUEUE,
    QUEUES,
    create_celery,
    producer_app,
    queue_for,
    reset_producer_app,
    route_task,
    send_task,
)
from packages.messaging.redis import broker_redis_sync
from packages.messaging.settings import MessagingSettings, get_messaging_settings, reset_messaging_settings_cache
from packages.messaging.tasks import TaskPayload
from packages.testing.fixtures.messaging import queued_payloads
from packages.testing.fixtures.services import refused_url


class Ping(TaskPayload):
    schema_version: int = 1
    run_id: str


def conf() -> MessagingSettings:
    return MessagingSettings(redis_broker_url="redis://broker:6379/0", redis_cache_url="redis://cache:6379/0")


@pytest.mark.parametrize(
    ("name", "queue"),
    [
        ("pipeline.drawings.render", "pipeline.cpu"),
        ("ml.infer.walls.segment", "ml.infer"),
        ("ml.training.yolo.launch", "ml.training"),
        ("notifications.fanout", DEFAULT_QUEUE),
        ("pipeline", DEFAULT_QUEUE),
        ("ml.inference.walls", DEFAULT_QUEUE),
    ],
)
def test_queue_is_derived_from_the_task_name_prefix(name: str, queue: str) -> None:
    assert queue_for(name) == queue
    assert route_task(name, [], {}, {}) == {"queue": queue}


def test_every_derived_queue_is_a_declared_queue() -> None:
    assert {queue_for(name) for name in ("pipeline.a", "ml.infer.a", "ml.training.a", "a")} == set(QUEUES)


def test_create_celery_applies_the_charter_configuration() -> None:
    settings = conf()
    app = create_celery("worker", settings)

    assert app.conf.task_serializer == app.conf.result_serializer == "json"
    assert app.conf.accept_content == app.conf.result_accept_content == ["json"]
    assert app.conf.task_ignore_result is True
    assert app.conf.task_acks_late is True
    assert app.conf.task_reject_on_worker_lost is True
    assert app.conf.worker_prefetch_multiplier == 1
    assert app.conf.task_default_queue == DEFAULT_QUEUE
    assert app.conf.task_time_limit == settings.task_time_limit_s
    assert app.conf.task_soft_time_limit == settings.task_soft_time_limit_s
    assert app.conf.worker_cancel_long_running_tasks_on_connection_loss is True
    assert app.conf.broker_connection_retry_on_startup is True
    assert app.conf.broker_url == settings.redis_broker_url


def test_visibility_timeout_is_set_in_exactly_one_place() -> None:
    """kombu không nhận `visibility_timeout` theo hàng; hai nơi khai là hai giá trị lệch nhau."""
    app = create_celery("worker", conf())

    assert app.conf.broker_transport_options == {"visibility_timeout": 7200}
    assert not app.conf.task_queues


def test_no_result_backend_is_configured() -> None:
    """Có `result_backend` là mở đường cho chord/group, thứ hiến chương cấm (K34)."""
    assert not create_celery("worker", conf()).conf.result_backend


def test_create_celery_turns_on_inline_after_commit_callbacks() -> None:
    create_celery("worker", conf())

    assert os.environ[AFTER_COMMIT_INLINE_ENV] == "1"


def test_after_commit_flag_does_not_leak_between_tests() -> None:
    """Test ngay sau một test gọi `create_celery`: cờ phải vắng mặt lại (BE-00 §7)."""
    assert AFTER_COMMIT_INLINE_ENV not in os.environ


def test_producer_app_is_built_once_and_never_becomes_current(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDIS_BROKER_URL", "redis://broker:6379/0")
    monkeypatch.setenv("REDIS_CACHE_URL", "redis://cache:6379/0")
    reset_messaging_settings_cache()
    reset_producer_app()

    app = producer_app()
    assert producer_app() is app
    # `set_as_current=False`: app gửi không được thành app "hiện hành" của tiến trình.
    assert celery_state.get_current_app() is not app

    reset_producer_app()
    assert producer_app() is not app
    reset_messaging_settings_cache()


def test_producer_app_does_not_wait_on_a_hung_broker(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gửi task nằm trên đường trả response: broker treo phải hỏng ngay, không giữ luồng."""
    monkeypatch.setenv("REDIS_BROKER_URL", "redis://broker:6379/0")
    monkeypatch.setenv("REDIS_CACHE_URL", "redis://cache:6379/0")
    reset_messaging_settings_cache()
    reset_producer_app()

    options = producer_app().conf.broker_transport_options
    assert options["socket_timeout"] == options["socket_connect_timeout"] == 1
    assert producer_app().conf.broker_connection_retry is False
    assert producer_app().conf.broker_connection_max_retries == 0
    reset_messaging_settings_cache()


def test_producer_app_does_not_set_the_inline_flag(messaging_env: None) -> None:
    """API giữ executor riêng cho callback sau commit; chỉ worker chạy chúng tại chỗ."""
    producer_app()

    assert AFTER_COMMIT_INLINE_ENV not in os.environ


def test_send_task_puts_one_message_on_the_queue_named_by_the_prefix(messaging_env: None) -> None:
    client = broker_redis_sync(get_messaging_settings())
    try:
        client.delete(*QUEUES)
        send_task("pipeline.drawings.render", Ping(run_id="run_1"))

        assert queued_payloads(client, "pipeline.cpu") == [{"schema_version": 1, "run_id": "run_1"}]
        assert client.llen(DEFAULT_QUEUE) == 0
    finally:
        client.delete(*QUEUES)
        client.close()


def test_send_task_reports_an_unreachable_broker_as_dependency_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C13: broker không nối được → 503 + `retry_after`, task gọi nó thử lại như lỗi tạm."""
    monkeypatch.setenv("REDIS_BROKER_URL", refused_url("redis"))
    monkeypatch.setenv("REDIS_CACHE_URL", refused_url("redis"))
    reset_messaging_settings_cache()
    reset_producer_app()

    with pytest.raises(AppError) as caught:
        send_task("pipeline.drawings.render", Ping(run_id="run_1"))

    assert caught.value.code is DEPENDENCY_UNAVAILABLE
    assert caught.value.retry_after == 5
    reset_messaging_settings_cache()
