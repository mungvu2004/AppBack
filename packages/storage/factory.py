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


def _origin(url: str) -> tuple[str, str]:
    """(scheme, host:port) của một URL — đơn vị để so origin."""
    parts = urlsplit(url)
    return parts.scheme, parts.netloc


def _check_public_origin(settings: StorageSettings, core_settings: CoreSettings) -> None:
    """S3 ở staging/production phải khác origin với app, không thì `ValueError` (BE-00 §8, K15).

    S3/MinIO không đặt được `X-Content-Type-Options: nosniff`, nên tệp người dùng chỉ an
    toàn khi nằm khác origin với app. Dev/test được chung origin: rủi ro chỉ có khi ra ngoài.
    """
    if (
        settings.storage_backend == "s3"
        and core_settings.app_env in ("staging", "production")
        and _origin(settings.s3_public_endpoint) == _origin(core_settings.public_base_url)
    ):
        raise ValueError("S3_PUBLIC_ENDPOINT phải khác origin với PUBLIC_BASE_URL ở staging/production")


def create_storage(settings: StorageSettings, core_settings: CoreSettings | None, clock: Clock) -> ObjectStorage:
    """Bộ điều hợp theo `STORAGE_BACKEND`; hai client S3 dùng chung một pool HTTP.

    `core_settings` là của app phát URL cho trình duyệt (API, việc nền của nó): có nó thì
    kiểm luật khác origin trước khi dựng. `None` cho tiến trình không ký URL — `ml` không
    cầm `SECRET_KEY`/`PUBLIC_BASE_URL` (NO-085); kho local khi đó từ chối `signed_url`.
    """
    if core_settings is not None:
        _check_public_origin(settings, core_settings)
    if settings.storage_backend == "local":
        base_url = None if core_settings is None else core_settings.public_base_url
        return LocalDiskStorage(Path(settings.storage_local_root), clock, base_url)
    pool = http_client()
    return S3Storage(
        client=minio_client(settings, settings.s3_endpoint, pool),
        public_client=minio_client(settings, settings.s3_public_endpoint, pool),
        bucket=settings.s3_bucket,
        clock=clock,
    )
