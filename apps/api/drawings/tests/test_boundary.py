"""Ranh giới nhập của nhóm "hàm worker nhập" trong `apps.api.drawings` (BE-00 §7, §12).

`jobs.py` chạy trong ảnh worker, mà ảnh ấy **không cài** `fastapi`, `starlette`, `jwt`,
`argon2` (`.importlinter`, contract `apps.api.*.jobs`). Bốn module nó gọi lại — `runs`,
`progress`, `drawings`, `scales` — vì thế cũng phải nhập được khi bốn gói kia vắng mặt:
một `from apps.api.core.deps import …` lọt vào bất kỳ file nào trong nhóm là lịch nền
chết lúc khởi động worker chứ không phải lúc chạy test.

`lint-imports` chỉ canh `jobs.py`; ở đây kiểm cả năm, và kiểm bằng **tiến trình Python
mới** để không bị đánh lừa bởi các module đã nằm sẵn trong `sys.modules` của pytest.
"""

import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest

REPO_ROOT: Final = Path(__file__).resolve().parents[4]
WORKER_BLOCKED: Final = ("fastapi", "starlette", "jwt", "argon2")
WORKER_MODULES: Final = ("jobs", "runs", "progress", "drawings", "scales")


def _python(code: str) -> subprocess.CompletedProcess[str]:
    """Chạy một đoạn Python ở gốc repo, trả kết quả (không ném khi mã thoát khác 0)."""
    return subprocess.run(  # noqa: S603 — trình thông dịch của chính tiến trình test, mã cố định
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


@pytest.mark.parametrize("module", WORKER_MODULES)
def test_worker_module_imports_without_web_or_crypto_packages(module: str) -> None:
    """Worker nhập được `apps.api.drawings.<module>` khi bốn gói của đường web bị chặn."""
    blocked = "; ".join(f"sys.modules[{name!r}] = None" for name in WORKER_BLOCKED)
    result = _python(f"import sys; {blocked}; import apps.api.drawings.{module}")
    assert result.returncode == 0, result.stderr
