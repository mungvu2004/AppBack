"""Ranh giới nhập của `apps.api.spatial_read` (BE-00 §7, B3-02 [8] "Ranh giới"): tiến trình mới.

`apps/worker` nhập `jobs.py` để chạy beat, và ảnh worker **không cài** `fastapi`, `starlette`,
`jwt`, `argon2`. Một lời nhập gián tiếp — chẳng hạn `apps.api.floors.lookup` kéo
`apps.api.projects.parts` kéo starlette — chỉ lộ ra khi bốn gói ấy thật sự vắng mặt, nên phép
kiểm phải chạy ở **tiến trình con** chứ không trong pytest (nơi cả bốn đã nạp sẵn).

`router`, `graph`, `wire`, `cli` được miễn: chúng là lớp HTTP/CLI, không ai nhập từ worker.
`wire` tuy không nhập `fastapi` nhưng hợp đồng [2] xếp nó vào nhóm miễn — không chốt chặt
hơn hiến chương ở đây, vì làm thế là dựng một bất biến không ai hứa.
"""

import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest

REPO_ROOT: Final = Path(__file__).resolve().parents[4]
WORKER_BLOCKED: Final = ("fastapi", "starlette", "jwt", "argon2")

WORKER_SAFE_MODULES: Final = (
    "apps.api.spatial_read",
    "apps.api.spatial_read.assemble",
    "apps.api.spatial_read.codec",
    "apps.api.spatial_read.counts",
    "apps.api.spatial_read.documents",
    "apps.api.spatial_read.drawing_scales",
    "apps.api.spatial_read.entity_ids",
    "apps.api.spatial_read.jobs",
    "apps.api.spatial_read.pages",
    "apps.api.spatial_read.settings",
)
"""Mọi module của gói trừ `router`, `graph`, `wire`, `cli` (B3-02 [2] "Hàm cho prompt sau")."""


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


@pytest.mark.parametrize("module", WORKER_SAFE_MODULES)
def test_module_imports_without_web_or_crypto_packages(module: str) -> None:
    """Nhập được khi `fastapi`, `starlette`, `jwt`, `argon2` bị chặn — đủ bốn gói."""
    blocked = "; ".join(f"sys.modules[{name!r}] = None" for name in WORKER_BLOCKED)
    result = _python(f"import sys; {blocked}; import {module}")
    assert result.returncode == 0, result.stderr
