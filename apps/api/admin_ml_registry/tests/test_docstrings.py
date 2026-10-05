"""Quét R-01 cho cụm ml-admin: mọi hàm (kể cả hàm lồng, closure, `__init__`) có docstring."""

import ast
from pathlib import Path
from typing import Final

import pytest

REPO_ROOT: Final = Path(__file__).resolve().parents[4]
FUNCTION_MAX_LINES: Final = 50
SCANNED: Final = (
    "apps/api/admin_ml_registry",
    "apps/api/admin_ml_datasets",
    "apps/worker/datasets",
    "apps/worker/training_bridge",
)


def _functions(path: Path) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Mọi hàm (kể cả hàm lồng, phương thức) trong `path`."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)]


def _undocumented(path: Path) -> list[str]:
    """`file:dòng tên` của mọi hàm trong `path` không có docstring."""
    return [
        f"{path.relative_to(REPO_ROOT).as_posix()}:{node.lineno} {node.name}"
        for node in _functions(path)
        if ast.get_docstring(node) is None
    ]


@pytest.mark.parametrize("package", SCANNED)
def test_every_function_has_a_docstring(package: str) -> None:
    """Không hàm nào trong gói thiếu docstring (R-01; NO-262, NO-276)."""
    missing = [line for path in sorted((REPO_ROOT / package).rglob("*.py")) for line in _undocumented(path)]

    assert missing == []


def test_registry_functions_stay_within_the_line_ceiling() -> None:
    """Không hàm nào của mã nguồn `admin_ml_registry` dài quá 50 dòng (R-08; NO-261)."""
    too_long = [
        f"{path.name}:{node.lineno} {node.name}"
        for path in sorted((REPO_ROOT / SCANNED[0]).glob("*.py"))
        for node in _functions(path)
        if node.end_lineno is not None and node.end_lineno - node.lineno + 1 > FUNCTION_MAX_LINES
    ]

    assert too_long == []
