"""Fixture golden (B0-07): gắn bộ ghi vào `API_RESPONSE_OBSERVERS`, cho test AppFront và runner Node.

- `pytest_configure` thêm `record_response` vào sổ observer của B0-06 (`setdefault`, nên thứ tự
  nạp `api.py`/`golden.py` không quan trọng, và gọi lại không thêm bản thứ hai);
- `appfront_dir` — `Path(APPFRONT_DIR)`; thiếu file F-00a thì test **hỏng**, không bỏ qua.
  Mọi test cần Node hay AppFront xin fixture này (B0-09 xếp chúng vào nhóm CI có AppFront);
- `contract_build` — bố cục runner dựng một lần mỗi phiên test (`tools.contract.runner_client`).
"""

from pathlib import Path

import pytest

from packages.testing.fixtures.api import API_RESPONSE_OBSERVERS
from packages.testing.golden.recorder import record_response
from tools.contract.runner_client import (
    AppFrontMissingError,
    appfront_dir_from_env,
    build_layout,
    check_appfront,
    node_dir_from_env,
)


def pytest_configure(config: pytest.Config) -> None:
    """Đúng một bộ ghi golden trong sổ observer, bất kể thứ tự nạp plugin."""
    observers = config.stash.setdefault(API_RESPONSE_OBSERVERS, [])
    if record_response not in observers:
        observers.append(record_response)


def require_appfront(path: Path) -> Path:
    """`path` khi có file F-00a; không thì làm test hỏng ngay (không `skip`, K24)."""
    try:
        return check_appfront(path)
    except AppFrontMissingError as exc:
        pytest.fail(str(exc), pytrace=False)


@pytest.fixture(scope="session")
def appfront_dir() -> Path:
    """AppFront @ SHA ghim (`APPFRONT_DIR`, mặc định `/appfront` trong container verify)."""
    return require_appfront(appfront_dir_from_env())


@pytest.fixture(scope="session")
def contract_build(appfront_dir: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Bố cục runner Node dựng từ AppFront thật và `node_modules` trên volume (không mock, K23)."""
    return build_layout(appfront_dir, node_dir_from_env(), tmp_path_factory.mktemp("contract") / "build")
