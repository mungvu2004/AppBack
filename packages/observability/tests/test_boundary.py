"""Ranh giới nhập (BE-00 §2.1, §12): `packages.observability` nhập được khi
`fastapi`, `starlette`, `sqlalchemy`, `celery`, `prometheus_client` bị chặn."""

import subprocess
import sys
from pathlib import Path
from typing import Final

REPO_ROOT: Final = Path(__file__).resolve().parents[3]

_BOUNDARY_CODE: Final = """
import sys

BLOCKED = {"fastapi", "starlette", "sqlalchemy", "celery", "prometheus_client"}


class Blocker:
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in BLOCKED:
            raise ImportError("bi chan: " + name)
        return None


sys.meta_path.insert(0, Blocker())
import packages.observability.exporter  # noqa: E402
import packages.observability.metrics  # noqa: E402
import packages.observability.settings  # noqa: E402

packages.observability.metrics.counter("appback_boundary_total", help="ranh gioi")
print("ok")
"""


def test_observability_imports_without_infrastructure() -> None:
    """`packages.observability` không kéo `fastapi`/`starlette`/`sqlalchemy`/`celery`/`prometheus_client`."""
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
