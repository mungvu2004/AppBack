"""Ranh giới nhập của `apps.api.floors.jobs` (BE-00 §12, B2-03 [6] "Khác"): tiến trình Python mới."""

import subprocess
import sys
from pathlib import Path
from typing import Final

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


def test_jobs_imports_without_web_or_crypto_packages() -> None:
    """Worker nhập được `apps.api.floors.jobs` khi `fastapi`, `starlette`, `jwt`, `argon2` bị chặn."""
    blocked = "; ".join(f"sys.modules[{name!r}] = None" for name in WORKER_BLOCKED)
    result = _python(f"import sys; {blocked}; import apps.api.floors.jobs")
    assert result.returncode == 0, result.stderr
