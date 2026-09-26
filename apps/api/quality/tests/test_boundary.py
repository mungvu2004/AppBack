"""Ranh giới nhập của `apps.api.quality.assessments` (BE-00 §7 "Hàm worker nhập"): tiến trình Python mới."""

import subprocess
import sys
from pathlib import Path
from typing import Final

REPO_ROOT: Final = Path(__file__).resolve().parents[4]
WORKER_BLOCKED: Final = ("fastapi", "starlette", "jwt", "argon2")


def test_assessments_imports_without_web_or_crypto_packages() -> None:
    """Worker nhập được `apps.api.quality.assessments` khi `fastapi`, `starlette`, `jwt`, `argon2` bị chặn."""
    blocked = "; ".join(f"sys.modules[{name!r}] = None" for name in WORKER_BLOCKED)
    result = subprocess.run(  # noqa: S603 — trình thông dịch của chính tiến trình test, mã cố định
        [sys.executable, "-c", f"import sys; {blocked}; import apps.api.quality.assessments"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
