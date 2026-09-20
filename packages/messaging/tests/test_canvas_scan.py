"""Quét AST toàn repo: cấm chord/group/chain, cấm `.delay()`/`.apply_async()` trong `apps/api`.

Hiến chương điều phối pipeline bằng **trạng thái trong DB**, không bằng kết quả task
(K34), và `apps/api` gửi việc bằng `send_task(tên, payload)` để khỏi nhập mã worker
(BE-00 §7). Hai luật đó không có cổng nào khác bắt được, nên bắt ở đây và bắt cho cả
mã của prompt viết sau.

Quét bằng AST chứ không bằng chuỗi, nên chính file này — chỉ nhắc các tên đó trong
chuỗi và chú thích — không tự làm mình hỏng.
"""

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
CANVAS_MODULES = frozenset({"celery", "celery.canvas"})
CANVAS_NAMES = frozenset({"chord", "group", "chain"})
SEND_METHODS = frozenset({"delay", "apply_async"})
API_PREFIX = ("apps", "api")


def findings_in(source: str, relative: Path) -> list[str]:
    """Vi phạm trong một file, mỗi dòng một câu đủ để sửa mà không phải mở lại file."""
    tree = ast.parse(source, filename=str(relative))
    under_api = relative.parts[:2] == API_PREFIX
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in CANVAS_MODULES:
            found += [
                f"{relative}:{node.lineno} nhập {alias.name} của celery canvas (K34)"
                for alias in node.names
                if alias.name in CANVAS_NAMES
            ]
        if (
            under_api
            and isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in SEND_METHODS
        ):
            found.append(f"{relative}:{node.lineno} gọi .{node.func.attr}() trong apps/api (BE-00 §7)")
    return found


def scan(root: Path) -> list[str]:
    """Mọi vi phạm dưới `packages/` và `apps/` của một cây mã."""
    found: list[str] = []
    for directory in ("packages", "apps"):
        for path in sorted((root / directory).rglob("*.py")):
            found += findings_in(path.read_text(encoding="utf-8"), path.relative_to(root))
    return found


def test_the_repository_uses_neither_canvas_nor_direct_task_calls() -> None:
    assert scan(REPO_ROOT) == []


@pytest.fixture
def fake_tree(tmp_path: Path) -> Path:
    (tmp_path / "packages" / "somewhere").mkdir(parents=True)
    (tmp_path / "apps" / "api" / "orders").mkdir(parents=True)
    return tmp_path


def test_the_scan_catches_a_canvas_import(fake_tree: Path) -> None:
    (fake_tree / "packages" / "somewhere" / "flow.py").write_text("from celery import chord\n", encoding="utf-8")

    assert [line.split(" ", 1)[1] for line in scan(fake_tree)] == ["nhập chord của celery canvas (K34)"]


def test_the_scan_catches_a_canvas_import_from_the_canvas_module(fake_tree: Path) -> None:
    (fake_tree / "packages" / "somewhere" / "flow.py").write_text(
        "from celery.canvas import group, chain\n", encoding="utf-8"
    )

    assert len(scan(fake_tree)) == 2


def test_importing_something_else_from_celery_is_fine(fake_tree: Path) -> None:
    (fake_tree / "packages" / "somewhere" / "flow.py").write_text("from celery import shared_task\n", encoding="utf-8")

    assert scan(fake_tree) == []


@pytest.mark.parametrize("call", ["ship.delay(1)", "ship.apply_async(args=[1])"])
def test_the_scan_catches_direct_task_calls_in_the_api(fake_tree: Path, call: str) -> None:
    (fake_tree / "apps" / "api" / "orders" / "service.py").write_text(f"{call}\n", encoding="utf-8")

    assert len(scan(fake_tree)) == 1


def test_direct_task_calls_outside_the_api_are_not_this_rule(fake_tree: Path) -> None:
    """Test của gói này gọi `.apply()`; luật chỉ chặn `apps/api`."""
    (fake_tree / "packages" / "somewhere" / "flow.py").write_text("ship.delay(1)\n", encoding="utf-8")

    assert scan(fake_tree) == []
