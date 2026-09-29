"""Fixture trỏ `apps.api.drawings.urls.signer()` vào kho của test (FIX-112).

`signer()` là cửa duy nhất để ký URL bản vẽ, và bất kỳ module nào đọc `floor.drawings` /
`drawing_pages` đều đi qua nó — kể cả ngoài request. Không cài kho của test thì `signer()` rơi
vào `_default_signer()`, mà hàm đó `@cache`: nó chỉ dựng được khi biến môi trường `STORAGE_*` có
mặt, **và** bản dựng xong nằm lại trong tiến trình. Hệ quả là một test không khai gì có thể xanh
chỉ vì một test khác trong cùng tiến trình đã làm ấm cache đó — đúng kiểu phụ thuộc thứ tự mà
`pytest -n` phá vỡ (bước 5 chia file sang tiến trình khác là đỏ ngay).

Fixture ở đây **không** `autouse`: module nào cần thì xin, để chỗ phụ thuộc hiện ra trong mã.
"""

from collections.abc import Iterator

import pytest

from apps.api.drawings.urls import use_signer
from packages.storage.local import LocalDiskStorage


@pytest.fixture
def drawing_signer(local_storage: LocalDiskStorage) -> Iterator[LocalDiskStorage]:
    """Cài kho của test cho `urls.signer()`, rồi gỡ — không để trạng thái rò sang test sau."""
    use_signer(local_storage)
    yield local_storage
    use_signer(None)
