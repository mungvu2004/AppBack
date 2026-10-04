"""Cấu hình kho: thiếu trường thì hỏng **lúc nạp**, không phải lúc ghi object đầu tiên."""

from collections.abc import Iterator
from typing import Literal

import pytest
from pydantic import SecretStr, ValidationError

from packages.storage.settings import StorageSettings, get_storage_settings, reset_storage_settings_cache

S3_FIELDS = {
    "s3_endpoint": "http://minio:9000",
    "s3_public_endpoint": "https://files.appback.test",
    "s3_bucket": "appback",
    "s3_access_key": "key",
    "s3_secret_key": "secret",
}
AppEnv = Literal["dev", "test", "ci", "staging", "production"]
_ENV_NAMES = ("STORAGE_BACKEND", "STORAGE_LOCAL_ROOT", *(name.upper() for name in S3_FIELDS), "S3_REGION", "APP_ENV")


@pytest.fixture(autouse=True)
def storage_env_clean(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Môi trường kho sạch; test tự đặt biến khi cần."""
    for name in _ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    reset_storage_settings_cache()
    yield
    reset_storage_settings_cache()


def s3_settings(app_env: AppEnv = "dev", **overrides: str) -> StorageSettings:
    """`StorageSettings` S3 hợp lệ, cho phép ghi đè từng trường để kiểm một luật."""
    fields = {**S3_FIELDS, **overrides}
    return StorageSettings(
        storage_backend="s3",
        app_env=app_env,
        s3_endpoint=fields["s3_endpoint"],
        s3_public_endpoint=fields["s3_public_endpoint"],
        s3_bucket=fields["s3_bucket"],
        s3_access_key=fields["s3_access_key"],
        s3_secret_key=SecretStr(fields["s3_secret_key"]),
    )


def test_local_backend_needs_a_root() -> None:
    """Backend local thiếu `STORAGE_LOCAL_ROOT` → lỗi lúc nạp."""
    with pytest.raises(ValidationError, match="STORAGE_LOCAL_ROOT"):
        StorageSettings(storage_backend="local")


def test_local_backend_is_enough_with_a_root() -> None:
    """Backend local chỉ cần `STORAGE_LOCAL_ROOT`."""
    settings = StorageSettings(storage_backend="local", storage_local_root="/var/lib/appback")

    assert settings.storage_local_root == "/var/lib/appback"
    assert settings.s3_region == "us-east-1"


def test_s3_backend_lists_missing_fields() -> None:
    """Backend S3 liệt kê mọi trường còn thiếu."""
    with pytest.raises(ValidationError, match="S3_ENDPOINT, S3_PUBLIC_ENDPOINT, S3_BUCKET"):
        StorageSettings(storage_backend="s3")


def test_s3_backend_needs_a_secret_key() -> None:
    """Backend S3 thiếu `S3_SECRET_KEY` → lỗi lúc nạp."""
    with pytest.raises(ValidationError, match="S3_SECRET_KEY"):
        s3_settings(s3_secret_key="")


@pytest.mark.parametrize("endpoint", ["minio:9000", "http://minio:9000/bucket", "ftp://minio", "http://"])
def test_s3_endpoints_must_be_absolute_urls(endpoint: str) -> None:
    """Endpoint S3 phải là URL tuyệt đối http(s) không có đường dẫn."""
    with pytest.raises(ValidationError, match="S3_ENDPOINT"):
        s3_settings(s3_endpoint=endpoint)


def test_production_s3_loads_without_the_api_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dịch vụ `ml` không có `SECRET_KEY`/`PUBLIC_BASE_URL` vẫn nạp được cấu hình kho (FIX-105)."""
    monkeypatch.setenv("APP_ENV", "production")
    for name in ("SECRET_KEY", "SECRET_KEY_PREVIOUS", "PUBLIC_BASE_URL"):
        monkeypatch.delenv(name, raising=False)

    assert s3_settings().s3_public_endpoint == "https://files.appback.test"


def test_get_storage_settings_reads_env_and_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    """`get_storage_settings` đọc env một lần và nhớ kết quả."""
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_LOCAL_ROOT", "/objects")

    assert get_storage_settings().storage_local_root == "/objects"
    monkeypatch.setenv("STORAGE_LOCAL_ROOT", "/khac")
    assert get_storage_settings().storage_local_root == "/objects"

    reset_storage_settings_cache()
    assert get_storage_settings().storage_local_root == "/khac"


@pytest.mark.parametrize("app_env", ["staging", "production"])
@pytest.mark.parametrize("field", ["s3_access_key", "s3_secret_key"])
def test_s3_placeholder_credentials__rejected_outside_dev(app_env: AppEnv, field: str) -> None:
    """SEC-041: khoá mẫu `change-me-*` của `env.example` không được nhận ở staging/production."""
    with pytest.raises(ValidationError, match="khoá mẫu"):
        s3_settings(app_env, **{field: f"change-me-api-{field}"})


def test_s3_placeholder_credentials__accepted_in_dev() -> None:
    """Dev/test/ci giữ nguyên `env.example` để dựng nhanh."""
    settings = s3_settings(
        "dev",
        s3_access_key="change-me-api-access",
        s3_secret_key="change-me-api-secret",  # noqa: S106 — khoá mẫu công khai của env.example
    )

    assert settings.s3_access_key == "change-me-api-access"


def test_invalid_endpoint__error_does_not_echo_credentials() -> None:
    """Endpoint dán nhầm `user:mật-khẩu@host` không được lộ nguyên văn trong thông điệp lỗi."""
    with pytest.raises(ValidationError) as raised:
        s3_settings(s3_endpoint="http://admin:hunter2secret@minio:9000/path")

    assert "hunter2secret" not in str(raised.value)
