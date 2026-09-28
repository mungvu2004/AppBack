"""Câu tiếng Việt của thông báo và làm sạch nhãn (B4-02 [6] "Câu"; BE-00 §10).

FE in `{message}` rồi liên kết `{objectLabel}` ngay sau, nên câu **không** lặp lại nhãn ở cuối.
Không nhập `fastapi`, `jwt`, `argon2` (B5-06b gọi qua `notify`).
"""

import unicodedata
from typing import Final

from packages.core.text import nfc

LABEL_MAX: Final = 200
_INVISIBLE: Final = frozenset({"Cc", "Cf"})
"""Loại `Cc` (điều khiển) và `Cf` (định dạng): gồm `U+202A-U+202E`, `U+2066-U+2069`, ký tự rộng 0."""


def clean_label(value: str, *, max_len: int = LABEL_MAX) -> str:
    """NFC, bỏ ký tự `Cc`/`Cf`, gộp khoảng trắng, cắt `max_len`; có thể trả rỗng (người gọi quyết)."""
    spaced = "".join(" " if ch.isspace() else ch for ch in value)  # xuống dòng, tab là khoảng trắng chứ không phải rác
    kept = "".join(ch for ch in spaced if unicodedata.category(ch) not in _INVISIBLE)
    return " ".join(nfc(kept).split())[:max_len].rstrip()


def project_invite(actor_name: str | None) -> str:
    """Người thêm có tên → nêu tên; không tên (đã xoá mềm hoặc tên rỗng sau làm sạch) → câu vô danh."""
    name = clean_label(actor_name) if actor_name else ""
    return f"{name} đã thêm bạn vào dự án" if name else "bạn vừa được thêm vào dự án"


def ai_completed() -> str:
    """AI xong bản vẽ; FE nối tên tầng."""
    return "hệ thống AI đã xử lý xong bản vẽ"


def violation_found(count: int) -> str:
    """`count` ≥ 1, nhóm nghìn bằng dấu chấm (`1.234`); `count < 1` là lỗi lập trình."""
    if count < 1:
        raise ValueError(f"count phải ≥ 1, nhận {count}")
    return f"phát hiện {count:,} vi phạm luật ở".replace(",", ".")
