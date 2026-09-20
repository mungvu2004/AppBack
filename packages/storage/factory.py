"""`create_storage` — chọn bộ điều hợp theo `STORAGE_BACKEND` (BE-00 §7, §8)."""

from pathlib import Path
from urllib.parse import urlsplit

import urllib3
from minio import Minio

from packages.core.clock import Clock
from packages.core.settings import CoreSettings
from packages.storage.local import LocalDiskStorage
from packages.storage.port import ObjectStorage
from packages.storage.s3 import S3Storage, http_client
from packages.storage.settings import StorageSettings


def minio_client(settings: StorageSettings, endpoint: str, pool: urllib3.PoolManager) -> Minio:
    """Client `minio` cho một endpoint; vùng ghim nên ký URL không phải hỏi S3."""
    parts = urlsplit(endpoint)
    return Minio(
        parts.netloc,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key.get_secret_value(),
        secure=parts.scheme == "https",
        region=settings.s3_region,
        http_client=pool,
    )


def create_storage(settings: StorageSettings, core_settings: CoreSettings, clock: Clock) -> ObjectStorage:
    """Bộ điều hợp theo `STORAGE_BACKEND`; hai client S3 dùng chung một pool HTTP."""
    if settings.storage_backend == "local":
        return LocalDiskStorage(Path(settings.storage_local_root), clock, core_settings.public_base_url)
    pool = http_client()
    return S3Storage(
        client=minio_client(settings, settings.s3_endpoint, pool),
        public_client=minio_client(settings, settings.s3_public_endpoint, pool),
        bucket=settings.s3_bucket,
        clock=clock,
    )
