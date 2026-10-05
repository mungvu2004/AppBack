"""Ranh giới nhập của `apps.worker.pipeline_build` (BE-00 §7, §12; B5-05 [8] "Ranh giới").

Nhập thật trong tiến trình con với tám gói bị chặn: `fastapi`, `starlette`, `jwt`, `argon2`,
`sqlalchemy`, `asyncpg`, `torch`, `onnxruntime`. `tasks.py` nhập `build` ở đầu module, nên bài
này cũng bao luôn `build`, `geometry`, `rooms` và chuỗi `shapely`/`numpy` chúng kéo theo.
"""

import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest

from packages.testing.boundary import WORKER_BLOCKED

REPO_ROOT: Final = Path(__file__).resolve().parents[4]
BLOCKED: Final = (*WORKER_BLOCKED, "sqlalchemy", "asyncpg", "torch", "onnxruntime")
IMPORT_TIMEOUT_S: Final = 120.0


@pytest.mark.parametrize("module", ["apps.worker.pipeline_build", "apps.worker.pipeline_build.tasks"])
def test_imports_without_web_or_ml_packages(module: str) -> None:
    """Nhập được khi tám gói tiến trình con không có (ảnh `worker` không cài chúng)."""
    blocked = "; ".join(f"sys.modules[{name!r}] = None" for name in BLOCKED)
    result = subprocess.run(  # noqa: S603 — trình thông dịch của chính tiến trình test, mã cố định
        [sys.executable, "-c", f"import sys; {blocked}; import {module}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=IMPORT_TIMEOUT_S,
    )
    assert result.returncode == 0, result.stderr
