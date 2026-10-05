"""Ranh giới nhập của bốn module worker của `apps.api.spatial_write` (BE-00 §7, B3-03 [8] "Ranh giới").

`apps/worker` nhập `jobs.py` để chạy beat, và ảnh worker **không cài** `fastapi`, `starlette`,
`jwt`, `argon2`. `writer.py`/`changes.py` cũng phải nhập được trong ngữ cảnh đó vì `jobs.py`
không nhập chúng nhưng B3-03 [2] xếp cả ba (kèm `errors.py`) vào "hàm cho prompt sau" mà lịch
nền có thể cần gọi. Một lời nhập gián tiếp chỉ lộ ra khi bốn gói ấy thật sự vắng mặt, nên phép
kiểm phải chạy ở **tiến trình con** chứ không trong pytest (nơi cả bốn đã nạp sẵn).

`router`, `schemas` (việc R) được miễn: chúng là lớp HTTP, không ai nhập từ worker.
"""

import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest

from packages.testing.boundary import WORKER_BLOCKED

REPO_ROOT: Final = Path(__file__).resolve().parents[4]

WORKER_SAFE_MODULES: Final = (
    "apps.api.spatial_write.writer",
    "apps.api.spatial_write.changes",
    "apps.api.spatial_write.errors",
    "apps.api.spatial_write.jobs",
)
"""Bốn gói của B3-03 [8] "Ranh giới": writer, changes, errors, jobs."""


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


@pytest.mark.parametrize("module", WORKER_SAFE_MODULES)
def test_module_imports_without_web_or_crypto_packages(module: str) -> None:
    """Nhập được khi `fastapi`, `starlette`, `jwt`, `argon2` bị chặn — đủ bốn gói."""
    blocked = "; ".join(f"sys.modules[{name!r}] = None" for name in WORKER_BLOCKED)
    result = _python(f"import sys; {blocked}; import {module}")
    assert result.returncode == 0, result.stderr
