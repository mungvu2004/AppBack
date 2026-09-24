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


LEAKED_ENV = ("SECRET_KEY", "PUBLIC_BASE_URL", "REDIS_CACHE_URL")
"""Ba biến `ml` không được cần: khoá gốc ký JWT, URL công khai và DSN `redis-cache` (NO-085)."""


@pytest.mark.parametrize(
    ("app_env", "backend", "expected"),
    [
        ("test", "onnx", "started"),
        ("production", "fake", "refused: ML_BACKEND=fake bị cấm ở APP_ENV=production"),
    ],
)
def test_celery_main_starts_without_the_signing_key(
    messaging_env: None, app_env: str, backend: str, expected: str
) -> None:
    """NO-085: `ml` chỉ cần `APP_ENV`, không cần `SECRET_KEY`/`PUBLIC_BASE_URL`/`REDIS_CACHE_URL`.

    Tiến trình nạp trọng số ngoài mà cầm khoá gốc ký JWT là trái tách quyền của BE-00
    §2.1/§9 — nó chỉ đọc `APP_ENV` để chặn bộ giả ở môi trường thật. Vế `production`+`fake`
    chứng minh `APP_ENV` thật sự được đọc chứ không rơi về mặc định.
    """
    env = {key: value for key, value in os.environ.items() if key not in LEAKED_ENV}
    env |= {"APP_ENV": app_env, "ML_BACKEND": backend}

    result = subprocess.run(  # noqa: S603 — lệnh cố định, chạy chính Python của venv
        [sys.executable, "-c", SCRIPT], cwd=REPO_ROOT, env=env, capture_output=True, text=True, check=False, timeout=120
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines()[-1] == expected


EXPORTER_SCRIPT = textwrap.dedent(
    """
    from celery.signals import worker_process_init
    import apps.ml.celery_main  # nhập điểm vào thật để dây tín hiệu được gắn
    print("wired:", worker_process_init.has_listeners())
    """
)


def test_the_ml_process_inherits_the_shared_metrics_exporter(messaging_env: None) -> None:
    """NO-161 phần B5-01: `ml` dựng app bằng `create_celery`, nên nhận luôn exporter chung.

    Dây nối khai một lần ở `packages/messaging/celery_app.py` cho cả `worker` lẫn `ml`
    (R-07); test này kiểm nó có mặt ở **điểm vào thật của ảnh `ml`**, trong một tiến trình
    mới không có `SECRET_KEY`.
    """
    env = {key: value for key, value in os.environ.items() if key not in LEAKED_ENV}
    env |= {"APP_ENV": "test", "METRICS_PORT": "0"}

    result = subprocess.run(  # noqa: S603 — lệnh cố định, chạy chính Python của venv
        [sys.executable, "-c", EXPORTER_SCRIPT],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines()[-1] == "wired: True"
