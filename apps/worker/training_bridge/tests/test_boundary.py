"""Ranh giới nhập của `apps.worker.training_bridge` (BE-00 §7, §12, B6-03a [8] "Ranh giới").

Chạy thật trong tiến trình con: một finder ở `sys.meta_path` ném `ImportError` cho
`fastapi`, `starlette`, `jwt`, `argon2` trước khi chúng nạp được, rồi nhập từng module của
cầu nối. Khuôn `apps/worker/datasets/tests/test_boundary.py`, nhưng chặn bằng finder thay vì
đặt `sys.modules[name] = None` (spec [8] của prompt này chỉ định finder).
"""

import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest

REPO_ROOT: Final = Path(__file__).resolve().parents[4]
BLOCKED: Final = ("fastapi", "starlette", "jwt", "argon2")
IMPORT_TIMEOUT_S: Final = 120.0

_MODULES: Final = (
    "apps.worker.training_bridge.tasks",
    "apps.worker.training_bridge.jobs",
    "apps.worker.training_bridge.settings",
    "apps.worker.training_bridge.errors",
    "apps.worker.training_bridge.messages",
)

_SCRIPT: Final = """
import sys

BLOCKED = {blocked!r}
MODULES = {modules!r}


class _BlockingFinder:
    \"\"\"`sys.meta_path` finder: nạp bất kỳ tên nào trong BLOCKED ném ImportError ngay.\"\"\"

    def find_spec(self, fullname, path, target=None):
        \"\"\"Chặn tên trong BLOCKED (và gói con của nó); nhường tên khác cho finder sau.\"\"\"
        if fullname in BLOCKED or any(fullname.startswith(name + ".") for name in BLOCKED):
            raise ImportError(f"blocked: {{fullname}}")
        return None


sys.meta_path.insert(0, _BlockingFinder())

for module in MODULES:
    __import__(module)
"""


@pytest.mark.parametrize("module", _MODULES)
def test_each_module_importable_alone_without_web_or_crypto_packages(module: str) -> None:
    """Mỗi module cầu nối nhập được một mình (không kéo module khác lộ phụ thuộc web/crypto)."""
    script = _SCRIPT.format(blocked=BLOCKED, modules=(module,))
    result = subprocess.run(  # noqa: S603 — trình thông dịch của chính tiến trình test, mã cố định
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=IMPORT_TIMEOUT_S,
    )

    assert result.returncode == 0, result.stderr
