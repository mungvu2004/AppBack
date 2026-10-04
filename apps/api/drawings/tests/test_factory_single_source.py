"""Nguồn đơn của bảng đuôi tệp → loại/MIME: factory bản vẽ nhập từ `uploads`, không chép lại (NO-219, R-07)."""

from apps.api.drawings import uploads
from packages.testing.factories import drawings as factory


def test_drawings_factory__ext_maps_come_from_uploads() -> None:
    """Factory dùng chính `uploads.EXT_KIND`/`KIND_MIME`, và không còn bảng `_EXT_KIND`/`_EXT_TYPE` riêng."""
    assert vars(factory)["EXT_KIND"] is uploads.EXT_KIND
    assert vars(factory)["KIND_MIME"] is uploads.KIND_MIME
    assert not hasattr(factory, "_EXT_KIND")
    assert not hasattr(factory, "_EXT_TYPE")
