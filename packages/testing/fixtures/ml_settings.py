"""Cache `get_ml_settings` sạch quanh **mọi** test (NO-312).

`get_ml_settings` là `lru_cache` theo tiến trình. Test vá `ML_DEVICE=cuda` bằng `monkeypatch`
rồi để ai đó gọi nó lần đầu là ghim `cuda` vào cache cả tiến trình — `monkeypatch` trả biến môi
trường nhưng **không** trả cache, nên mọi test sau trong cùng worker xdist thấy `cuda` (6 test
`training_runner` đỏ `ML_DEVICE_UNAVAILABLE`). Fixture autouse ở đây xoá cache *trước* (test không
phụ thuộc ai chạy trước) và *sau* (test không làm bẩn người sau), nên mọi tệp khỏi tự lo.
"""

from collections.abc import Iterator

import pytest

from apps.ml.runtime.settings import reset_ml_settings_cache


@pytest.fixture(autouse=True)
def ml_settings_cache() -> Iterator[None]:
    """Xoá cache `get_ml_settings` trước và sau mỗi test."""
    reset_ml_settings_cache()
    yield
    reset_ml_settings_cache()
