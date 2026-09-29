"""Ranh giới nhập của `apps.worker.datasets` và các module `apps.api` nó kéo theo (BE-00 §7, §12).

`import-linter` (`worker-no-web`) đã canh việc này ở bước 4 của cổng, nhưng nó đọc **cây nhập
tĩnh**: một `import fastapi` nằm trong thân hàm vẫn nằm trong cây, còn một phụ thuộc lọt vào qua
`importlib` thì không. Test này chạy thật: nhập module trong một tiến trình mà `fastapi`,
`starlette`, `uvicorn`, `jwt`, `argon2` đã bị đặt thành `None` trong `sys.modules`, nên bất kỳ
lượt nhập nào — đầu file hay trong hàm, lúc nạp module — cũng vỡ ngay.
"""

import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest

REPO_ROOT: Final = Path(__file__).resolve().parents[4]
BLOCKED: Final = ("fastapi", "starlette", "uvicorn", "jwt", "argon2")
IMPORT_TIMEOUT_S: Final = 120.0


@pytest.mark.parametrize(
    "module",
    [
        "apps.worker.datasets.tasks",
        "apps.worker.datasets.jobs",
        "apps.worker.datasets.render",
        "apps.worker.datasets.writer",
        "apps.api.admin_ml_datasets.versions",
        "apps.api.admin_ml_datasets.errors",
        "apps.api.admin_ml_datasets.settings",
    ],
)
def test_imports_without_web_or_crypto_packages(module: str) -> None:
    """Nhập được khi `fastapi`, `starlette`, `uvicorn`, `jwt`, `argon2` bị chặn (ảnh `worker` không cài chúng)."""
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
