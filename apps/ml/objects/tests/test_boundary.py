"""Ranh giới nhập của `apps.ml.objects` (BE-00 §12, K của [9]): tiến trình con, không `skip`.

Chép khuôn `apps/ml/runtime/tests/test_imports.py`. Module này (và các module con
`labels`, `tiles`, `detector`, `tasks`) không được kéo `sqlalchemy`, `fastapi`, `torch`,
`ultralytics` — kể cả khi các thư viện đó có mặt trong môi trường verify.
"""

import subprocess
import sys
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]


def test_objects_import_without_db_web_or_torch_stack() -> None:
    """Nhập `apps.ml.objects` và các module con khi `sqlalchemy`, `fastapi`, `torch`, `ultralytics` bị chặn."""
    script = textwrap.dedent(
        """
        import importlib, importlib.abc, sys

        class Block(importlib.abc.MetaPathFinder):
            def find_spec(self, name, path=None, target=None):
                top = name.split(".")[0]
                if top in ("sqlalchemy", "fastapi", "torch", "ultralytics"):
                    raise ImportError("chặn " + name)
                return None

        sys.meta_path.insert(0, Block())
        for module in ("apps.ml.objects", "apps.ml.objects.labels", "apps.ml.objects.tiles",
                       "apps.ml.objects.detector", "apps.ml.objects.tasks"):
            importlib.import_module(module)
        print("ok")
        """
    )
    result = subprocess.run(  # noqa: S603 — lệnh cố định, chạy chính Python của venv
        [sys.executable, "-c", script], cwd=REPO_ROOT, capture_output=True, text=True, check=False, timeout=120
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"
