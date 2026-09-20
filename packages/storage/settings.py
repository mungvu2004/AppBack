"""Cấu hình kho object. Nơi **duy nhất** đọc `STORAGE_*` và `S3_*`.

`S3_REGION` bắt buộc (mặc định `us-east-1`) để ký URL không phải hỏi
`GetBucketLocation`; `S3_PUBLIC_ENDPOINT` là địa chỉ **trình duyệt** thấy, khác
`S3_ENDPOINT` nội bộ.
"""

from functools import cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from packages.core.settings import get_core_settings

_S3_FIELDS = ("s3_endpoint", "s3_public_endpoint", "s3_bucket", "s3_access_key")


def _origin(url: str) -> tuple[str, str]:
    """(scheme, host:port) của một URL — đơn vị để so origin."""
    parts = urlsplit(url)
    return parts.scheme, parts.netloc


def _check_endpoint(name: str, url: str) -> None:
    """Endpoint phải là URL tuyệt đối http(s) không có đường dẫn."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc or parts.path or parts.query:
        raise ValueError(f"{name.upper()} phải là URL tuyệt đối http(s), không có đường dẫn: {url!r}")


class StorageSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", env_file=None)

    storage_backend: Literal["local", "s3"]
    storage_local_root: str = ""
    s3_endpoint: str = ""
    s3_public_endpoint: str = ""
    s3_bucket: str = ""
    s3_access_key: str = ""
    s3_secret_key: SecretStr = SecretStr("")
    s3_region: str = "us-east-1"

    @model_validator(mode="after")
    def _backend_fields(self) -> "StorageSettings":
        """Kiểm đủ trường cho backend đang chọn và luật khác origin của BE-00 §8."""
        if self.storage_backend == "local":
            if not self.storage_local_root:
                raise ValueError("STORAGE_LOCAL_ROOT bắt buộc khi STORAGE_BACKEND=local")
            return self
        missing = [name for name in _S3_FIELDS if not getattr(self, name)]
        if not self.s3_secret_key.get_secret_value():
            missing.append("s3_secret_key")
        if missing:
            raise ValueError(f"thiếu cấu hình S3: {', '.join(name.upper() for name in missing)}")
        for name in ("s3_endpoint", "s3_public_endpoint"):
            _check_endpoint(name, str(getattr(self, name)))
        core = get_core_settings()
        # S3/MinIO không đặt được `X-Content-Type-Options: nosniff`, nên tệp người
        # dùng chỉ an toàn khi nằm khác origin với app (BE-00 §8, K15).
        if core.app_env in ("staging", "production") and _origin(self.s3_public_endpoint) == _origin(
            core.public_base_url
        ):
            raise ValueError("S3_PUBLIC_ENDPOINT phải khác origin với PUBLIC_BASE_URL ở staging/production")
        return self


@cache
def get_storage_settings() -> StorageSettings:
    """`StorageSettings` đọc một lần mỗi tiến trình."""
    return StorageSettings()


def reset_storage_settings_cache() -> None:
    """Chỉ cho test và CLI: đọc lại biến môi trường ở lần gọi sau."""
    get_storage_settings.cache_clear()
