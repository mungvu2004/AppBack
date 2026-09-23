"""Ranh giới nhập (BE-00 §2.1): hai gói ảnh nhập được khi không có tầng web/DB/ML.

`.importlinter` đã chặn ở bước 4 theo tên module; test này chốt thêm ở lúc **chạy**:
chặn `sqlalchemy`, `fastapi`, `celery`, `torch` bằng `sys.modules[name] = None` rồi
nhập hai gói trong một tiến trình con sạch — nhập nhầm sẽ ném `ImportError`.
"""

import subprocess
import sys
from typing import Final

import pytest

_BLOCKED: Final = ("sqlalchemy", "fastapi", "celery", "torch")
_PACKAGES: Final = ("packages.vision.preprocess", "packages.vision.quality")
_TIMEOUT_S: Final = 120

_SCRIPT: Final = f"""
import sys

for name in {_BLOCKED!r}:
    sys.modules[name] = None

import importlib

for package in {_PACKAGES!r}:
    module = importlib.import_module(package)
    assert module.__all__, package

from packages.vision.preprocess import sniff_kind
from packages.vision.quality import QUALITY_CODES, assess

assert sniff_kind(b"") == "unknown"
assert len(QUALITY_CODES) == 5
assert callable(assess)
print("ok")
"""


def _run_child() -> subprocess.CompletedProcess[str]:
    """Chạy `_SCRIPT` trong một tiến trình con `python -c` (không kế thừa module đã nạp)."""
    return subprocess.run(  # noqa: S603 — lệnh cố định, chạy chính Python của venv
        [sys.executable, "-c", _SCRIPT],
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_S,
        check=False,
    )


def test_packages_import_without_web_db_and_ml_layers() -> None:
    """Nhập `preprocess` và `quality` với bốn thư viện tầng khác bị chặn → được."""
    result = _run_child()
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("ok")


@pytest.mark.parametrize("name", _BLOCKED)
def test_blocked_module_really_raises_in_child(name: str) -> None:
    """Chốt chính phép chặn có tác dụng: nhập module bị chặn trong tiến trình con → chặn thật.

    Không có test này thì test trên vẫn xanh kể cả khi `sys.modules[name] = None`
    không chặn được gì, tức phép kiểm ranh giới thành vô nghĩa.
    """
    script = f"import sys; sys.modules[{name!r}] = None; import {name}"
    result = subprocess.run(  # noqa: S603 — lệnh cố định, chạy chính Python của venv
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=_TIMEOUT_S, check=False
    )
    assert result.returncode != 0
    assert "halted; None in sys.modules" in result.stderr
