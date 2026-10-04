"""NO-282 — gói bên ngoài mà mã test nhập trực tiếp phải được khai ở nhóm `dev`, ghim đúng bản trong `uv.lock`.

`docker` được nhập thẳng ở `packages/testing/fixtures/services.py` và `tools/tests/test_shared_services.py`
nhưng chỉ có mặt nhờ đi kèm `testcontainers`: một lần nâng `testcontainers` bỏ phụ thuộc đó là import vỡ
mà `uv lock` không báo trước.
"""

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _locked_version(name: str) -> str:
    """Bản của gói `name` trong `uv.lock`."""
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    return str(next(pkg["version"] for pkg in lock["package"] if pkg["name"] == name))


def test_dev_group__declares_docker_pinned_to_lock() -> None:
    """Nhóm `dev` khai `docker==<bản trong uv.lock>` — khai rõ phụ thuộc trực tiếp, không đổi bản đang khoá."""
    dev = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["dependency-groups"]["dev"]
    assert f"docker=={_locked_version('docker')}" in dev
