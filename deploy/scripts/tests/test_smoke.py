"""Test `deploy/scripts/smoke.sh` — 5 kiểm smoke với máy chủ HTTP thử."""

from __future__ import annotations

import time
from pathlib import Path

from deploy.scripts.tests.support import REPO_ROOT, HttpStub, Reply, run_script

SCRIPT = REPO_ROOT / "deploy" / "scripts" / "smoke.sh"

FULL_ROUTES = {
    "/api/health": Reply(200),
    "/api/ready": Reply(200),
    "/": Reply(200, headers={"Content-Security-Policy": "default-src 'self'"}),
    "/draco/draco_decoder.wasm": Reply(200, body=b"wasm"),
    "/api/nope": Reply(404, body=b'{"code":"NOT_FOUND"}'),
}


def test_smoke_all_routes_pass() -> None:
    """Đủ 5 route đúng hợp đồng → thoát 0, mỗi kiểm in một dòng "đạt"."""
    with HttpStub(FULL_ROUTES) as stub:
        result = run_script(SCRIPT, [stub.url])
    assert result.returncode == 0, result.stderr
    assert result.stdout.count("đạt") == 5


def test_smoke_missing_csp_header_fails() -> None:
    """Trang / thiếu Content-Security-Policy → kiểm / hỏng, thoát 1."""
    routes = dict(FULL_ROUTES)
    routes["/"] = Reply(200)
    with HttpStub(routes) as stub:
        result = run_script(SCRIPT, [stub.url])
    assert result.returncode == 1
    assert "hỏng /" in result.stdout


def test_smoke_missing_draco_route_fails() -> None:
    """Thiếu /draco/draco_decoder.wasm (404 mặc định của stub) → hỏng, thoát 1."""
    routes = dict(FULL_ROUTES)
    del routes["/draco/draco_decoder.wasm"]
    with HttpStub(routes) as stub:
        result = run_script(SCRIPT, [stub.url])
    assert result.returncode == 1
    assert "hỏng /draco/draco_decoder.wasm" in result.stdout


def test_smoke_nope_without_code_key_fails() -> None:
    """/api/nope 404 nhưng thân không có khoá "code" → hỏng, thoát 1."""
    routes = dict(FULL_ROUTES)
    routes["/api/nope"] = Reply(404, body=b"{}")
    with HttpStub(routes) as stub:
        result = run_script(SCRIPT, [stub.url])
    assert result.returncode == 1
    assert "hỏng /api/nope" in result.stdout


def test_smoke_max_time_uses_remaining_budget_not_fixed_10s() -> None:
    """Review round 1 P3 (RES-02): mỗi `curl` phải dùng phần ngân sách CÒN LẠI của
    `SMOKE_DEADLINE_S`, không phải 10s cố định — route treo lâu hơn cả ngân sách tổng phải bị
    `--max-time` chặn gần đúng ngân sách, không để tổng vọt lên ~70s như trước."""
    routes = dict(FULL_ROUTES)
    routes["/api/health"] = Reply(200, delay_s=5.0)  # dài hơn cả SMOKE_DEADLINE_S=2 bên dưới
    with HttpStub(routes) as stub:
        start = time.monotonic()
        result = run_script(SCRIPT, [stub.url], env={"SMOKE_DEADLINE_S": "2"}, timeout=20)
        elapsed = time.monotonic() - start
    assert result.returncode == 1
    assert elapsed < 8, f"elapsed={elapsed:.1f}s — --max-time vẫn cố định 10s thay vì ngân sách còn lại"


def test_smoke_missing_argument_exits_2(tmp_path: Path) -> None:
    """Không đối số → thoát 2, không gọi HTTP."""
    result = run_script(SCRIPT, [], env={"HOME": str(tmp_path)})
    assert result.returncode == 2
