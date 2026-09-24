"""Cấu hình worker `ml`. Nơi **duy nhất** đọc `ML_*`; không đọc biến chứa DSN (BE-00 §2.1).

`ML_BACKEND=fake` thay ba bộ chạy ONNX bằng bộ giả (`packages.ml_contracts.fakes`) cho
dev/test; `apps/ml/celery_main.py` từ chối nó ở `staging`/`production`.

`MlEnvSettings` là ngoại lệ hẹp của "chỉ đọc `ML_*`": nó đọc đúng một biến nền (`APP_ENV`)
để `ml` không phải cầm `SECRET_KEY` chỉ vì muốn biết mình đang chạy ở đâu (NO-085).
"""

from functools import cache
from typing import Annotated, Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MlEnvSettings(BaseSettings):
    """`APP_ENV` và **chỉ** `APP_ENV` — thứ duy nhất `ml` cần từ cấu hình nền (NO-085).

    Không đọc qua `CoreSettings`: nó đòi kèm `SECRET_KEY` (khoá gốc ký JWT) và
    `PUBLIC_BASE_URL`, nên lấy `APP_ENV` bằng nó là buộc compose đưa khoá ký vào một tiến
    trình chỉ nạp trọng số ngoài — trái tách quyền của BE-00 §2.1/§9. Đọc một lần lúc
    `worker_init`, nên không cần cache.
    """

    model_config = SettingsConfigDict(extra="ignore", env_file=None)

    app_env: Literal["dev", "test", "ci", "staging", "production"]


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
