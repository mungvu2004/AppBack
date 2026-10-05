"""Ranh giới nhập (BE-00 §2.1, §12): `packages.vision.walls` và module con nhập được khi
tầng ML/DB/hàng đợi và hợp đồng `packages.ml_contracts` bị chặn lúc chạy (B5-02 [8]).

Mọi module con của gói đều nằm trong danh sách: nhánh gộp có đủ cả bốn, nên thiếu một cái
là test đỏ chứ không còn bỏ qua (K24 — test bị skip là hỏng ở cổng).
"""

import subprocess
import sys
from typing import Final

import pytest

_BLOCKED: Final = ("torch", "onnxruntime", "celery", "sqlalchemy", "packages.ml_contracts")
_MODULES: Final = (
    "packages.vision.walls",
    "packages.vision.walls.classic",
    "packages.vision.walls.metrics",
    "packages.vision.walls.vectorize",
    "packages.vision.walls.types",
)
_TIMEOUT_S: Final = 120

_SCRIPT: Final = """
import importlib
import sys

for name in {blocked!r}:
    sys.modules[name] = None

module = importlib.import_module({module!r})
print("ok")
"""


def _run(module: str) -> subprocess.CompletedProcess[str]:
    """Nhập `module` trong tiến trình con sạch với `ml_contracts` bị chặn bằng `sys.modules`."""
    script = _SCRIPT.format(blocked=_BLOCKED, module=module)
    return subprocess.run(  # noqa: S603 — lệnh cố định
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=_TIMEOUT_S, check=False
    )


@pytest.mark.parametrize("module", _MODULES)
def test_module_imports_with_ml_and_db_blocked(module: str) -> None:
    """Nhập mỗi module con khi bốn thư viện ML/DB và `packages.ml_contracts` bị chặn → thoát 0."""
    result = _run(module)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("ok")


@pytest.mark.parametrize("name", _BLOCKED)
def test_blocking_really_raises(name: str) -> None:
    """Phép chặn có tác dụng: nhập chính module bị chặn trong tiến trình con → lỗi."""
    result = subprocess.run(  # noqa: S603 — lệnh cố định, tên lấy từ `_BLOCKED`
        [sys.executable, "-c", f"import sys; sys.modules[{name!r}] = None; import {name}"],
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_S,
        check=False,
    )
    assert result.returncode != 0
