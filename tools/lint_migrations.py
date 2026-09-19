"""Lint migration Alembic — BE-00 §6.1, cài đúng B0-01 [6]I.

Quét `packages/db/migrations/versions/*.py`. Chưa có thư mục → "0 revision",
thoát 0. Không gọi Alembic, không chạm DB (đó là `packages.db.migrate_check`,
B0-03).
"""

from __future__ import annotations

import ast
import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VERSIONS_DIR = REPO_ROOT / "packages" / "db" / "migrations" / "versions"
CONTRACTS_TOML = REPO_ROOT / "docs" / "contracts.toml"

MAX_REVISION_LEN = 32

_BANNED_CALL_NAMES = {"drop_table", "drop_column", "drop_constraint", "rename_table", "batch_alter_table"}
_ALTER_COLUMN_BANNED_KWARGS = {"new_column_name", "nullable", "type_"}
_RAW_SQL_FUNCS = {"execute", "text", "exec_driver_sql"}
_SQL_DANGER_RE = re.compile(
    r"DROP|RENAME|SET\s+NOT\s+NULL|TRUNCATE|DELETE\s+FROM|ALTER\s+COLUMN\s+\S+\s+TYPE",
    re.IGNORECASE,
)
# Mẫu tên revision merge — hằng duy nhất, `tools/verify/steps.py merge-heads` nhập lại (B0-01 [6]I)
MERGE_REVISION_RE = re.compile(r"^r\d{8}_merge_w\d{2}_[1-9]\d*$")
_NORMAL_RE = re.compile(r"^r\d{8}_[a-z][a-z0-9_]*$")
_FIX_TAIL_RE = re.compile(r"_fix(\d*)$")
_CONTRACT_COMMENT_RE = re.compile(r"^\s*#\s*contract:\s*.+$")


@dataclass
class Violation:
    file: str
    rule: str
    detail: str


@dataclass
class Report:
    violations: list[Violation] = field(default_factory=list)

    def add(self, file: str, rule: str, detail: str) -> None:
        self.violations.append(Violation(file, rule, detail))

    @property
    def ok(self) -> bool:
        return not self.violations


def _validate_revision_id(revision: str) -> list[str]:
    problems: list[str] = []
    if len(revision) > MAX_REVISION_LEN:
        problems.append(f"revision dài {len(revision)} ký tự, vượt trần {MAX_REVISION_LEN}")

    if "_merge_w" in revision:
        if not MERGE_REVISION_RE.match(revision):
            problems.append("sai mẫu revision merge r<yyyymmdd>_merge_w<nn>_<k> (k từ 1, không số 0 đầu)")
        return problems

    base = revision
    fix_match = _FIX_TAIL_RE.search(revision)
    if fix_match:
        if len(fix_match.group(1)) != 3:
            problems.append("hậu tố _fix phải đúng 3 chữ số")
        base = revision[: fix_match.start()]
    if not _NORMAL_RE.match(base):
        problems.append("sai mẫu revision r<yyyymmdd>_<mã>[_fix<nnn>]")
    return problems


def _module_level_str(tree: ast.Module, name: str) -> str | None:
    """`name = "..."` hoặc `name: str = "..."` (mẫu alembic sinh ra) ở mức module."""
    for node in tree.body:
        if isinstance(node, ast.Assign):
            hit = any(isinstance(t, ast.Name) and t.id == name for t in node.targets)
        elif isinstance(node, ast.AnnAssign):
            hit = isinstance(node.target, ast.Name) and node.target.id == name
        else:
            continue
        if hit:
            value = node.value
            return value.value if isinstance(value, ast.Constant) and isinstance(value.value, str) else None
    return None


