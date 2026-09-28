"""Câu ghi chú người đọc của phiên bản sinh tự động (B3-04 [6] "Câu người đọc").

Tiếng Việt viết thường; `n` viết liền, không dấu nhóm (`v1000`). `after_note` khớp
`versionHistoryGateway.ts:313` của FE. Module không nhập gì của HTTP (worker gọi được).
"""


def after_note(n: int) -> str:
    """Ghi chú bản "sau" của một lượt phục hồi từ phiên bản thứ `n`."""
    return f"phục hồi nội dung của phiên bản v{n}"


def before_note(n: int) -> str:
    """Ghi chú bản "trước" của một lượt phục hồi từ phiên bản thứ `n`."""
    return f"trạng thái trước khi phục hồi phiên bản v{n}"


def before_pipeline_note() -> str:
    """Ghi chú bản "trước" khi pipeline AI ghi đè lớp (B5-06b)."""
    return "trạng thái trước khi ghi kết quả AI"
