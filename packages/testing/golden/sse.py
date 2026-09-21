"""Đọc byte SSE thô thành khung, theo đặc tả EventSource (B0-07 [6], H5; B4-01 dùng lại).

Test luồng phải kiểm **byte thật nhận được** (S03: không `event:`, có `id:`, `data:` là JSON
đúng schema; S04: `: ping`), nên bộ đọc giữ lại những gì trình duyệt sẽ bỏ qua: tên sự kiện
và chú thích. Luật (WHATWG HTML §9.2.6):

- dòng kết thúc bằng CRLF, LF hay CR; khung kết thúc bằng một dòng trống;
- `:` đầu dòng là chú thích; `tên: giá trị` bỏ **một** khoảng trắng sau dấu `:`;
- nhiều dòng `data:` nối bằng `\\n`; `id` chứa NUL bị bỏ; trường lạ (`retry`) bị bỏ;
- phần sau ngắt dòng cuối cùng là khung dở, bị bỏ (luồng còn đang gửi).
"""

import re
from dataclasses import dataclass
from typing import Final

_LINE_BREAK_RE: Final = re.compile(r"\r\n|\r|\n")


@dataclass(frozen=True, slots=True)
class SseFrame:
    """Một khung SSE; `data` rỗng khi khung chỉ có chú thích (heartbeat `: ping`)."""

    id: str | None
    data: str
    event: str | None
    comments: tuple[str, ...]


def _split_field(line: str) -> tuple[str, str]:
    """`(tên, giá trị)` của một dòng; chú thích có tên rỗng. Bỏ một khoảng trắng đầu giá trị."""
    name, _, value = line.partition(":")
    return name, value.removeprefix(" ")


def parse_sse(raw: bytes) -> list[SseFrame]:
    """Mọi khung **đã đủ** trong `raw`, theo thứ tự nhận; byte UTF-8 hỏng thành U+FFFD như trình duyệt."""
    frames: list[SseFrame] = []
    data: list[str] = []
    comments: list[str] = []
    fields: dict[str, str] = {}
    for line in _LINE_BREAK_RE.split(raw.decode("utf-8", errors="replace").removeprefix("﻿"))[:-1]:
        if line:
            name, value = _split_field(line)
            if name == "data":
                data.append(value)
            elif not name:
                comments.append(value)
            elif name == "event" or (name == "id" and "\0" not in value):
                fields[name] = value
            continue
        if data or comments or fields:
            frames.append(SseFrame(fields.get("id"), "\n".join(data), fields.get("event"), tuple(comments)))
        data, comments, fields = [], [], {}
    return frames
