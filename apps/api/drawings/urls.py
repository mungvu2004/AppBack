"""Kho object dùng để **ký URL** bản vẽ, tách khỏi `drawings.py` vì hai lý do.

`create_storage` kéo `minio` → `argon2` lúc nhập, nên nó chỉ được nhập trong thân hàm
(mẫu `apps/api/floors/jobs.py`). Và cổng `floor.drawings`/`drawing_pages` được gọi ngoài
request (không có `app.state.storage`), nên phải có một kho dựng lười theo tiến trình.

`use_signer` là cửa duy nhất để test trỏ vào `local_storage` của mình; nó từ chối chạy
ngoài `APP_ENV=test` để không ai thay kho của production lúc chạy thật.
"""

from functools import cache

from packages.core.clock import SystemClock
from packages.core.settings import get_core_settings
from packages.storage.port import ObjectStorage

_test_signer: ObjectStorage | None = None


@cache
def _default_signer() -> ObjectStorage:
    """Kho theo biến môi trường, dựng **một** lần mỗi tiến trình (client S3 không rẻ)."""
    from packages.storage.factory import create_storage
    from packages.storage.settings import get_storage_settings

    return create_storage(get_storage_settings(), get_core_settings(), SystemClock())


def signer() -> ObjectStorage:
    """Kho để ký URL bản vẽ; bản test đã cài (`use_signer`) thắng bản theo môi trường."""
    return _test_signer if _test_signer is not None else _default_signer()


def use_signer(storage: ObjectStorage | None) -> None:
    """Cài (hay gỡ, với `None`) kho của test; ngoài `APP_ENV=test` → `RuntimeError`."""
    if get_core_settings().app_env != "test":
        raise RuntimeError("use_signer chỉ dùng khi APP_ENV=test")
    global _test_signer  # một kho mỗi tiến trình, như `_executor` của B0-03
    _test_signer = storage
