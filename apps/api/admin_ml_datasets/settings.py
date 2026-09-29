"""Hạn mức dựng dataset ML (B6-02 [5], theo mẫu `apps/api/admin_ml_registry/settings.py`).

Đọc **lười** qua `get_ml_datasets_settings()`; test đổi trần bằng `monkeypatch.setenv` rồi
`reset_ml_datasets_settings_cache()`.
"""

from functools import cache

from pydantic import PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


class MlDatasetsSettings(BaseSettings):
    """Trần mẫu/dự án và nhịp gửi lại, hết hạn của task dựng phiên bản."""

    model_config = SettingsConfigDict(extra="ignore", env_file=None)

    dataset_max_samples: PositiveInt = 2000
    dataset_project_ids_max: PositiveInt = 500
    dataset_build_requeue_after_s: PositiveInt = 600
    dataset_build_timeout_s: PositiveInt = 3600


@cache
def get_ml_datasets_settings() -> MlDatasetsSettings:
    """Cấu hình của tiến trình, đọc biến môi trường một lần."""
    return MlDatasetsSettings()


def reset_ml_datasets_settings_cache() -> None:
    """Chỉ cho test và CLI: đọc lại biến môi trường ở lần gọi sau."""
    get_ml_datasets_settings.cache_clear()
