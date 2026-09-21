"""Ranh giới nhập của `apps/api/auth` (BE-00 §2.1, §7, §12): chạy trong tiến trình Python mới."""

import os
import subprocess
import sys
from pathlib import Path
from typing import Final

REPO_ROOT: Final = Path(__file__).resolve().parents[4]
WORKER_BLOCKED: Final = ("fastapi", "starlette", "jwt", "argon2")
CONFIG_ENV: Final = ("APP_ENV", "PUBLIC_BASE_URL", "SECRET_KEY", "DATABASE_URL", "REDIS_BROKER_URL", "REDIS_CACHE_URL")


def _python(code: str, *, stdin: str = "", env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Chạy một đoạn Python ở gốc repo, trả kết quả (không ném khi mã thoát khác 0)."""
    return subprocess.run(  # noqa: S603 — trình thông dịch của chính tiến trình test, mã cố định
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        env=env,
    )


def test_jobs_import_without_web_or_crypto_packages() -> None:
    """Worker nhập `apps.api.auth.jobs` để chạy beat: nhập được khi `fastapi`, `starlette`, `jwt`, `argon2` bị chặn."""
    blocked = "; ".join(f"sys.modules[{name!r}] = None" for name in WORKER_BLOCKED)
    result = _python(f"import sys; {blocked}; import apps.api.auth.jobs")
    assert result.returncode == 0, result.stderr


def test_cli_import_does_not_read_stdin() -> None:
    """Nhập `apps.api.auth.cli` không đọc stdin, không chạy `main` (B0-06 nhập mọi module)."""
    result = _python("import sys, apps.api.auth.cli; sys.stdout.write(sys.stdin.read())", stdin="giu-nguyen")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "giu-nguyen"


def test_modules_import_without_any_configuration() -> None:
    """Không biến môi trường nào: mọi module nhập được, không đọc cấu hình, không dựng executor băm."""
    env = {name: value for name, value in os.environ.items() if name not in CONFIG_ENV}
    code = (
        "import apps.api.auth.router, apps.api.auth.verifier, apps.api.auth.jobs; "
        "from apps.api.auth import passwords, settings; "
        "assert passwords._executor is None; "
        "assert settings.get_auth_settings.cache_info().currsize == 0"
    )
    result = _python(code, env=env)
    assert result.returncode == 0, result.stderr
