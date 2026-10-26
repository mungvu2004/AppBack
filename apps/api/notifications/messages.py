"""Câu tiếng Việt của thông báo và làm sạch nhãn (B4-02 [6] "Câu"; BE-00 §10).

FE in `{message}` rồi liên kết `{objectLabel}` ngay sau, nên câu **không** lặp lại nhãn ở cuối.
Câu cố định viết hoa chữ đầu (luật chữ A6 của FE); câu mở bằng tên người giữ nguyên tên.
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
    return f"{name} đã thêm bạn vào dự án" if name else "Bạn vừa được thêm vào dự án"


def ai_completed(project_name: str | None = None) -> str:
    """AI xong bản vẽ; FE nối tên tầng. Có tên dự án (sau làm sạch) → mở câu bằng `Dự án <tên>:` (G1-13)."""
    name = clean_label(project_name) if project_name else ""
    sentence = "Hệ thống AI đã xử lý xong bản vẽ"
    return f"Dự án {name}: {sentence}" if name else sentence


def ai_failed(project_name: str | None = None) -> str:
    """AI không xử lý được bản vẽ; FE nối tên tầng (`objectLabel`) như `ai_completed`, nên câu không nêu tầng."""
    name = clean_label(project_name) if project_name else ""
    sentence = "AI chưa xử lý được bản vẽ"
    return f"Dự án {name}: {sentence}" if name else sentence


def violation_found(count: int) -> str:
    """`count` ≥ 1, nhóm nghìn bằng dấu chấm (`1.234`); `count < 1` là lỗi lập trình."""
    if count < 1:
        raise ValueError(f"count phải ≥ 1, nhận {count}")
    return f"Phát hiện {count:,} vi phạm luật ở".replace(",", ".")
