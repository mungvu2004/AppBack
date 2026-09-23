"""`VisionError` mang đúng một mã lõi 422 và đổi được sang `AppError` của W7."""

import pytest

from packages.core import error_codes
from packages.vision.preprocess.errors import VisionError, VisionErrorCode

_CASES: list[tuple[VisionErrorCode, object]] = [
    ("IMAGE_TOO_LARGE", error_codes.IMAGE_TOO_LARGE),
    ("PDF_UNREADABLE", error_codes.PDF_UNREADABLE),
    ("FILE_CORRUPT", error_codes.FILE_CORRUPT),
    ("FILE_TYPE_MISMATCH", error_codes.FILE_TYPE_MISMATCH),
    ("VALIDATION", error_codes.VALIDATION),
]


@pytest.mark.parametrize(("code", "error_code"), _CASES)
def test_vision_error_str_is_code(code: VisionErrorCode, error_code: object) -> None:
    """`str(e)` là chính mã, để log và assert không phải bóc thuộc tính."""
    error = VisionError(code)
    assert str(error) == code
    assert error.code == code
    assert error.field is None
    assert error.to_app_error().code is error_code


def test_vision_error_field_reaches_app_error_params() -> None:
    """`field` đi thẳng vào `params` để FE tô đúng ô nhập (W7)."""
    app_error = VisionError("VALIDATION", field="pageIndex").to_app_error()
    assert app_error.code is error_codes.VALIDATION
    assert app_error.params == {"field": "pageIndex"}


def test_vision_error_unknown_code_is_programming_error() -> None:
    """Mã lạ là lỗi lập trình → `ValueError`, không phải lỗi dữ liệu người dùng."""
    with pytest.raises(ValueError, match="mã lỗi ảnh lạ"):
        VisionError("NOPE")  # type: ignore[arg-type]  # cố ý truyền mã ngoài Literal để chốt lỗi lúc chạy
