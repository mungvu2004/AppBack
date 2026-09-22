"""Đường gốc repo và trợ giúp chung cho test tĩnh B0-08 — không phải test.

File Docker/compose/nginx/MinIO đích thuộc ba worker khác chạy song song và
**chưa có** trên nhánh này (B0-08 chỉ viết test theo hợp đồng). Test phải `fail`
với thông điệp "thiếu <file>" khi file chưa tồn tại — không `skip`/`xfail` (K24,
hợp đồng B0-08 §1).
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def require_path(relative: str) -> Path:
    """Trả đường tuyệt đối `REPO_ROOT/relative`; `fail` rõ ràng nếu chưa tồn tại."""
    path = REPO_ROOT / relative
    if not path.exists():
        pytest.fail(f"thiếu {relative}")
    return path
