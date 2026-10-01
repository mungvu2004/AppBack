"""Hạn của job huấn luyện (B6-03a [5]), theo mẫu `apps/api/admin_ml_datasets/settings.py`.

Một nguồn cho cả API và cầu nối (`apps/worker/training_bridge/settings.py` chỉ đọc lại):
N35 và cầu nối cùng đặt `cancel_key` với một TTL, N36/N37 và cầu nối cùng một cửa sổ muộn.
Đọc **lười** qua `get_training_settings()`; test đổi bằng `monkeypatch.setenv` rồi
`reset_training_settings_cache()`.
"""

from functools import cache

from pydantic import PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


class TrainingSettings(BaseSettings):
    """TTL khoá huỷ, ba nhịp lịch, cửa sổ muộn, trần trọng số/log/điểm của mỗi job."""

    model_config = SettingsConfigDict(extra="ignore", env_file=None)

    training_cancel_ttl_s: PositiveInt = 172800
    training_heartbeat_timeout_s: PositiveInt = 300
    training_requeue_after_s: PositiveInt = 600
    training_purge_after_s: PositiveInt = 3600
    training_late_window_s: PositiveInt = 600
    training_weights_max_bytes: PositiveInt = 536870912
    training_max_log_lines: PositiveInt = 10000
    training_max_metric_points: PositiveInt = 200000


@cache
def get_training_settings() -> TrainingSettings:
    """Cấu hình của tiến trình, đọc biến môi trường một lần."""
    return TrainingSettings()


def reset_training_settings_cache() -> None:
    """Chỉ cho test: đọc lại biến môi trường ở lần gọi sau."""
    get_training_settings.cache_clear()
