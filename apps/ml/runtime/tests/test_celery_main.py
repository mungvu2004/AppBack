"""Điểm vào worker `ml`: nhập được, dò task một cấp, chặn bộ giả ở môi trường thật (tiến trình mới)."""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]

SCRIPT = textwrap.dedent(
    """
    import apps.ml.celery_main as main
    assert main.app.main == "ml"
    try:
        main.check_worker()
    except RuntimeError as exc:
        print("refused:", exc)
    else:
        print("started")
    """
)

ENV_BASE = {
    "PUBLIC_BASE_URL": "https://appback.test",
    "SECRET_KEY": "khoa-thu-cho-worker-ml-0123456789abcd",
}


@pytest.mark.parametrize(
    ("app_env", "backend", "expected"),
    [
        ("test", "fake", "started"),
        ("production", "onnx", "started"),
        ("staging", "fake", "refused: ML_BACKEND=fake bị cấm ở APP_ENV=staging"),
        ("production", "fake", "refused: ML_BACKEND=fake bị cấm ở APP_ENV=production"),
    ],
)
def test_celery_main_imports(messaging_env: None, app_env: str, backend: str, expected: str) -> None:
    """`worker_init` kiểm broker `noeviction` (Redis thật) và từ chối `ML_BACKEND=fake` ở staging/production."""
    env = {**os.environ, **ENV_BASE, "APP_ENV": app_env, "ML_BACKEND": backend}
    result = subprocess.run(  # noqa: S603 — lệnh cố định, chạy chính Python của venv
        [sys.executable, "-c", SCRIPT], cwd=REPO_ROOT, env=env, capture_output=True, text=True, check=False, timeout=120
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines()[-1] == expected
