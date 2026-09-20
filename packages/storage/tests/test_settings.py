"""Cấu hình kho: thiếu trường thì hỏng **lúc nạp**, không phải lúc ghi object đầu tiên."""

from collections.abc import Iterator

import pytest
from pydantic import SecretStr, ValidationError

from packages.core.settings import reset_settings_cache
from packages.storage.settings import StorageSettings, get_storage_settings, reset_storage_settings_cache

APP_URL = "https://appback.test"
S3_FIELDS = {
    "s3_endpoint": "http://minio:9000",
    "s3_public_endpoint": "https://files.appback.test",
    "s3_bucket": "appback",
    "s3_access_key": "key",
    "s3_secret_key": "secret",
}
_ENV_NAMES = ("STORAGE_BACKEND", "STORAGE_LOCAL_ROOT", *(name.upper() for name in S3_FIELDS), "S3_REGION")


@pytest.fixture(autouse=True)
def core_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Cấu hình lõi tối thiểu, môi trường kho sạch; test tự đổi `APP_ENV` khi cần."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("PUBLIC_BASE_URL", APP_URL)
    monkeypatch.setenv("SECRET_KEY", "secret-du-dai-cho-cau-hinh-b0-04")
    for name in _ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    reset_settings_cache()
    reset_storage_settings_cache()
    yield
    reset_settings_cache()
    reset_storage_settings_cache()


def s3_settings(**overrides: str) -> StorageSettings:
    """`StorageSettings` S3 hợp lệ, cho phép ghi đè từng trường để kiểm một luật."""
    fields = {**S3_FIELDS, **overrides}
    return StorageSettings(
        storage_backend="s3",
        s3_endpoint=fields["s3_endpoint"],
        s3_public_endpoint=fields["s3_public_endpoint"],
        s3_bucket=fields["s3_bucket"],
        s3_access_key=fields["s3_access_key"],
        s3_secret_key=SecretStr(fields["s3_secret_key"]),
    )


def production(monkeypatch: pytest.MonkeyPatch) -> None:
    """Chuyển sang `APP_ENV=production` (PUBLIC_BASE_URL đã là https)."""
    monkeypatch.setenv("APP_ENV", "production")
    reset_settings_cache()


def test_local_backend_needs_a_root() -> None:
    with pytest.raises(ValidationError, match="STORAGE_LOCAL_ROOT"):
        StorageSettings(storage_backend="local")


def test_local_backend_is_enough_with_a_root() -> None:
    settings = StorageSettings(storage_backend="local", storage_local_root="/var/lib/appback")

    assert settings.storage_local_root == "/var/lib/appback"
    assert settings.s3_region == "us-east-1"


def test_s3_backend_lists_missing_fields() -> None:
    with pytest.raises(ValidationError, match="S3_ENDPOINT, S3_PUBLIC_ENDPOINT, S3_BUCKET"):
        StorageSettings(storage_backend="s3")


def test_s3_backend_needs_a_secret_key() -> None:
    with pytest.raises(ValidationError, match="S3_SECRET_KEY"):
        s3_settings(s3_secret_key="")


@pytest.mark.parametrize("endpoint", ["minio:9000", "http://minio:9000/bucket", "ftp://minio", "http://"])
def test_s3_endpoints_must_be_absolute_urls(endpoint: str) -> None:
    with pytest.raises(ValidationError, match="S3_ENDPOINT"):
        s3_settings(s3_endpoint=endpoint)


def test_production_rejects_s3_on_the_app_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    """BE-00 §8, K15: S3 không đặt được `nosniff`, nên phải khác origin với app."""
    production(monkeypatch)

    with pytest.raises(ValidationError, match="khác origin"):
        s3_settings(s3_public_endpoint=APP_URL)


def test_production_accepts_s3_on_another_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    production(monkeypatch)

    assert s3_settings().s3_public_endpoint == "https://files.appback.test"


def test_dev_may_share_the_origin() -> None:
    """Ở dev/test cùng origin vẫn chạy được: rủi ro chỉ có thật khi ra ngoài."""
    assert s3_settings(s3_public_endpoint=APP_URL).s3_public_endpoint == APP_URL


def test_get_storage_settings_reads_env_and_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_LOCAL_ROOT", "/objects")

    assert get_storage_settings().storage_local_root == "/objects"
    monkeypatch.setenv("STORAGE_LOCAL_ROOT", "/khac")
    assert get_storage_settings().storage_local_root == "/objects"

    reset_storage_settings_cache()
    assert get_storage_settings().storage_local_root == "/khac"
