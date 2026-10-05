"""Hằng ranh giới nhập dùng chung (NO-353) khớp `.importlinter`, và không test nào chép lại tuple chặn."""

from __future__ import annotations

import ast
import configparser
from pathlib import Path
from typing import Final

import pytest

from packages.testing.boundary import CLI_BLOCKED, PURE_BLOCKED, WORKER_BLOCKED
from tools.contract.check import H1_EXEMPT

REPO_ROOT: Final = Path(__file__).resolve().parent.parent.parent
_SCAN_ROOTS: Final = ("apps", "packages")
_OWNER: Final = Path("packages/testing/boundary.py")
_WEB_MARKERS: Final = ("jwt", "argon2")


def _contracts() -> dict[str, set[str]]:
    """Tên hợp đồng của `.importlinter` → tập `forbidden_modules`."""
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(REPO_ROOT / ".importlinter", encoding="utf-8")
    return {
        section.split(":")[-1]: set(parser[section].get("forbidden_modules", "").split())
        for section in parser.sections()
        if section.startswith("importlinter:contract:")
    }


def _is_copy(node: ast.expr) -> bool:
    """`node` là literal gộp chứa trọn `PURE_BLOCKED` hoặc `jwt`+`argon2` (cả chuỗi trích dẫn trong mã nhúng)."""
    if isinstance(node, ast.Tuple | ast.List | ast.Set):
        names = {e.value for e in node.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)}
        return set(PURE_BLOCKED) <= names or set(_WEB_MARKERS) <= names
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return all(f"'{m}'" in node.value or f'"{m}"' in node.value for m in _WEB_MARKERS)
    return False


def _copies_of_blocked_tuple() -> list[str]:
    """`file:dòng` của mọi literal/chuỗi mã nhúng chép lại bộ gói bị chặn trong test, ngoài tệp hằng chung."""
    found: list[str] = []
    for root in _SCAN_ROOTS:
        for path in sorted((REPO_ROOT / root).rglob("*.py")):
            rel = path.relative_to(REPO_ROOT)
            if rel == _OWNER or "tests" not in rel.parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(rel))
            found += [f"{rel.as_posix()}:{n.lineno}" for n in ast.walk(tree) if isinstance(n, ast.expr) and _is_copy(n)]
    return found


@pytest.mark.parametrize("contract", ["worker-no-web", "api-jobs-no-web"])
def test_worker_blocked__equals_importlinter_contract(contract: str) -> None:
    """`WORKER_BLOCKED` bằng đúng `forbidden_modules` của hai hợp đồng worker/jobs."""
    assert _contracts()[contract] == set(WORKER_BLOCKED)


def test_cli_blocked__equals_importlinter_contract() -> None:
    """`CLI_BLOCKED` bằng đúng `forbidden_modules` của `api-cli-no-web` (NO-352)."""
    assert _contracts()["api-cli-no-web"] == set(CLI_BLOCKED)


def test_pure_blocked__subset_of_domain_vision_contract() -> None:
    """`PURE_BLOCKED` nằm trong `forbidden_modules` của `domain-vision-isolated`."""
    assert set(PURE_BLOCKED) <= _contracts()["domain-vision-isolated"]


def test_boundary_tests__do_not_copy_blocked_tuple() -> None:
    """Không test nào tự chép tuple gói web bị chặn: phải nhập `packages.testing.boundary` (R-07)."""
    assert _copies_of_blocked_tuple() == []


def test_infra_ops__equal_h1_exempt() -> None:
    """`case_gate.INFRA_OPS` và `H1_EXEMPT` của hợp đồng FE là cùng một danh sách ba op (NO-222)."""
    from tools.case_gate import INFRA_OPS

    assert INFRA_OPS == H1_EXEMPT
