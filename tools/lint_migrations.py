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

# Phá huỷ: cấm trong expand, miễn cho revision contract đã đăng ký (FIX-038).
_DESTRUCTIVE_CALL_NAMES = {"drop_table", "drop_column", "drop_constraint", "rename_table"}
# Không phá huỷ nhưng dựng lại cả bảng (chép dữ liệu, khoá bảng): cấm cả trong contract.
_BATCH_ALTER_TABLE = "batch_alter_table"
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
            return _const_str(node.value)
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


def _const_str(node: ast.AST | None) -> str | None:
    """Giá trị của hằng chuỗi; `None` với mọi thứ khác (biến, f-string, thiếu đối số)."""
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _is_const(node: ast.AST | None, value: bool) -> bool:
    """`node` là đúng hằng `True`/`False` viết trong mã (biểu thức tính ra thì không tính)."""
    return isinstance(node, ast.Constant) and node.value is value


def _keywords(call: ast.Call) -> dict[str | None, ast.expr]:
    """Tham số khoá của một lời gọi; `**kw` mang khoá `None`."""
    return {kw.arg: kw.value for kw in call.keywords}


def _collect_created_tables(nodes: list[ast.AST]) -> set[str]:
    """Bảng tạo trong chính revision: index trên chúng chưa khoá ai, khỏi cần `CONCURRENTLY`."""
    calls = [n for n in nodes if isinstance(n, ast.Call) and _call_attr(n) == "create_table" and n.args]
    return {name for call in calls if (name := _const_str(call.args[0])) is not None}


def _ancestors(node: ast.AST, parents: dict[int, ast.AST]) -> list[ast.AST]:
    """Chuỗi node cha của `node`, gần nhất trước."""
    out: list[ast.AST] = []
    while id(node) in parents:
        node = parents[id(node)]
        out.append(node)
    return out


def _in_autocommit_block(ancestors: list[ast.AST]) -> bool:
    """Có tổ tiên `with ...autocommit_block():`: `CREATE INDEX CONCURRENTLY` không chạy được trong giao dịch."""
    return any(
        "autocommit_block" in ast.dump(item.context_expr)
        for anc in ancestors
        if isinstance(anc, ast.With)
        for item in anc.items
    )


@dataclass(frozen=True)
class _Finding:
    """Vi phạm của một lời gọi; `destructive` = luật phá huỷ của expand, miễn cho contract đã đăng ký."""

    rule: str
    detail: str
    destructive: bool


def _check_banned_call(attr: str) -> list[_Finding]:
    """Thao tác cấm (§6.1): tên trong `_DESTRUCTIVE_CALL_NAMES` miễn cho contract, `batch_alter_table` thì không."""
    if attr in _DESTRUCTIVE_CALL_NAMES:
        return [_Finding("thao tác cấm (§6.1)", attr, destructive=True)]
    if attr == _BATCH_ALTER_TABLE:
        return [_Finding("thao tác cấm (§6.1)", attr, destructive=False)]
    return []


def _check_alter_column(node: ast.Call) -> list[_Finding]:
    """`alter_column` đổi tên, đổi kiểu hay `nullable=False` làm hỏng mã cũ còn chạy song song (expand)."""
    return [
        _Finding("alter_column cấm tham số", str(kw.arg), destructive=True)
        for kw in node.keywords
        if kw.arg in _ALTER_COLUMN_BANNED_KWARGS and (kw.arg != "nullable" or _is_const(kw.value, False))
    ]


def _check_add_column(node: ast.Call) -> list[_Finding]:
    """`add_column` NOT NULL thiếu `server_default` hỏng trên bảng đã có dòng."""
    columns = [arg for arg in node.args if isinstance(arg, ast.Call) and _call_attr(arg) == "Column"]
    return [
        _Finding("add_column NOT NULL thiếu server_default", "", destructive=True)
        for kwargs in map(_keywords, columns)
        if _is_const(kwargs.get("nullable"), False) and "server_default" not in kwargs
    ]


def _check_raw_sql(node: ast.Call, attr: str) -> list[_Finding]:
    """SQL thô: không phải hằng thì không duyệt được (cấm cả contract); hằng có từ khoá phá huỷ thì cấm expand."""
    sql = _const_str(node.args[0]) if node.args else None
    if sql is None:
        return [_Finding(f"{attr} đối số không phải hằng chuỗi", "", destructive=False)]
    if _SQL_DANGER_RE.search(sql):
        return [_Finding(f"{attr} chuỗi SQL cấm", sql, destructive=True)]
    return []


def _check_create_index(node: ast.Call, created_tables: set[str], parents: dict[int, ast.AST]) -> list[_Finding]:
    """Index trên bảng có sẵn khoá bảng trừ khi `CONCURRENTLY` trong `autocommit_block` (cấm cả contract)."""
    kwargs = _keywords(node)
    positional = _const_str(node.args[1]) if len(node.args) >= 2 else None
    table = positional if positional is not None else _const_str(kwargs.get("table_name"))
    if table is None or table in created_tables:
        return []
    if not _is_const(kwargs.get("postgresql_concurrently"), True):
        return [_Finding("create_index thiếu postgresql_concurrently=True", table, destructive=False)]
    if not _in_autocommit_block(_ancestors(node, parents)):
        return [_Finding("create_index CONCURRENTLY ngoài autocommit_block", table, destructive=False)]
    return []


def _check_call(node: ast.Call, attr: str, created_tables: set[str], parents: dict[int, ast.AST]) -> list[_Finding]:
    """Luật của §6.1 cho lời gọi `<x>.<attr>(...)`; mỗi tên thuộc đúng một luật."""
    if attr == "alter_column":
        return _check_alter_column(node)
    if attr == "add_column":
        return _check_add_column(node)
    if attr in _RAW_SQL_FUNCS:
        return _check_raw_sql(node, attr)
    if attr == "create_index":
        return _check_create_index(node, created_tables, parents)
    return _check_banned_call(attr)


def _lint_body(tree: ast.Module, report: Report, filename: str, *, contract: bool = False) -> None:
    """Luật thân revision (BE-00 §6.1), bỏ thân `downgrade()`.

    `contract` = revision `# contract:` đã đăng ký: luật phá huỷ của expand (drop, rename,
    NOT NULL, chuỗi SQL nguy hiểm) không áp — phá huỷ chính là việc của revision contract.
    Vẫn áp: SQL không phải hằng (không đọc được thì không duyệt được), `batch_alter_table`,
    index khoá bảng có sẵn (khoá bảng không phụ thuộc expand hay contract).
    """
    nodes = _nodes_excluding_downgrade(tree)
    created_tables = _collect_created_tables(nodes)
    # cha của từng node: đủ để biết một Call có nằm trong `with ...autocommit_block():` không
    parents = {id(child): node for node in nodes for child in ast.iter_child_nodes(node)}
    for node in nodes:
        if not isinstance(node, ast.Call) or (attr := _call_attr(node)) is None:
            continue
        for finding in _check_call(node, attr, created_tables, parents):
            if not (contract and finding.destructive):
                report.add(filename, finding.rule, finding.detail)


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
    registered = revision is not None and revision in contracts
    if has_contract_comment and not registered:
        report.add(rel, "# contract: chưa đăng ký ở docs/contracts.toml", revision or "?")

    _lint_body(tree, report, rel, contract=has_contract_comment and registered)


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
