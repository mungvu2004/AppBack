"""`create_storage` chọn đúng bộ điều hợp và đúng địa chỉ ký."""

from pathlib import Path
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
    settings = StorageSettings(
        storage_backend="s3",
        s3_endpoint="http://minio:9000",
        s3_public_endpoint=PUBLIC_ENDPOINT,
        s3_bucket="appback",
        s3_access_key="key",
        s3_secret_key=SecretStr("secret"),
    )

    storage = create_storage(settings, core_settings, fake_clock)

    assert isinstance(storage, S3Storage)
    signed = await storage.signed_url(KEY, disposition="attachment")
    assert urlsplit(signed.url).netloc == urlsplit(PUBLIC_ENDPOINT).netloc
    assert signed.url.startswith("https://")
