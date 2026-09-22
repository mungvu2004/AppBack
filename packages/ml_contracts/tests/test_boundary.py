"""Ranh giới nhập của `packages.ml_contracts` ([9] B5-01, BE-00 §12: tiến trình Python mới)."""

import subprocess
import sys
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

BLOCKED = ("torch", "onnxruntime", "packages.messaging", "packages.storage", "apps")
MODULES = (
    "families",
    "pinned",
    "labels",
    "payloads",
    "artifacts",
    "datasets",
    "ports",
    "fakes",
    "synthetic",
    "_png",
    "_font",
)


def test_ml_contracts_boundary() -> None:
    """Nhập mọi module của gói khi `torch`, `onnxruntime`, `messaging`, `storage`, `apps` bị chặn."""
    script = textwrap.dedent(
        f"""
        import importlib, importlib.abc, sys

        BLOCKED = {BLOCKED!r}

        class Block(importlib.abc.MetaPathFinder):
            def find_spec(self, name, path=None, target=None):
                if any(name == item or name.startswith(item + ".") for item in BLOCKED):
                    raise ImportError("chặn " + name)
                return None

        sys.meta_path.insert(0, Block())
        for module in {MODULES!r}:
            importlib.import_module("packages.ml_contracts." + module)
        print("ok")
        """
    )
    result = subprocess.run(  # noqa: S603 — lệnh cố định, chạy chính Python của venv
        [sys.executable, "-c", script], cwd=REPO_ROOT, capture_output=True, text=True, check=False, timeout=120
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"


def test_package_init_is_docstring_only() -> None:
    source = (REPO_ROOT / "packages" / "ml_contracts" / "__init__.py").read_text(encoding="utf-8")
    assert source.startswith('"""')
    assert source.strip().endswith('"""')
    assert source.count('"""') == 2
