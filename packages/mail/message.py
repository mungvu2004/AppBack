"""Thư cần gửi (B1-03 [2]).

Bất biến duy nhất: `to`, `subject` không chứa CR/LF — ngăn chèn header SMTP qua dữ
liệu người dùng (vd tên chứa `\\r\\nBcc: kẻ tấn công`). Định dạng email **không**
kiểm ở đây: người gọi (`validate_wire_email`) đã chuẩn hoá trước khi tới `packages.mail`.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MailMessage:
    """Một thư sắp gửi: `to`/`subject` chỉ văn bản một dòng, `text`/`html` là hai phần thân."""

    to: str
    subject: str
    text: str
    html: str

    def __post_init__(self) -> None:
        for field_name, value in (("to", self.to), ("subject", self.subject)):
            if "\r" in value or "\n" in value:
                raise ValueError(f"{field_name} không được chứa CR hay LF")
