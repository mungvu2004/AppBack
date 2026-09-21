"""Email trên dây và khoá Redis của email (BE-00 §5, §11, K37).

- `validate_wire_email` nhận **đúng** tập email mà `z.string().email()` của zod 3.23.8
  nhận (FE giải mọi email bằng nó, `src/api/schemas/index.ts:66`): cùng regex, cờ
  `re.IGNORECASE | re.ASCII`. Thiếu `re.ASCII` thì `re.I` của Python cho chữ s dài (U+017F)
  khớp `s` và dấu Kelvin (U+212A) khớp `k` — email Unicode lọt vào DB làm màn quản trị người
  dùng hỏng giải mã cả danh sách (K37). Không dùng `EmailStr` (nhận Unicode, cần gói ngoài).
- `email_key` là HMAC khoá `lookup` của email chuẩn hoá: khoá Redis không bao giờ chứa
  email thô hay SHA-256 trần, thứ dò ngược được bằng từ điển (K11).
"""

import hashlib
import hmac
import re
from typing import Final

from packages.core.keys import current_key
from packages.core.text import nfc, normalize_email

MAX_EMAIL_LENGTH: Final = 254
EMAIL_KEY_HEX: Final = 32

# Regex `.email()` của zod 3.23.8 (`emailRegex`, types.ts), chép nguyên; độ dài bị chặn ở
# 254 trước khi khớp, nên nhóm lặp `(...\.)+` không có đầu vào nào đủ dài để thành ReDoS.
_ZOD_EMAIL: Final = re.compile(
    r"(?!\.)(?!.*\.\.)([A-Z0-9_'+\-\.]*)[A-Z0-9_+-]@([A-Z0-9][A-Z0-9\-]*\.)+[A-Z]{2,}",
    re.IGNORECASE | re.ASCII,
)


def validate_wire_email(value: str) -> str:
    """Email hợp lệ theo FE → bản `nfc(strip)` để lưu; sai → `ValueError` (Pydantic ra 422).

    Thứ tự: trim, ASCII, độ dài, rồi mới regex — kiểm rẻ trước, và `isascii()` chặn cả
    chữ số hay chữ cái Unicode mà một regex không `re.ASCII` sẽ nhận nhầm.
    """
    trimmed = value.strip()
    if not trimmed or not trimmed.isascii() or len(trimmed) > MAX_EMAIL_LENGTH:
        raise ValueError("email sai dạng")
    if _ZOD_EMAIL.fullmatch(trimmed) is None:
        raise ValueError("email sai dạng")
    return nfc(trimmed)


def email_key(email: str) -> str:
    """HMAC-SHA256 (khoá `lookup`) của `normalize_email(email)`, 32 ký tự hex đầu."""
    digest = hmac.new(current_key("lookup"), normalize_email(email).encode("utf-8"), hashlib.sha256)
    return digest.hexdigest()[:EMAIL_KEY_HEX]
