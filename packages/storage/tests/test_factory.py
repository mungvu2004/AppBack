"""`create_storage` chọn đúng bộ điều hợp và đúng địa chỉ ký."""

from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import pytest
from pydantic import SecretStr

from packages.core.settings import CoreSettings, reset_settings_cache
from packages.storage.factory import create_storage
from packages.storage.local import LocalDiskStorage
from packages.storage.s3 import S3Storage
from packages.storage.settings import StorageSettings
from packages.testing.fixtures.clock import FakeClock

APP_URL = "https://appback.test"
PUBLIC_ENDPOINT = "https://files.appback.test"
KEY = "library/sofa/preview.png"


@pytest.fixture
def core_settings(monkeypatch: pytest.MonkeyPatch) -> CoreSettings:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("PUBLIC_BASE_URL", APP_URL)
    monkeypatch.setenv("SECRET_KEY", "secret-du-dai-cho-factory-cua-b0-04")
    reset_settings_cache()
    return CoreSettings()


async def test_create_storage_local(core_settings: CoreSettings, fake_clock: FakeClock, tmp_path: Path) -> None:
    settings = StorageSettings(storage_backend="local", storage_local_root=str(tmp_path))

    storage = create_storage(settings, core_settings, fake_clock)

    assert isinstance(storage, LocalDiskStorage)
    signed = await storage.signed_url(KEY, disposition="attachment")
    assert signed.url.startswith(f"{APP_URL}/api/files/")


async def test_create_storage_s3_signs_with_the_public_endpoint(
    core_settings: CoreSettings, fake_clock: FakeClock
) -> None:
    storage = create_storage(s3_settings(), core_settings, fake_clock)

    assert isinstance(storage, S3Storage)
    signed = await storage.signed_url(KEY, disposition="attachment")
    assert urlsplit(signed.url).netloc == urlsplit(PUBLIC_ENDPOINT).netloc
    assert signed.url.startswith("https://")


def s3_settings(public_endpoint: str = PUBLIC_ENDPOINT) -> StorageSettings:
    """`StorageSettings` S3 hợp lệ với `S3_PUBLIC_ENDPOINT` chọn được."""
    return StorageSettings(
        storage_backend="s3",
        s3_endpoint="http://minio:9000",
        s3_public_endpoint=public_endpoint,
        s3_bucket="appback",
        s3_access_key="key",
        s3_secret_key=SecretStr("secret"),
    )


def app_settings(app_env: Literal["dev", "test", "ci", "staging", "production"]) -> CoreSettings:
    """`CoreSettings` của API ở `app_env`, `PUBLIC_BASE_URL=APP_URL`."""
    return CoreSettings(app_env=app_env, public_base_url=APP_URL, secret_key=SecretStr("k" * 32))


@pytest.mark.parametrize("app_env", ["staging", "production"])
def test_create_storage_rejects_s3_on_the_app_origin(
    app_env: Literal["staging", "production"], fake_clock: FakeClock
) -> None:
    """BE-00 §8, K15: API ra ngoài với S3 cùng origin (không `nosniff`) không dựng được kho."""
    with pytest.raises(ValueError, match="khác origin"):
        create_storage(s3_settings(APP_URL), app_settings(app_env), fake_clock)


def test_create_storage_accepts_s3_on_another_origin_in_production(fake_clock: FakeClock) -> None:
    assert isinstance(create_storage(s3_settings(), app_settings("production"), fake_clock), S3Storage)


def test_create_storage_lets_dev_share_the_origin(fake_clock: FakeClock) -> None:
    """Ở dev/test cùng origin vẫn chạy được: rủi ro chỉ có thật khi ra ngoài."""
    assert isinstance(create_storage(s3_settings(APP_URL), app_settings("dev"), fake_clock), S3Storage)


def test_create_storage_without_core_settings_builds_s3(fake_clock: FakeClock) -> None:
    """Tiến trình không ký URL cho app (`ml`, NO-085) dựng kho S3 mà không cần `CoreSettings`."""
    assert isinstance(create_storage(s3_settings(), None, fake_clock), S3Storage)


async def test_create_storage_without_core_settings_refuses_to_sign_locally(
    fake_clock: FakeClock, tmp_path: Path
) -> None:
    """Kho local không có `PUBLIC_BASE_URL` vẫn ghi/đọc được nhưng không phát URL tương đối."""
    storage = create_storage(
        StorageSettings(storage_backend="local", storage_local_root=str(tmp_path)), None, fake_clock
    )
    await storage.put(KEY, b"x", content_type="application/octet-stream", max_bytes=1)

    assert await storage.stat(KEY) is not None
    with pytest.raises(RuntimeError, match="PUBLIC_BASE_URL"):
        await storage.signed_url(KEY, disposition="attachment")
