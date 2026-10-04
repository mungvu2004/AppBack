"""Cấu hình hàng đợi: biên của từng trường và quy tắc giữa các trường."""

from typing import Any

import pytest
from pydantic import ValidationError

from packages.messaging.settings import (
    MAX_BACKOFF_STEPS,
    MessagingSettings,
    get_messaging_settings,
    reset_messaging_settings_cache,
)

BROKER = "redis://broker:6379/0"
CACHE = "redis://cache:6379/0"


def settings(**overrides: Any) -> MessagingSettings:
    """Dựng cấu hình từ tham số, không đụng biến môi trường."""
    return MessagingSettings(redis_broker_url=BROKER, redis_cache_url=CACHE, **overrides)


def test_defaults_match_the_charter() -> None:
    """Giá trị mặc định khớp hiến chương (BE-00 §7)."""
    conf = settings()

    assert conf.celery_visibility_timeout_s == 7200
    assert conf.task_time_limit_s == 3600
    assert conf.task_soft_time_limit_s == 3300
    assert conf.task_retry_backoff_s == (10, 60, 300)
    assert conf.stream_maxlen == 1000


@pytest.mark.parametrize(
    "url",
    ["", "http://broker:6379", "redis:///0", "amqp://broker:5672"],
)
def test_broker_url_must_be_redis(url: str) -> None:
    """URL broker rỗng, sai scheme hay thiếu host bị từ chối, có tên biến."""
    with pytest.raises(ValidationError, match="REDIS_BROKER_URL"):
        MessagingSettings(redis_broker_url=url, redis_cache_url=CACHE)


@pytest.mark.parametrize(
    ("name", "url"), [("REDIS_BROKER_URL", "redis://b:6379/db0"), ("REDIS_CACHE_URL", "redis://c:6379/-1")]
)
def test_redis_url__non_numeric_database_path_is_rejected_with_its_variable(name: str, url: str) -> None:
    """NO-270: đường dẫn URL là DB gốc mà vai cộng lên (`with_db`), nên không phải số thì hỏng ngay, có tên biến."""
    urls = {"REDIS_BROKER_URL": BROKER, "REDIS_CACHE_URL": CACHE} | {name: url}
    with pytest.raises(ValidationError, match=f"{name}: đường dẫn phải là số hiệu DB"):
        MessagingSettings(redis_broker_url=urls["REDIS_BROKER_URL"], redis_cache_url=urls["REDIS_CACHE_URL"])


@pytest.mark.parametrize("url", ["redis://b:6379", "redis://b:6379/", "redis://b:6379/7"])
def test_redis_url__empty_or_numeric_database_path_is_accepted(url: str) -> None:
    """Đường dẫn vắng (nền 0) hay là số DB đều hợp lệ."""
    assert MessagingSettings(redis_broker_url=url, redis_cache_url=CACHE).redis_broker_url == url


def test_cache_url_is_checked_too() -> None:
    """URL cache khi có cũng phải là URL Redis hợp lệ."""
    with pytest.raises(ValidationError, match="REDIS_CACHE_URL"):
        MessagingSettings(redis_broker_url=BROKER, redis_cache_url="postgres://x")


def test_a_process_without_the_cache_instance_loads_without_the_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    """NO-085: `ml` không tới được `redis-cache`, nên `REDIS_CACHE_URL` là tuỳ chọn.

    Bắt buộc nó là buộc mọi tiến trình khai một DSN nó không bao giờ dùng — và ở `ml` đi
    kèm cả `SECRET_KEY`, trái mục đích tách quyền của BE-00 §2.1/§9.
    """
    monkeypatch.setenv("REDIS_BROKER_URL", BROKER)
    monkeypatch.delenv("REDIS_CACHE_URL", raising=False)

    assert MessagingSettings().redis_cache_url is None


def test_rediss_scheme_is_accepted() -> None:
    """Scheme `rediss://` (TLS) hợp lệ như `redis://`."""
    assert settings().redis_broker_url == BROKER
    assert MessagingSettings(redis_broker_url="rediss://b:6379/0", redis_cache_url=CACHE).redis_broker_url


def test_backoff_is_parsed_from_a_comma_list() -> None:
    """`TASK_RETRY_BACKOFF_S` dạng chuỗi phân cách dấu phẩy thành tuple số."""
    assert settings(task_retry_backoff_s="1, 2,3").task_retry_backoff_s == (1, 2, 3)


def test_backoff_accepts_a_tuple_unchanged() -> None:
    """Tuple truyền thẳng giữ nguyên."""
    assert settings(task_retry_backoff_s=(5,)).task_retry_backoff_s == (5,)


@pytest.mark.parametrize(
    "value",
    ["", ",", "0," * (MAX_BACKOFF_STEPS + 1), "-1,2,3"],
)
def test_backoff_rejects_empty_too_long_and_negative(value: str) -> None:
    """Rỗng, quá `MAX_BACKOFF_STEPS` bước hay có số âm đều bị từ chối."""
    with pytest.raises(ValidationError, match="TASK_RETRY_BACKOFF_S"):
        settings(task_retry_backoff_s=value)


def test_zero_backoff_is_allowed_for_tests() -> None:
    """Backoff toàn 0 hợp lệ — test dùng để khỏi chờ."""
    assert settings(task_retry_backoff_s="0,0,0").task_retry_backoff_s == (0, 0, 0)


def test_soft_limit_must_stay_below_the_hard_limit() -> None:
    """Trần mềm phải nhỏ hơn trần cứng của task."""
    with pytest.raises(ValidationError, match="TASK_SOFT_TIME_LIMIT_S"):
        settings(task_time_limit_s=60, task_soft_time_limit_s=60)


def test_settings_are_cached_until_reset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cấu hình được nhớ tới khi gọi `reset_messaging_settings_cache`."""
    monkeypatch.setenv("REDIS_BROKER_URL", BROKER)
    monkeypatch.setenv("REDIS_CACHE_URL", CACHE)
    reset_messaging_settings_cache()

    first = get_messaging_settings()
    assert get_messaging_settings() is first

    monkeypatch.setenv("STREAM_MAXLEN", "7")
    assert get_messaging_settings().stream_maxlen == 1000

    reset_messaging_settings_cache()
    assert get_messaging_settings().stream_maxlen == 7
    reset_messaging_settings_cache()


@pytest.mark.parametrize("name", ["redis_broker_url", "redis_cache_url"])
def test_invalid_url_error_does_not_echo_the_password(name: str) -> None:
    """NO-329 mở rộng: thông điệp `ValidationError` của URL sai không in mật khẩu nhúng trong URL."""
    values: dict[str, Any] = {"redis_broker_url": BROKER, "redis_cache_url": CACHE}
    values[name] = "http://:s3cr3tpw@broker:6379/0"
    with pytest.raises(ValidationError) as caught:
        MessagingSettings(**values)
    assert "s3cr3tpw" not in str(caught.value)
