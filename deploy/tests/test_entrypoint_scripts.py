"""Test tĩnh cho `deploy/nginx/docker-entrypoint.d/*.envsh` (hợp đồng §3, prompt [6]/[8]).

Chạy thẳng script bằng `sh` (không cần Docker) — script chỉ POSIX `sh`, không phụ
thuộc gì bên trong ảnh nginx, nên container verify (Linux) chạy được trực tiếp.
"""

from __future__ import annotations

import os
import shutil
import subprocess

from deploy.tests.support import require_path

_SCRIPT = "deploy/nginx/docker-entrypoint.d/15-s3-public-host.envsh"
_SH = shutil.which("sh") or "/bin/sh"


def _run(env_value: str | None) -> str:
    """Nguồn (`.`) script rồi in `$S3_PUBLIC_HOST`; `env_value=None` nghĩa là biến
    không được đặt (khác với chuỗi rỗng, nhưng script coi hai trường hợp như nhau
    qua `${S3_PUBLIC_ENDPOINT:-}`)."""
    path = require_path(_SCRIPT)
    env: dict[str, str] = {"PATH": os.environ.get("PATH", "/usr/bin:/bin")}
    if env_value is not None:
        env["S3_PUBLIC_ENDPOINT"] = env_value
    # Đường sh tuyệt đối (S607) và mọi đối số cố định trong repo, không phải
    # input người dùng (S603) — chỉ chạy chính script đang kiểm.
    result = subprocess.run(  # noqa: S603 — script + đối số cố định trong repo
        [_SH, "-c", f'. "{path}" && printf "%s" "$S3_PUBLIC_HOST"'],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def test_s3_public_host_envsh_falls_back_to_underscore_when_endpoint_empty() -> None:
    """`S3_PUBLIC_ENDPOINT` rỗng hoặc không đặt → `S3_PUBLIC_HOST=_` (không khớp
    Host nào thật, thay vì rỗng làm `server_name ;` hỏng `nginx -t`, review
    2026-09-22 #4, probe Q4)."""
    assert _run(None) == "_"
    assert _run("") == "_"


def test_s3_public_host_envsh_strips_scheme_port_and_path() -> None:
    """Có `S3_PUBLIC_ENDPOINT`: giữ hành vi cũ — chỉ tên host, bỏ scheme/cổng/đường."""
    assert _run("http://localhost:9000") == "localhost"
    assert _run("https://s3.example.com/bucket") == "s3.example.com"
