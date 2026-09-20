"""Fixture kho object (B0-04).

- `local_storage`: `LocalDiskStorage` trên `tmp_path` với `fake_clock` — module khác
  dùng nó làm kho cho test của mình.
- `s3_storage`: `S3Storage` trên MinIO **thật** (K23), bucket riêng mỗi test.
- `object_storage`: tham số hoá cả hai, cho bộ test hợp đồng.

`storage_env` đặt `SECRET_KEY` (token tệp của `LocalDiskStorage` ký bằng khoá con
`file`) và `PUBLIC_BASE_URL`; test cần giá trị khác thì `monkeypatch.setenv` trong
thân test rồi `reset_settings_cache()`.
"""

import secrets
from collections.abc import Iterator
from pathlib import Path

import pytest
from minio import Minio

from packages.core.settings import reset_settings_cache
from packages.storage.local import LocalDiskStorage
from packages.storage.port import ObjectStorage
from packages.storage.s3 import S3Storage, http_client
from packages.testing.fixtures.clock import FakeClock

PUBLIC_BASE_URL = "https://appback.test"
STORAGE_SECRET = "fixture-secret-for-storage-tests-0001"  # noqa: S105 — khoá giả của fixture


@pytest.fixture
def storage_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("PUBLIC_BASE_URL", PUBLIC_BASE_URL)
    monkeypatch.setenv("SECRET_KEY", STORAGE_SECRET)
    monkeypatch.delenv("SECRET_KEY_PREVIOUS", raising=False)
    reset_settings_cache()
    yield
    reset_settings_cache()


@pytest.fixture
def local_storage(tmp_path: Path, fake_clock: FakeClock, storage_env: None) -> LocalDiskStorage:
    return LocalDiskStorage(tmp_path / "objects", fake_clock, PUBLIC_BASE_URL)


@pytest.fixture
def s3_storage(minio_endpoint: tuple[str, str, str], fake_clock: FakeClock) -> S3Storage:
    endpoint, access_key, secret_key = minio_endpoint
    client = Minio(
        endpoint,
        access_key=access_key,
        secret_key=secret_key,
        secure=False,
        region="us-east-1",
        http_client=http_client(),
    )
    bucket = f"test-{secrets.token_hex(6)}"
    client.make_bucket(bucket)
    return S3Storage(client=client, public_client=client, bucket=bucket, clock=fake_clock)


@pytest.fixture(params=["local", "s3"])
def object_storage(request: pytest.FixtureRequest) -> ObjectStorage:
    storage: ObjectStorage = request.getfixturevalue(f"{request.param}_storage")
    return storage
