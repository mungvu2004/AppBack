"""Ranh giới nhập của ba module worker của `apps.api.versions` (BE-00 §7, B3-04 [8]).

B5-06b gọi `create_version` trong ảnh worker, nơi **không cài** `fastapi`, `starlette`, `jwt`,
`argon2`. Một lời nhập gián tiếp chỉ lộ ra khi bốn gói ấy thật sự vắng, nên phép kiểm chạy ở
**tiến trình con** (trong pytest cả bốn đã nạp sẵn). `router`, `schemas`, `service` (việc R) được
miễn: chúng là lớp HTTP.
"""

import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest

from packages.testing.boundary import WORKER_BLOCKED

REPO_ROOT: Final = Path(__file__).resolve().parents[4]
WORKER_SAFE_MODULES: Final = (
    "apps.api.versions.snapshots",
    "apps.api.versions.messages",
    "apps.api.versions.errors",
)


@pytest.mark.parametrize("module", WORKER_SAFE_MODULES)
def test_module_imports_without_web_or_crypto_packages(module: str) -> None:
    """Nhập được khi `fastapi`, `starlette`, `jwt`, `argon2` bị chặn — đủ bốn gói."""
    blocked = "; ".join(f"sys.modules[{name!r}] = None" for name in WORKER_BLOCKED)
    result = subprocess.run(  # noqa: S603 — trình thông dịch của chính tiến trình test, mã cố định
        [sys.executable, "-c", f"import sys; {blocked}; import {module}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
