"""Tệp test bị ảnh hưởng của cổng nhanh (PERF-04): đồ thị import (grimp) + fixture xin theo tên.

Một tệp `test_*.py` được chọn khi một trong ba điều đúng:
- nó thuộc một đơn vị bị chạm (`unit_of`, như PERF-03) — độ phủ đơn vị bị chạm cần đủ test của đơn vị;
- nó nhập, trực tiếp hay bắc cầu, một module bị đổi (`find_downstream_modules` của grimp);
- nó nhắc tên (tham số, chuỗi) một fixture của `packages/testing/fixtures/` mà module fixture nhập bắc
  cầu module bị đổi, hay xin một fixture như thế — test không nhập `packages.db` vẫn chạy trên nó qua
  `db_sessionmaker`.

Không thấy (cổng đầy đủ trước merge bắt): nạp động (`pkgutil`/`import_module` của
`apps.api.core.extensions`, `discover_trainers`, lịch Celery) và tiến trình con `python -m`. Module nạp
động hỏng lúc nhập thì test của chính đơn vị nó — luôn được chọn — vẫn đỏ.
"""

from __future__ import annotations

import ast
from collections.abc import Callable, Iterable
from functools import cache
from pathlib import Path, PurePosixPath

from tools.coverage_gate import unit_of

FULL_SUITE_FILES = frozenset({"conftest.py", "pyproject.toml", "uv.lock"})
FULL_SUITE_DIRS = ("packages/testing/", "packages/db/migrations/")
"""Hạ tầng test (fixture, plugin, thứ tự xdist) và lược đồ DB mọi fixture DB dựng: đổi là chạy cả bộ."""
IMPORT_ROOTS = ("packages", "apps", "tools")
"""Gói gốc của đồ thị import — đúng `root_packages` của `.importlinter`."""
TEST_ROOTS = ("packages", "apps", "tools", "deploy", "tests")
"""`testpaths` của `pyproject.toml`."""
FIXTURES_DIR = "packages/testing/fixtures"

Importers = Callable[[str], set[str]]


def module_of(path: str) -> str | None:
    """Tên module của một tệp `.py` dưới `IMPORT_ROOTS` (`__init__.py` → tên gói); khác → `None`."""
    p = PurePosixPath(path)
    if p.suffix != ".py" or not p.parts or p.parts[0] not in IMPORT_ROOTS:
        return None
    parts = p.with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


@cache
def _graph_importers() -> Importers:
    """`find_downstream_modules` của đồ thị grimp dựng một lần mỗi tiến trình (cwd = gốc repo, như lint-imports)."""
    import grimp  # chỉ cổng nhanh cần: không nạp khi `steps` chạy việc khác
    from grimp.exceptions import ModuleNotPresent

    graph = grimp.build_graph(*IMPORT_ROOTS, cache_dir=None)

    def importers(module: str) -> set[str]:
        # Gói: `__init__` chạy khi nhập BẤT KỲ module con nào, nên kẻ nhập module con cũng bị ảnh hưởng.
        try:
            return set(graph.find_downstream_modules(module, as_package=bool(graph.find_children(module))))
        except ModuleNotPresent:  # tệp đã xoá: kẻ nhập nó đã hỏng nhập — mypy/ruff của cổng nhanh bắt
            return set()

    return importers


def importers_of(module: str) -> set[str]:
    """Mọi module nhập `module`, trực tiếp hay bắc cầu, theo đồ thị import thật của repo."""
    return _graph_importers()(module)


def _is_fixture(decorator: ast.expr) -> bool:
    """Decorator là `fixture`, `pytest.fixture(...)`, `pytest_asyncio.fixture(...)`."""
    target = decorator.func if isinstance(decorator, ast.Call) else decorator
    name = target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", "")
    return name == "fixture"


def _fixture_name(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Tên fixture: `name=` của decorator nếu có, không thì tên hàm."""
    for decorator in fn.decorator_list:
        if isinstance(decorator, ast.Call):
            for kw in decorator.keywords:
                if kw.arg == "name" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    return kw.value.value
    return fn.name


def fixture_params(source: str) -> dict[str, set[str]]:
    """Fixture của một module → tên các tham số (fixture khác) nó xin."""
    return {
        _fixture_name(node): {a.arg for a in node.args.args + node.args.kwonlyargs}
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and any(map(_is_fixture, node.decorator_list))
    }


def mentioned_names(source: str) -> set[str]:
    """Mọi tên tham số và hằng chuỗi của một tệp test — tập trên của fixture nó có thể xin.

    Hằng chuỗi phủ `usefixtures("x")`, `request.getfixturevalue("x")`; thừa vài tên chỉ tốn thời gian.
    """
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            names.add(node.value)
    return names


def tainted_fixtures(root: Path, hit: set[str]) -> set[str]:
    """Fixture mà module fixture của nó nằm trong `hit`, cộng mọi fixture xin (bắc cầu) một fixture như thế."""
    params: dict[str, set[str]] = {}
    tainted: set[str] = set()
    for path in sorted((root / FIXTURES_DIR).glob("*.py")):
        own = fixture_params(path.read_text(encoding="utf-8"))
        params |= own
        if module_of(path.relative_to(root).as_posix()) in hit:
            tainted |= own.keys()
    grew = True
    while grew:
        grew = False
        for name, wants in params.items():
            if name not in tainted and wants & tainted:
                tainted.add(name)
                grew = True
    return tainted


def _test_files(root: Path) -> Iterable[str]:
    """Đường tương đối (dấu `/`) của mọi `test_*.py` trong thư mục `tests/` dưới `TEST_ROOTS`."""
    for top in TEST_ROOTS:
        for path in sorted((root / top).rglob("test_*.py")):
            rel = path.relative_to(root)
            if "tests" in rel.parts[:-1] and "__pycache__" not in rel.parts:
                yield rel.as_posix()


def affected_tests(changed: list[str], root: Path, importers: Importers | None = None) -> list[str] | None:
    """Tệp test cổng nhanh chạy cho tập tệp đổi `changed`; `None` = cả bộ, `[]` = không test nào.

    `importers` mặc định là đồ thị import thật (`importers_of`), chỉ dựng khi có module `.py` bị đổi.
    """
    if any(c in FULL_SUITE_FILES or c.startswith(FULL_SUITE_DIRS) for c in changed):
        return None
    modules = {m for m in map(module_of, changed) if m is not None}
    hit = set(modules)
    for module in modules:
        hit |= (importers or importers_of)(module)
    units = {u for u in map(unit_of, changed) if u is not None}
    tainted = tainted_fixtures(root, hit) if hit else set()
    return [
        rel
        for rel in _test_files(root)
        if unit_of(rel) in units
        or module_of(rel) in hit
        or (tainted and not tainted.isdisjoint(mentioned_names((root / rel).read_text(encoding="utf-8"))))
    ]
