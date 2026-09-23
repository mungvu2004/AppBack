"""Đọc mảng `export const <TÊN> = [...] as const` từ một file `.ts` của AppFront (R-07).

Dùng chung cho mọi test gương FE của `apps/api/telemetry` — không phải test, pytest
không thu thập (không có tiền tố `test_`).
"""

import re
from pathlib import Path

import pytest

_TS_ARRAY_RE = re.compile(r"export const (\w+) = \[(.*?)\] as const", re.DOTALL)


def read_ts_array(path: Path, name: str) -> list[str]:
    """Chuỗi bên trong khối `export const <name> = [...] as const` của `path`.

    Không tìm thấy khối → test hỏng ngay (`pytest.fail`), không bỏ qua (K24).
    """
    text = path.read_text(encoding="utf-8")
    for match_name, block in _TS_ARRAY_RE.findall(text):
        if match_name == name:
            return re.findall(r"'([^']*)'", block)
    pytest.fail(f"không tìm thấy khối 'export const {name} = [...] as const' trong {path}")
