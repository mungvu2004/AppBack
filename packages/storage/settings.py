"""Cấu hình kho object. Nơi **duy nhất** đọc `STORAGE_*` và `S3_*`.

`S3_REGION` bắt buộc (mặc định `us-east-1`) để ký URL không phải hỏi
`GetBucketLocation`; `S3_PUBLIC_ENDPOINT` là địa chỉ **trình duyệt** thấy, khác
`S3_ENDPOINT` nội bộ.

Không đọc `CoreSettings`: dịch vụ `ml` nạp lớp này mà không có `SECRET_KEY`,
`PUBLIC_BASE_URL` (NO-085). Luật khác origin của BE-00 §8 cần cả `PUBLIC_BASE_URL`
nên kiểm ở `create_storage`, nơi có `CoreSettings` (FIX-105).
"""

from functools import cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_S3_FIELDS = ("s3_endpoint", "s3_public_endpoint", "s3_bucket", "s3_access_key")


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
        """Kiểm đủ trường cho backend đang chọn; endpoint S3 là URL tuyệt đối."""
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
        return self


@cache
def get_storage_settings() -> StorageSettings:
    """`StorageSettings` đọc một lần mỗi tiến trình."""
    return StorageSettings()


def reset_storage_settings_cache() -> None:
    """Chỉ cho test và CLI: đọc lại biến môi trường ở lần gọi sau."""
    get_storage_settings.cache_clear()
