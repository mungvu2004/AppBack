"""Cấu hình hàng đợi và Redis. Nơi **duy nhất** đọc `REDIS_*`, `CELERY_*`, `TASK_*`.

Hai instance Redis tách nhau vì `maxmemory-policy` tính cho cả instance (BE-00 §1):
`redis-broker` phải `noeviction` (mất thông điệp là mất việc), `redis-cache` được
`allkeys-lru`. Số hiệu DB của từng vai nằm ở `packages.messaging.redis`.

`REDIS_CACHE_URL` **tuỳ chọn**: worker `ml` không tới được `redis-cache` (BE-00 §2.1), nên
bắt buộc nó chỉ làm compose phải bịa một DSN chết (NO-085).
"""

from functools import cache
from typing import Annotated, Final
from urllib.parse import urlsplit

from pydantic import ValidationInfo, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_SCHEMES: Final = ("redis", "rediss")
MAX_BACKOFF_STEPS: Final = 10


def _check_redis_url(name: str, value: str) -> str:
    """URL Redis tuyệt đối, có host; số hiệu DB do gói tự đặt nên đường dẫn bị bỏ qua."""
    parts = urlsplit(value)
    if parts.scheme not in _SCHEMES or not parts.hostname:
        raise ValueError(f"{name} phải là URL redis(s):// có host: {value!r}")
    return value


class MessagingSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", env_file=None)

    redis_broker_url: str
    redis_cache_url: str | None = None
    """`None` = tiến trình này không tới được `redis-cache` (worker `ml`, NO-085).

    Tuỳ chọn chứ không bắt buộc: bắt buộc là buộc compose khai một DSN mà `ml` không bao
    giờ dùng. Tiến trình thật sự cần cache mà thiếu biến sẽ hỏng ở `cache_redis()`, có tên
    biến trong thông báo (fail-closed tại chỗ dùng, R-17)."""
    celery_visibility_timeout_s: int = 7200
    task_time_limit_s: int = 3600
    task_soft_time_limit_s: int = 3300
    # Phân cách dấu phẩy; phần tử thứ `n` là số giây chờ trước lượt thử lại thứ `n+1`.
    task_retry_backoff_s: Annotated[tuple[int, ...], NoDecode] = (10, 60, 300)
    stream_maxlen: int = 1000

    @field_validator("redis_broker_url")
    @classmethod
    def _broker_url(cls, value: str) -> str:
        return _check_redis_url("REDIS_BROKER_URL", value)

    @field_validator("redis_cache_url")
    @classmethod
    def _cache_url(cls, value: str | None) -> str | None:
        """URL cache phải hợp lệ **khi có**; vắng mặt là hợp lệ (NO-085)."""
        return value if value is None else _check_redis_url("REDIS_CACHE_URL", value)

    @field_validator("task_retry_backoff_s", mode="before")
    @classmethod
    def _split_backoff(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(int(item) for item in value.split(",") if item.strip())
        return value

    @field_validator("task_retry_backoff_s")
    @classmethod
    def _check_backoff(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        """Ít nhất một lượt thử lại, không âm, có trần để một cấu hình sai không giữ task cả ngày."""
        if not 1 <= len(value) <= MAX_BACKOFF_STEPS:
            raise ValueError(f"TASK_RETRY_BACKOFF_S cần 1-{MAX_BACKOFF_STEPS} bước, nhận {len(value)}")
        if any(step < 0 for step in value):
            raise ValueError("TASK_RETRY_BACKOFF_S không nhận số âm")
        return value

    @field_validator("task_soft_time_limit_s")
    @classmethod
    def _soft_below_hard(cls, value: int, info: ValidationInfo) -> int:
        """Trần mềm phải nhỏ hơn trần cứng, không thì task bị giết trước khi kịp dọn (J05)."""
        hard = info.data.get("task_time_limit_s")
        if isinstance(hard, int) and value >= hard:
            raise ValueError(f"TASK_SOFT_TIME_LIMIT_S ({value}) phải nhỏ hơn TASK_TIME_LIMIT_S ({hard})")
        return value


@cache
def get_messaging_settings() -> MessagingSettings:
    return MessagingSettings()


def reset_messaging_settings_cache() -> None:
    """Chỉ cho test và CLI: đọc lại biến môi trường ở lần gọi sau."""
    get_messaging_settings.cache_clear()
