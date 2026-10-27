"""tools/verify/affected.py — chọn tệp test của cổng nhanh trên repo giả, đồ thị import giả (PERF-04)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.verify import affected

FIXTURE_DB = """
import pytest
from packages.db import engine


@pytest.fixture
def db_sessionmaker():
    return engine


@pytest.fixture(name="repo_api")
def _api(db_sessionmaker):
    return db_sessionmaker
"""

FIXTURE_CLOCK = """
import pytest


@pytest.fixture
def fake_clock():
    return 0
"""

GRAPH = {
    # module bị đổi → mọi module nhập nó (bắc cầu)
    "packages.db.engine": {"packages.testing.fixtures.db", "apps.api.auth.service", "apps.api.auth.tests.test_service"},
}


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Repo giả: hai module fixture và năm tệp test ở ba đơn vị."""
    files = {
        "packages/testing/fixtures/db.py": FIXTURE_DB,
        "packages/testing/fixtures/clock.py": FIXTURE_CLOCK,
        "packages/db/tests/test_engine.py": "def test_x(): ...\n",
        "apps/api/auth/tests/test_service.py": "def test_x(): ...\n",
        "apps/api/notes/tests/test_routes.py": "def test_x(db_sessionmaker): ...\n",
        "apps/api/notes/tests/test_usefixtures.py": 'import pytest\npytestmark = pytest.mark.usefixtures("repo_api")\n',
        "apps/worker/clock/tests/test_tick.py": "def test_x(fake_clock): ...\n",
        "apps/worker/clock/tests/helpers.py": "def test_not_collected(db_sessionmaker): ...\n",
    }
    for rel, text in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text, encoding="utf-8")
    return tmp_path


def _importers(module: str) -> set[str]:
    """Đồ thị giả: `GRAPH`, module lạ → không ai nhập."""
    return GRAPH.get(module, set())


def test_module_of() -> None:
    """Tệp `.py` dưới gốc import → tên module (`__init__` → gói); tệp khác → None."""
    assert affected.module_of("apps/api/auth/service.py") == "apps.api.auth.service"
    assert affected.module_of("packages/db/__init__.py") == "packages.db"
    assert affected.module_of("deploy/tests/test_x.py") is None
    assert affected.module_of("docs/x.md") is None


def test_affected_tests__đơn_vị_đồ_thị_import_và_fixture(repo: Path) -> None:
    """Đổi `packages/db/engine.py`: test của đơn vị, test nhập bắc cầu, test xin fixture (kể cả qua fixture
    khác và `usefixtures`); bỏ test không dính, bỏ tệp không phải `test_*.py`."""
    assert affected.affected_tests(["packages/db/engine.py"], repo, _importers) == [
        "packages/db/tests/test_engine.py",
        "apps/api/auth/tests/test_service.py",
        "apps/api/notes/tests/test_routes.py",
        "apps/api/notes/tests/test_usefixtures.py",
    ]


def test_affected_tests__module_lá_chỉ_đơn_vị(repo: Path) -> None:
    """Module không ai nhập, không fixture nào dính: chỉ test của đơn vị nó."""
    assert affected.affected_tests(["apps/worker/clock/tick.py"], repo, _importers) == [
        "apps/worker/clock/tests/test_tick.py"
    ]


def test_affected_tests__không_mã_thì_không_test(repo: Path) -> None:
    """Chỉ đổi tài liệu: không test nào, không dựng đồ thị."""

    def boom(_module: str) -> set[str]:
        raise AssertionError("không được dựng đồ thị")

    assert affected.affected_tests(["docs/x.md", "README.md"], repo, boom) == []


@pytest.mark.parametrize(
    "changed",
    ["conftest.py", "pyproject.toml", "uv.lock", "packages/testing/fixtures/db.py", "packages/db/migrations/r.py"],
)
def test_affected_tests__hạ_tầng_chung_thì_cả_bộ(repo: Path, changed: str) -> None:
    """Hạ tầng test và lược đồ DB chạm mọi test: `None` = cả bộ."""
    assert affected.affected_tests(["apps/api/auth/service.py", changed], repo, _importers) is None


def test_importers_of__đồ_thị_thật() -> None:
    """Đồ thị grimp thật của repo: `steps` nhập `affected`, gói thì tính cả kẻ nhập module con."""
    assert "tools.verify.steps" in affected.importers_of("tools.verify.affected")
    assert "tools.tests.test_steps_commands" in affected.importers_of("tools.verify")
    assert affected.importers_of("tools.verify.không_có") == set()
