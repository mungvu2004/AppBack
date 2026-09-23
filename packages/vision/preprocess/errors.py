"""Lỗi của gói ảnh: `VisionError` mang đúng một mã lõi 422 của B0-02.

Gói không khai mã mới (khối [2] B2-05a); tầng gọi đổi sang `AppError` bằng
`to_app_error()` để handler W7 dựng thân lỗi.
"""

from typing import Final, Literal

from packages.core import error_codes
from packages.core.errors import AppError, ErrorCode

VisionErrorCode = Literal["IMAGE_TOO_LARGE", "PDF_UNREADABLE", "FILE_CORRUPT", "FILE_TYPE_MISMATCH", "VALIDATION"]

_CODES: Final[dict[str, ErrorCode]] = {
    "IMAGE_TOO_LARGE": error_codes.IMAGE_TOO_LARGE,
    "PDF_UNREADABLE": error_codes.PDF_UNREADABLE,
    "FILE_CORRUPT": error_codes.FILE_CORRUPT,
    "FILE_TYPE_MISMATCH": error_codes.FILE_TYPE_MISMATCH,
    "VALIDATION": error_codes.VALIDATION,
}


class VisionError(Exception):
    """Lỗi dữ liệu vào của gói ảnh; `str(e) == code`.

    `field` là tên trường dây (`pageIndex`, `corners`) khi lỗi gắn với một tham số
    người gọi truyền; `None` khi lỗi thuộc về chính tệp. Mã lạ → `ValueError`
    (lỗi lập trình, không phải lỗi dữ liệu).
    """

    def __init__(self, code: VisionErrorCode, *, field: str | None = None) -> None:
        """Chốt `code` thuộc đúng 5 mã của bảng và đặt `str(e) == code`; mã lạ → `ValueError`
        vì gõ sai mã là lỗi lập trình, không phải lỗi dữ liệu vào cần trả 422."""
        if code not in _CODES:
            raise ValueError(f"mã lỗi ảnh lạ: {code!r}")
        super().__init__(code)
        self.code: Final = code
        self.field: Final = field

    def to_app_error(self) -> AppError:
        """Đổi sang `AppError` qua hằng của `packages.core.error_codes` (giữ `field`)."""
        error_code = _CODES[self.code]
        return error_code.error() if self.field is None else error_code.error(field=self.field)
