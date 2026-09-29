"""Hạn mức của registry model ML (B6-01 [5], theo mẫu `apps/api/library/settings.py`).

Đọc **lười** qua `get_ml_registry_settings()`; test đổi trần bằng `monkeypatch.setenv` rồi
`reset_ml_registry_settings_cache()`. `protected_namespaces=()`: cả ba khoá bắt đầu bằng
`MODEL_`, thứ Pydantic vốn giữ riêng cho `model_config`/`model_dump`.
"""

from functools import cache
from typing import Final

from pydantic import PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict

UPLOAD_BODY_LIMIT: Final = 536870912
"""512 MiB — trần thân của N26 (`route_options`, HOP-DONG-MOI §8) và mặc định của khoá dưới.

Hằng riêng vì `route_options` chốt trần **lúc nạp module**, trước khi test kịp đổi biến môi
trường: trần thân của khung cố định, còn trần `storage.put` đọc `MODEL_UPLOAD_MAX_BYTES` ở
từng request nên test hạ được xuống 1 MiB.
"""


class MlRegistrySettings(BaseSettings):
    """Trần thân N26 và nhịp gửi lại đánh giá của lịch `requeue_evaluations`."""

    model_config = SettingsConfigDict(extra="ignore", env_file=None, protected_namespaces=())

    model_upload_max_bytes: PositiveInt = UPLOAD_BODY_LIMIT
    model_eval_requeue_after_s: PositiveInt = 1800
    model_eval_max_attempts: PositiveInt = 6


@cache
def get_ml_registry_settings() -> MlRegistrySettings:
    """Cấu hình của tiến trình, đọc biến môi trường một lần."""
    return MlRegistrySettings()


def reset_ml_registry_settings_cache() -> None:
    """Chỉ cho test và CLI: đọc lại biến môi trường ở lần gọi sau."""
    get_ml_registry_settings.cache_clear()
