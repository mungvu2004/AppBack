"""Ranh giới nhập (BE-00 §2.1, §12): gói miền thuần, nhập được khi thư viện hạ tầng bị chặn."""

import subprocess
import sys
from pathlib import Path
from typing import Final

from packages.testing.boundary import PURE_BLOCKED

REPO_ROOT: Final = Path(__file__).resolve().parents[4]
_BLOCKED: Final = (*PURE_BLOCKED, "numpy", "shapely")

# Tiến trình con chặn thư viện hạ tầng, nhập gói, chạy thử hai hàm công khai, rồi kiểm không kéo
# theo gói nội bộ bị cấm; in "ok" nếu mọi thứ đạt.
_BOUNDARY_CODE: Final = """
import sys

BLOCKED = __BLOCKED__


class Blocker:
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in BLOCKED:
            raise ImportError("bi chan: " + name)
        return None


sys.meta_path.insert(0, Blocker())
from packages.domain.rules_ai import apply_post_rules, merge_pipeline_result
from packages.domain.spatial import SpatialLayer, sample_layer

layer = sample_layer(0)
assert apply_post_rules(layer) is not None
assert merge_pipeline_result(layer, SpatialLayer(walls=(), openings=(), rooms=(), furniture=())).layer is not None
FORBIDDEN = ("packages.db", "packages.storage", "packages.messaging", "packages.vision", "apps")
bad = sorted(m for m in sys.modules if m.split(".")[0] in {"apps"} or m.startswith(FORBIDDEN[:4]))
assert not bad, bad
print("ok")
"""


def test_rules_ai_imports_without_infrastructure() -> None:
    """`packages.domain.rules_ai` nhập và chạy được khi `sqlalchemy`, `fastapi`, `celery`, `numpy` bị chặn."""
    result = subprocess.run(  # noqa: S603 — lệnh cố định, chạy chính Python của venv
        [sys.executable, "-c", _BOUNDARY_CODE.replace("__BLOCKED__", repr(set(_BLOCKED)))],
        cwd=REPO_ROOT,
        env={"PYTHONPATH": str(REPO_ROOT), "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"
