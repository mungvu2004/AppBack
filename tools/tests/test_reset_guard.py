"""FIX-114 — hai lưới an toàn quanh `packages/testing`.

1. `assert_reset_target`: lượt dọn `DELETE` của `db_url` chỉ được chạm database dùng chung của
   chính tiến trình test này. Đây là đường **duy nhất** chạy `DELETE FROM` mọi bảng, nên chặn ở
   đó là chặn cho mọi người gọi (R-19); test dưới dựng đúng các URL lạc mà lỗi thật sẽ tạo ra.
2. Hợp đồng `testing-only-from-tests` của `.importlinter`: mã sản phẩm không nhập
   `packages.testing`. `lint-imports` (bước 4) kiểm import thật; test dưới kiểm **cấu hình**,
   để một gói mới thêm vào `packages/` hay `apps/` mà quên khai là đỏ ngay chứ không âm thầm
   nằm ngoài hợp đồng.
"""

from __future__ import annotations

import configparser
import sys
from pathlib import Path

import pytest

from packages.testing.fixtures.db import SHARED_DB, assert_reset_target, shared_db_name
from packages.testing.fixtures.worker_id import XDIST_WORKER_ENV

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_SECTION = "importlinter:contract:testing-only-from-tests"
TESTING_PACKAGE = "packages.testing"


def _url(database: str) -> str:
    """URL Postgres giả trỏ tới database `database`."""
    return f"postgresql+asyncpg://u:p@127.0.0.1:5432/{database}"


# --- 1. chặn cứng lượt dọn DELETE ----------------------------------------------------


def test_lượt_dọn_nhận_database_của_chính_tiến_trình(monkeypatch: pytest.MonkeyPatch) -> None:
    """Đường thường: tên khớp `shared_db_name()` và đang chạy dưới pytest → không ném gì."""
    monkeypatch.setenv(XDIST_WORKER_ENV, "gw3")
    assert_reset_target(_url(shared_db_name()))


@pytest.mark.parametrize(
    "database",
    [
        "postgres",  # database quản trị của máy chủ
        "appback",  # database thật của môi trường chạy
        "appback_template_gw3",  # database mẫu, không phải bản dùng chung
        f"{SHARED_DB}_gw4",  # bản dùng chung của **tiến trình xdist khác**
        SHARED_DB,  # tên ngoài xdist trong khi tiến trình này đang ở gw3
        "",  # URL không nêu database
    ],
)
def test_lượt_dọn_từ_chối_database_lạ(monkeypatch: pytest.MonkeyPatch, database: str) -> None:
    """Lượt dọn từ chối database lạ."""
    monkeypatch.setenv(XDIST_WORKER_ENV, "gw3")
    with pytest.raises(RuntimeError, match="chỉ dọn được"):
        assert_reset_target(_url(database))


def test_lượt_dọn_từ_chối_khi_không_thấy_phiên_pytest(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tên database đúng nhưng tiến trình không phải phiên pytest → vẫn không chạy `DELETE`."""
    monkeypatch.setenv(XDIST_WORKER_ENV, "gw3")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delitem(sys.modules, "pytest")
    with pytest.raises(RuntimeError, match="dưới pytest"):
        assert_reset_target(_url(shared_db_name()))


def test_lượt_dọn_chấp_nhận_khi_chỉ_có_biến_môi_trường_của_pytest(monkeypatch: pytest.MonkeyPatch) -> None:
    """`PYTEST_CURRENT_TEST` một mình là đủ — tiến trình con chưa nhập `pytest` vẫn dọn được."""
    monkeypatch.setenv(XDIST_WORKER_ENV, "gw3")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "tools/tests/test_reset_guard.py::x (teardown)")
    monkeypatch.delitem(sys.modules, "pytest")
    assert_reset_target(_url(shared_db_name()))


# --- 2. hợp đồng cấm nhập packages.testing từ mã sản phẩm ----------------------------


def _contract() -> configparser.SectionProxy:
    """Mục hợp đồng `testing-only-from-tests` trong `.importlinter`."""
    parser = configparser.ConfigParser()
    parser.read(REPO_ROOT / ".importlinter", encoding="utf-8")
    assert CONTRACT_SECTION in parser, f"thiếu hợp đồng [{CONTRACT_SECTION}] trong .importlinter"
    return parser[CONTRACT_SECTION]


def _lines(section: configparser.SectionProxy, key: str) -> set[str]:
    """Các dòng của khoá `key` trong một mục, thành tập."""
    return {line.strip() for line in section[key].splitlines() if line.strip()}


def _top_level_modules() -> set[str]:
    """Nguồn của hợp đồng: mọi gói một cấp dưới `packages/` và `apps/`, cộng chính `tools`.

    `tools` là một gói (`tools/__init__.py`) chứ không phải thư mục chứa nhiều gói, và mã không
    phải test của nó (`coverage_gate.py`, `case_gate.py`) cũng là mã sản phẩm
    — bỏ nó ra ngoài là lưới không phủ hết ý của hợp đồng (review F-4). `packages.testing` đứng
    ngoài vì nó chính là thứ đang bị cấm nhập.
    """
    found = {"tools"}
    for parent in ("packages", "apps"):
        for path in sorted((REPO_ROOT / parent).iterdir()):
            if (path / "__init__.py").exists():
                found.add(f"{parent}.{path.name}")
    return found - {TESTING_PACKAGE}


def test_hợp_đồng_cấm_đúng_packages_testing() -> None:
    """Hợp đồng chỉ cấm đúng `packages.testing`."""
    section = _contract()
    assert section["type"] == "forbidden"
    assert _lines(section, "forbidden_modules") == {TESTING_PACKAGE}


def test_hợp_đồng_phủ_mọi_gói_sản_phẩm() -> None:
    """Gói mới trong `packages/` hay `apps/` phải được khai, không thì nó nằm ngoài lưới."""
    assert _lines(_contract(), "source_modules") == _top_level_modules()


def test_hợp_đồng_vẫn_cho_test_nhập_packages_testing() -> None:
    """Test của mọi gói nhập `packages.testing` là hợp lệ (CLAUDE.md, BE-00 §2.1).

    Mẫu dùng `**` ở khúc giữa vì thư mục test nằm cả ở một cấp (`packages/core/tests`,
    `tools/tests`) lẫn hai cấp (`packages/domain/rules_ai/tests`, `tools/contract/tests`);
    `tools` cần hai dòng vì `**` không khớp được khúc rỗng (review F-5).
    """
    assert _lines(_contract(), "ignore_imports") == {
        "packages.**.tests.** -> packages.testing.**",
        "apps.**.tests.** -> packages.testing.**",
        "tools.tests.** -> packages.testing.**",
        "tools.**.tests.** -> packages.testing.**",
    }