def revision_of(path: Path) -> str | None:
    """Giá trị `revision` của một file migration (None nếu không đọc được)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return None
    return _module_level_str(tree, "revision")


def _call_attr(node: ast.AST) -> str | None:
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _find_downgrade(tree: ast.Module) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "downgrade":
            return node
    return None


def _nodes_excluding_downgrade(tree: ast.Module) -> list[ast.AST]:
    """Mọi node của module, bỏ hẳn thân hàm `downgrade` (BE-00 §6.1)."""
    downgrade = _find_downgrade(tree)
    skip_ids = {id(n) for n in ast.walk(downgrade)} if downgrade else set()

    out: list[ast.AST] = []
    stack: list[ast.AST] = [tree]
    while stack:
        node = stack.pop()
        if id(node) in skip_ids and node is not tree:
            continue
        out.append(node)
        stack.extend(ast.iter_child_nodes(node))
    return out


def _collect_created_tables(nodes: list[ast.AST]) -> set[str]:
    tables: set[str] = set()
    for node in nodes:
        if _call_attr(node) == "create_table" and isinstance(node, ast.Call) and node.args:
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                tables.add(first.value)
    return tables


def _in_autocommit_block(node: ast.Call, ancestors: list[ast.AST]) -> bool:
    for anc in ancestors:
        if isinstance(anc, ast.With):
            for item in anc.items:
                src = ast.dump(item.context_expr)
                if "autocommit_block" in src:
                    return True
    return False


def _lint_body(source: str, tree: ast.Module, report: Report, filename: str) -> None:
    nodes = _nodes_excluding_downgrade(tree)
    created_tables = _collect_created_tables(nodes)

    # ancestry đủ để biết một Call có nằm trong `with ...autocommit_block():` không
    parent: dict[int, ast.AST] = {}
    for n in nodes:
        for child in ast.iter_child_nodes(n):
            parent[id(child)] = n

    def ancestors_of(node: ast.AST) -> list[ast.AST]:
        out = []
        cur = node
        while id(cur) in parent:
            cur = parent[id(cur)]
            out.append(cur)
        return out

    for node in nodes:
        if not isinstance(node, ast.Call):
            continue
        attr = _call_attr(node)
        if attr is None:
            continue

        if attr in _BANNED_CALL_NAMES:
            report.add(filename, "thao tác cấm (§6.1)", attr)

        if attr == "alter_column":
            for kw in node.keywords:
                if kw.arg in _ALTER_COLUMN_BANNED_KWARGS:
                    if kw.arg == "nullable" and not (isinstance(kw.value, ast.Constant) and kw.value.value is False):
                        continue
                    report.add(filename, "alter_column cấm tham số", str(kw.arg))

        if attr == "add_column":
            for arg in node.args:
                if _call_attr(arg) == "Column" and isinstance(arg, ast.Call):
                    kwargs = {kw.arg: kw.value for kw in arg.keywords}
                    nullable = kwargs.get("nullable")
                    is_not_null = isinstance(nullable, ast.Constant) and nullable.value is False
                    if is_not_null and "server_default" not in kwargs:
                        report.add(filename, "add_column NOT NULL thiếu server_default", "")

        if attr in _RAW_SQL_FUNCS:
            first = node.args[0] if node.args else None
            if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
                report.add(filename, f"{attr} đối số không phải hằng chuỗi", "")
            elif _SQL_DANGER_RE.search(first.value):
                report.add(filename, f"{attr} chuỗi SQL cấm", first.value)

        if attr == "create_index":
            table_name: str | None = None
            if len(node.args) >= 2:
                t = node.args[1]
                if isinstance(t, ast.Constant) and isinstance(t.value, str):
                    table_name = t.value
            kwargs = {kw.arg: kw.value for kw in node.keywords}
            if table_name is None:
                kw_table = kwargs.get("table_name")
                if isinstance(kw_table, ast.Constant) and isinstance(kw_table.value, str):
                    table_name = kw_table.value
            if table_name is not None and table_name not in created_tables:
                concurrently = kwargs.get("postgresql_concurrently")
                has_concurrently = isinstance(concurrently, ast.Constant) and concurrently.value is True
                if not has_concurrently:
                    report.add(filename, "create_index thiếu postgresql_concurrently=True", table_name)
                elif not _in_autocommit_block(node, ancestors_of(node)):
                    report.add(filename, "create_index CONCURRENTLY ngoài autocommit_block", table_name)


def _lint_file(path: Path, contracts: set[str], report: Report) -> None:
    try:
        rel = str(path.relative_to(REPO_ROOT))
    except ValueError:
        rel = str(path)  # test dùng thư mục tạm ngoài repo
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=rel)
    except SyntaxError as e:
        report.add(rel, "lỗi cú pháp", str(e))
        return

    revision = _module_level_str(tree, "revision")
    if revision is None:
        report.add(rel, 'thiếu biến revision = "..."', "")
    else:
        for problem in _validate_revision_id(revision):
            report.add(rel, "tên revision", problem)

    has_contract_comment = any(_CONTRACT_COMMENT_RE.match(line) for line in source.splitlines()[:10])
    if has_contract_comment and (revision is None or revision not in contracts):
        report.add(rel, "# contract: chưa đăng ký ở docs/contracts.toml", revision or "?")

    _lint_body(source, tree, report, rel)


def _load_contracts() -> set[str]:
    if not CONTRACTS_TOML.is_file():
        return set()
    data = tomllib.loads(CONTRACTS_TOML.read_text(encoding="utf-8"))
    return set(data.get("revisions", []))


def run(versions_dir: Path = VERSIONS_DIR) -> Report:
    report = Report()
    if not versions_dir.is_dir():
        return report

    contracts = _load_contracts()
    files = sorted(p for p in versions_dir.glob("*.py") if p.name != "__init__.py")
    for f in files:
        _lint_file(f, contracts, report)
    return report


def main(argv: list[str] | None = None) -> int:
    """`python -m tools.lint_migrations [thư mục versions]` (mặc định của repo)."""
    args = sys.argv[1:] if argv is None else argv
    versions_dir = Path(args[0]) if args else VERSIONS_DIR
    if not versions_dir.is_dir():
        print("lint_migrations: 0 revision")
        return 0

    report = run(versions_dir)
    n = len([p for p in versions_dir.glob("*.py") if p.name != "__init__.py"])
    if report.ok:
        print(f"lint_migrations: đạt ({n} revision)")
        return 0
    print(f"lint_migrations: hỏng ({n} revision)")
    for v in report.violations:
        print(f"  - {v.file}: [{v.rule}] {v.detail}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
