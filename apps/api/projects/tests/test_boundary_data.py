"""Ranh giới nhập của `apps.api.projects.{memberships,summaries}` (BE-00 §7): tiến trình Python mới.

Worker B5-06a/b nhập hai module này ngoài tiến trình API, nơi `fastapi`, `starlette`, `jwt`,
`argon2` có thể không cài. Chặn chúng trong `sys.modules` của **tiến trình con** là cách duy
nhất bắt được một import gián tiếp lọt qua (tiến trình test đã nạp sẵn cả bốn gói).
"""

import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest

REPO_ROOT: Final = Path(__file__).resolve().parents[4]
WORKER_BLOCKED: Final = ("fastapi", "starlette", "jwt", "argon2")


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


@pytest.mark.parametrize("module", ["apps.api.projects.memberships", "apps.api.projects.summaries"])
def test_data_modules_import_without_web_or_crypto_packages(module: str) -> None:
    """Nhập được khi `fastapi`, `starlette`, `jwt`, `argon2` bị chặn trong `sys.modules`."""
    blocked = "; ".join(f"sys.modules[{name!r}] = None" for name in WORKER_BLOCKED)
    result = _python(f"import sys; {blocked}; import {module}")
    assert result.returncode == 0, result.stderr
