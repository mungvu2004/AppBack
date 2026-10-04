"""Ranh giới nhập (NO-337): mã dưới `packages/` không nhập tầng công cụ `tools` — tầng ngoài nhập tầng trong.

Ngoại lệ duy nhất (người dùng duyệt giữ nguyên 2026-10-04): fixture `packages/testing/fixtures/golden.py` nhập
`tools.contract.runner_client` — runner Node gắn với tài sản `tools/contract/*.ts`, dời xuống `packages`
là sai tầng. Thư mục `tests/` được nhập `tools` (test của công cụ).
"""

import ast
from pathlib import Path

PACKAGES_DIR = Path(__file__).resolve().parents[3]
ALLOWED: frozenset[tuple[str, str]] = frozenset(
    {("packages/testing/fixtures/golden.py", "tools.contract.runner_client")},
)


def _tools_imports(path: Path) -> list[str]:
    """Tên module `tools`/`tools.*` mà `path` nhập (tuyệt đối)."""
    names: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.append(node.module)
    return [n for n in names if n == "tools" or n.startswith("tools.")]


def test_packages_sources__do_not_import_tools() -> None:
    """Không file nguồn nào dưới `packages/` (ngoài `tests/` và ngoại lệ đã duyệt) nhập `tools`."""
    root = PACKAGES_DIR.parent
    bad = [
        (rel, name)
        for path in sorted(PACKAGES_DIR.rglob("*.py"))
        if "tests" not in path.relative_to(PACKAGES_DIR).parts
        for rel in [path.relative_to(root).as_posix()]
        for name in _tools_imports(path)
        if (rel, name) not in ALLOWED
    ]
    assert bad == []
