"""Ranh giới nhập của `state`, `jobs`, `settings`: worker `bake` và beat nhập chúng (BE-00 §7).

Mẫu `apps/worker/datasets/tests/test_boundary.py`: nhập module trong tiến trình con mà các gói
web/crypto (`WORKER_BLOCKED`) bị đặt `None`, nên mọi lượt nhập `apps.api.core` kéo theo
`fastapi`/`starlette` đều vỡ ngay.
"""

import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest

from packages.testing.boundary import WORKER_BLOCKED

REPO_ROOT: Final = Path(__file__).resolve().parents[4]
IMPORT_TIMEOUT_S: Final = 120.0


@pytest.mark.parametrize(
    "module",
    ["apps.api.lighting_bake.state", "apps.api.lighting_bake.jobs", "apps.api.lighting_bake.settings"],
)
def test_imports_without_web_or_crypto_packages(module: str) -> None:
    """Nhập được khi `fastapi`, `starlette`, `uvicorn`, `jwt`, `argon2` bị chặn, và không kéo `apps.api.core`."""
    blocked = "; ".join(f"sys.modules[{name!r}] = None" for name in WORKER_BLOCKED)
    check = "assert not [m for m in sys.modules if m.startswith('apps.api.core')]"
    result = subprocess.run(  # noqa: S603 — trình thông dịch của chính tiến trình test, mã cố định
        [sys.executable, "-c", f"import sys; {blocked}; import {module}; {check}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=IMPORT_TIMEOUT_S,
    )

    assert result.returncode == 0, result.stderr
