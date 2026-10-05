"""Ranh giới nhập của `apps.worker.pipeline_persist` (BE-00 §7, §12; B5-06b [8] "Ranh giới").

`import-linter` (bước 4 của cổng) đọc cây nhập **tĩnh**: một `import fastapi` trong thân hàm
vẫn nằm trong cây, còn một phụ thuộc lọt vào qua `importlib` thì không. Test này nhập thật
trong một tiến trình mà bốn gói web/crypto đã bị đặt `None` trong `sys.modules`, nên lượt nhập
nào cũng vỡ ngay — kể cả lúc `create_storage` được nhập trễ trong `tasks._storage`.
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
    [
        "apps.worker.pipeline_persist.service",
        "apps.worker.pipeline_persist.tasks",
        "apps.worker.pipeline_persist.merge",
        "apps.worker.pipeline_persist.context",
    ],
)
def test_imports_without_web_or_crypto_packages(module: str) -> None:
    """Nhập được khi `fastapi`, `starlette`, `jwt`, `argon2` bị chặn (ảnh `worker` không cài chúng)."""
    blocked = "; ".join(f"sys.modules[{name!r}] = None" for name in WORKER_BLOCKED)
    result = subprocess.run(  # noqa: S603 — trình thông dịch của chính tiến trình test, mã cố định
        [sys.executable, "-c", f"import sys; {blocked}; import {module}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=IMPORT_TIMEOUT_S,
    )

    assert result.returncode == 0, result.stderr
