"""Ranh giới nhập (BE-00 §2.1, §12): hai gói miền nhập được khi thư viện hạ tầng bị chặn."""

import subprocess
import sys
from pathlib import Path
from typing import Final

REPO_ROOT: Final = Path(__file__).resolve().parents[4]

# Tiến trình con chặn thư viện hạ tầng rồi nhập hai gói; in "ok" nếu cả hai vào được.
_BOUNDARY_CODE: Final = """
import sys

BLOCKED = {"sqlalchemy", "fastapi", "celery", "numpy", "torch"}


class Blocker:
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in BLOCKED:
            raise ImportError("bi chan: " + name)
        return None


sys.meta_path.insert(0, Blocker())
import packages.domain.scale  # noqa: E402
import packages.domain.spatial  # noqa: E402

packages.domain.spatial.sample_building()
print("ok")
"""


def test_domain_packages_import_without_infrastructure() -> None:
    """`packages.domain.spatial`, `packages.domain.scale` không kéo `sqlalchemy`, `fastapi`, `celery`, `numpy`."""
    result = subprocess.run(  # noqa: S603 — lệnh cố định, chạy chính Python của venv
        [sys.executable, "-c", _BOUNDARY_CODE],
        cwd=REPO_ROOT,
        env={"PYTHONPATH": str(REPO_ROOT), "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"
