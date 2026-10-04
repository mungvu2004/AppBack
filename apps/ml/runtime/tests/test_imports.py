"""Luật nhập của `apps/ml` (M03, BE-00 §9, [9] B5-01) — AST và tiến trình Python mới (BE-00 §12)."""

import ast
import subprocess
import sys
import textwrap
from collections.abc import Iterator
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SCANNED = (REPO_ROOT / "apps" / "ml", REPO_ROOT / "packages" / "ml_contracts")
ULTRALYTICS_ALLOWED = (
    "apps/ml/runtime/export_yolo.py",
    "apps/ml/runtime/ultralytics_import.py",
    "apps/ml/training_yolo/",
)
BANNED_MODULES = ("pickle", "joblib", "dill", "cloudpickle")
ULTRALYTICS_GATES = ("prepare_ultralytics", "import_ultralytics")


def _module_level(node: ast.AST) -> Iterator[ast.AST]:
    """Mọi nút chạy lúc nhập module: đi vào if/try/with/class cấp module, bỏ qua thân hàm."""
    for child in ast.iter_child_nodes(node):
        if not isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
            yield child
            yield from _module_level(child)


def _findings(tree: ast.AST, rel: str) -> Iterator[str]:
    """Vi phạm trong một module.

    Mã sản phẩm: `torch.load`, nhập pickle/joblib, `ultralytics` ngoài chỗ cho phép. Tệp test chỉ chịu
    luật `ultralytics` (test được nhập pickle), và được nhập nó khi tệp đó nhập một cổng
    (`ULTRALYTICS_GATES`), nhưng chỉ trong thân hàm: nhập cấp module chạy trước mọi cổng nên vẫn bị bắt
    — nhập trần vá `PIL.Image.open` toàn tiến trình (NO-322, NO-323).
    """
    in_tests = "/tests/" in rel
    allowed_path = rel.startswith(ULTRALYTICS_ALLOWED)
    gated = in_tests and any(isinstance(node, ast.alias) and node.name in ULTRALYTICS_GATES for node in ast.walk(tree))
    ultralytics_ok = allowed_path or gated
    module_level = {id(node) for node in _module_level(tree)} if gated and not allowed_path else set()
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module, *(f"{node.module}.{alias.name}" for alias in node.names)]
        elif (
            not in_tests
            and isinstance(node, ast.Attribute)
            and node.attr == "load"
            and ast.unparse(node.value) == "torch"
        ):
            yield f"{rel}: torch.load"
        for name in names:
            top = name.split(".")[0]
            if not in_tests and (top in BANNED_MODULES or name == "torch.load"):
                yield f"{rel}: nhập {name}"
            if top == "ultralytics" and not ultralytics_ok:
                yield f"{rel}: nhập ultralytics ngoài chỗ cho phép"
            elif top == "ultralytics" and id(node) in module_level:
                yield f"{rel}: nhập ultralytics cấp module trong tệp test"


def scan(root: Path) -> list[str]:
    """Vi phạm luật nhập trong mọi `*.py` dưới `SCANNED` của `root` (kể cả tệp test), theo thứ tự đường dẫn."""
    found: list[str] = []
    for base in SCANNED:
        for path in sorted((root / base.relative_to(REPO_ROOT)).rglob("*.py")):
            rel = path.relative_to(root).as_posix()
            found.extend(_findings(ast.parse(path.read_text(encoding="utf-8")), rel))
    return found


def test_ml_imports_m03_ast(tmp_path: Path) -> None:
    """Mã sản phẩm của `apps/ml`, `ml_contracts` sạch; bộ quét bắt được từng kiểu vi phạm (không rỗng giả)."""
    assert scan(REPO_ROOT) == []
    bad = tmp_path / "apps" / "ml" / "evil"
    bad.mkdir(parents=True)
    (tmp_path / "packages" / "ml_contracts").mkdir(parents=True)
    (bad / "x.py").write_text(
        "import pickle\nimport torch\nfrom joblib import load\nfrom ultralytics import YOLO\nw = torch.load('w.pt')\n",
        encoding="utf-8",
    )
    assert scan(tmp_path) == [
        "apps/ml/evil/x.py: nhập pickle",
        "apps/ml/evil/x.py: nhập joblib",
        "apps/ml/evil/x.py: nhập joblib.load",
        "apps/ml/evil/x.py: nhập ultralytics ngoài chỗ cho phép",
        "apps/ml/evil/x.py: nhập ultralytics ngoài chỗ cho phép",
        "apps/ml/evil/x.py: torch.load",
    ]


def test_scan__flags_bare_ultralytics_in_test_files(tmp_path: Path) -> None:
    """Chặn tái phát NO-323: tệp test nhập `ultralytics` mà không qua cổng → bị bắt; qua cổng thì được."""
    tests = tmp_path / "apps" / "ml" / "evil" / "tests"
    tests.mkdir(parents=True)
    (tmp_path / "packages" / "ml_contracts").mkdir(parents=True)
    (tests / "test_bare.py").write_text("import ultralytics\nimport pickle\n", encoding="utf-8")
    (tests / "test_gated.py").write_text(
        "from apps.ml.runtime.ultralytics_import import import_ultralytics\n"
        "def test_x():\n    import_ultralytics()\n    import ultralytics\n",
        encoding="utf-8",
    )
    (tests / "test_module_level.py").write_text(
        "from apps.ml.runtime.ultralytics_import import import_ultralytics\n"
        "import ultralytics\ndef test_x():\n    import_ultralytics()\n",
        encoding="utf-8",
    )
    (tests / "test_module_try.py").write_text(
        "from apps.ml.runtime.ultralytics_import import import_ultralytics\n"
        "try:\n    from ultralytics import YOLO\nexcept ImportError:\n    YOLO = None\n",
        encoding="utf-8",
    )
    assert scan(tmp_path) == [
        "apps/ml/evil/tests/test_bare.py: nhập ultralytics ngoài chỗ cho phép",
        "apps/ml/evil/tests/test_module_level.py: nhập ultralytics cấp module trong tệp test",
        "apps/ml/evil/tests/test_module_try.py: nhập ultralytics cấp module trong tệp test",
        "apps/ml/evil/tests/test_module_try.py: nhập ultralytics cấp module trong tệp test",
    ]


def test_runtime_imports_without_torch_or_forbidden_packages() -> None:
    """Nhập runtime (trừ `export*.py`) không kéo `torch`/`transformers`/`ultralytics`; không nhập db, api, worker."""
    script = textwrap.dedent(
        """
        import importlib, importlib.abc, sys

        class Block(importlib.abc.MetaPathFinder):
            def find_spec(self, name, path=None, target=None):
                top = name.split(".")
                if name.startswith(("packages.db", "apps.api", "apps.worker")) or top[0] in (
                    "torch", "transformers", "ultralytics", "sqlalchemy", "asyncpg", "fastapi"
                ):
                    raise ImportError("chặn " + name)
                return None

        sys.meta_path.insert(0, Block())
        for module in (
            "settings", "errors", "loader", "device", "gpu", "tasks_util", "trainers", "export_pinned",
            "ultralytics_import",
        ):
            importlib.import_module("apps.ml.runtime." + module)
        print("ok")
        """
    )
    result = subprocess.run(  # noqa: S603 — lệnh cố định, chạy chính Python của venv
        [sys.executable, "-c", script], cwd=REPO_ROOT, capture_output=True, text=True, check=False, timeout=120
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"
