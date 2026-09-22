"""Cấu hình worker `ml`. Nơi **duy nhất** đọc `ML_*`; không đọc biến chứa DSN (BE-00 §2.1).

`ML_BACKEND=fake` thay ba bộ chạy ONNX bằng bộ giả (`packages.ml_contracts.fakes`) cho
dev/test; `apps/ml/celery_main.py` từ chối nó ở `staging`/`production`.
"""

from functools import cache
from typing import Annotated, Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MlSettings(BaseSettings):
    """`ML_DEVICE`, `ML_BACKEND`, `ML_MODELS_DIR` (ảnh `ml` nhúng bản ghim ở đây), `ML_ORT_THREADS`."""

    model_config = SettingsConfigDict(extra="ignore", env_file=None)

    ml_device: Literal["auto", "cpu", "cuda"] = "auto"
    ml_backend: Literal["onnx", "fake"] = "onnx"
    ml_models_dir: str = "/opt/models"
    ml_ort_threads: Annotated[int, Field(ge=1, le=64)] = 4


@cache
def get_ml_settings() -> MlSettings:
    """`MlSettings` đọc một lần mỗi tiến trình."""
    return MlSettings()


def reset_ml_settings_cache() -> None:
    """Chỉ cho test và CLI: đọc lại biến môi trường ở lần gọi sau."""
    get_ml_settings.cache_clear()
