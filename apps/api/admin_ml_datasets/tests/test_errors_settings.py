"""`errors.py`, `settings.py`: mã lỗi khai đúng luật (import không ném), hạn mức đọc lười và đổi được."""

import pytest
from pydantic import ValidationError

from apps.api.admin_ml_datasets.errors import (
    DATASET_BUILD_IN_PROGRESS,
    DATASET_BUILD_TIMEOUT,
    DATASET_EMPTY,
    DATASET_FAMILY_UNSUPPORTED,
    DATASET_NAME_TAKEN,
    DATASET_TOO_LARGE,
)
from apps.api.admin_ml_datasets.settings import get_ml_datasets_settings, reset_ml_datasets_settings_cache


def test_errors__status_and_failure_codes() -> None:
    """Mã lỗi 409 và các mã `failure_code` khớp hợp đồng."""
    assert (DATASET_NAME_TAKEN.status, DATASET_BUILD_IN_PROGRESS.status) == (409, 409)
    assert {DATASET_EMPTY, DATASET_TOO_LARGE, DATASET_FAMILY_UNSUPPORTED, DATASET_BUILD_TIMEOUT} == {
        "DATASET_EMPTY",
        "DATASET_TOO_LARGE",
        "DATASET_FAMILY_UNSUPPORTED",
        "DATASET_BUILD_TIMEOUT",
    }


def test_settings__defaults_and_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mặc định của settings và ghi đè bằng biến môi trường."""
    reset_ml_datasets_settings_cache()
    defaults = get_ml_datasets_settings()
    assert defaults.dataset_max_samples == 2000
    assert defaults.dataset_project_ids_max == 500
    assert defaults.dataset_build_requeue_after_s == 600
    assert defaults.dataset_build_timeout_s == 3600

    monkeypatch.setenv("DATASET_MAX_SAMPLES", "5")
    reset_ml_datasets_settings_cache()
    assert get_ml_datasets_settings().dataset_max_samples == 5
    reset_ml_datasets_settings_cache()


def test_settings__rejects_non_positive() -> None:
    """Settings từ chối giá trị không dương."""
    from apps.api.admin_ml_datasets.settings import MlDatasetsSettings

    with pytest.raises(ValidationError):
        MlDatasetsSettings(dataset_max_samples=0)
