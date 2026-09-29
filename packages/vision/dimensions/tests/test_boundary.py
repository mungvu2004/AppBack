"""Ranh giới nhập (BE-00 §2.1, §12): `packages.vision.dimensions` nhập được khi tầng ML/DB bị chặn lúc chạy."""

import subprocess
import sys
from typing import Final

import pytest

_BLOCKED: Final = ("torch", "onnxruntime", "rapidocr_onnxruntime", "sqlalchemy")
_TIMEOUT_S: Final = 120

_SCRIPT: Final = f"""
import sys

for name in {_BLOCKED!r}:
    sys.modules[name] = None

import packages.vision.dimensions as dimensions

assert dimensions.__all__
assert dimensions.parse_length_mm("3.500") == 3500
assert dimensions.match_room_label("WC").name == "phòng tắm"
print("ok")
"""


def _run(script: str) -> subprocess.CompletedProcess[str]:
    """Chạy `script` trong tiến trình con sạch của chính Python venv."""
    return subprocess.run(  # noqa: S603 — lệnh cố định
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=_TIMEOUT_S, check=False
    )


def test_package_imports_with_ml_and_db_blocked() -> None:
    """Nhập và gọi hàm khi bốn thư viện bị chặn → thoát 0."""
    result = _run(_SCRIPT)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("ok")


@pytest.mark.parametrize("name", _BLOCKED)
def test_blocking_really_raises(name: str) -> None:
    """Phép chặn có tác dụng: nhập chính module bị chặn trong tiến trình con → lỗi."""
    result = _run(f"import sys; sys.modules[{name!r}] = None; import {name}")
    assert result.returncode != 0
    assert "halted; None in sys.modules" in result.stderr
