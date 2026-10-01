"""Ranh giới nhập của `pipeline_steps` (B5-06c [8] việc C "Khối [9] CẤM TUYỆT ĐỐI").

Năm module (`tasks`, `jobs`, `step_done`, `sweep`, `purge`) phải nhập được (không lỗi cú
pháp/vòng) và không module nào trong số đó nhập `apps.ml`, `torch`, `onnxruntime`, `fastapi` —
soát bằng AST trên mã nguồn, không chỉ bằng `sys.modules` sau khi nhập (một nhập trễ trong
thân hàm vẫn phải bị bắt).
"""

import ast
import importlib
from pathlib import Path
from typing import Final

import pytest

MODULE_NAMES: Final = ("tasks", "jobs", "step_done", "sweep", "purge")
FORBIDDEN_ROOTS: Final = ("apps.ml", "torch", "onnxruntime", "fastapi")
_PACKAGE_DIR: Final = Path(__file__).resolve().parent.parent


def _matches_forbidden(module: str) -> bool:
    """`module` là, hay nằm dưới, một trong `FORBIDDEN_ROOTS`."""
    return any(module == root or module.startswith(f"{root}.") for root in FORBIDDEN_ROOTS)


def _forbidden_imports(source: str, relative: Path) -> list[str]:
    """Mọi `import`/`from … import …` (kể cả lồng trong hàm) chạm một trong `FORBIDDEN_ROOTS`."""
    tree = ast.parse(source, filename=str(relative))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [
                f"{relative}:{node.lineno} nhập {alias.name}"
                for alias in node.names
                if alias.name.split(".")[0] in {root.split(".")[0] for root in FORBIDDEN_ROOTS}
            ]
        elif isinstance(node, ast.ImportFrom) and node.module and _matches_forbidden(node.module):
            found.append(f"{relative}:{node.lineno} nhập {node.module}")
    return found


@pytest.mark.parametrize("name", MODULE_NAMES)
def test_module_source_has_no_forbidden_import(name: str) -> None:
    """Soát mã nguồn (AST): không `apps.ml`, `torch`, `onnxruntime`, `fastapi`."""
    path = _PACKAGE_DIR / f"{name}.py"
    assert (
        _forbidden_imports(path.read_text(encoding="utf-8"), path.relative_to(_PACKAGE_DIR.parent.parent.parent)) == []
    )


@pytest.mark.parametrize("name", MODULE_NAMES)
def test_module_imports_successfully(name: str) -> None:
    """Mỗi module nhập được qua đường chính thức (`apps.worker.pipeline_steps.<name>`)."""
    importlib.import_module(f"apps.worker.pipeline_steps.{name}")
