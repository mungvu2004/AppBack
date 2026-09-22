"""Quét tĩnh `ci.yml`, `codeql.yml`, `dependabot.yml`, `.gitleaks.toml`, `job.sh` (B0-09).

Không mạng, không dựng ảnh/container — chỉ soi cấu trúc YAML/TOML và đối chiếu
`job.sh` với hợp đồng CLI đã ghim (hop-dong.md §2, prompt B0-09 [8] "Quét
workflow"/"Quét codeql.yml, dependabot.yml"). Cạm bẫy YAML 1.1: PyYAML đọc khoá
trần `on:` thành khoá boolean `True` — `_triggers()` dò cả hai dạng.
"""

from __future__ import annotations

import os
import re
import subprocess
import tomllib
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
CI_YML = REPO_ROOT / ".github" / "workflows" / "ci.yml"
CODEQL_YML = REPO_ROOT / ".github" / "workflows" / "codeql.yml"
DEPENDABOT_YML = REPO_ROOT / ".github" / "dependabot.yml"
GITLEAKS_TOML = REPO_ROOT / ".gitleaks.toml"
JOB_SH = REPO_ROOT / "tools" / "ci" / "job.sh"
COMMIT_MSG_HOOK = REPO_ROOT / ".githooks" / "commit-msg"

EXPECTED_JOBS = ["lint", "typecheck", "unit", "integration", "ml", "contract", "build", "commits", "coverage"]

_SHA_USES_RE = re.compile(r"^[\w.-]+/[\w.-]+(?:/[\w./-]+)?@[0-9a-f]{40}(?:\s*#.*)?$")
_STEPS_ARG_RE = re.compile(r"--steps\s+([0-9,b]+)")

# Ánh xạ job (bảng [2] hop-dong.md) -> bước verify 1-8/5b nó phủ, đọc thẳng từ
# `job.sh` (không chép tay): mỗi job gọi `tools.verify.steps verify --steps
# <n>` cho các bước dùng lại được nguyên; bước 5 không đi qua CLI đó (job chạy
# `coverage run -m pytest --ci-split=<nhóm>` trực tiếp cho unit/integration/ml).
_ALL_VERIFY_STEPS = {"0", "1", "2", "3", "4", "6", "7", "8", "5b"}


def _load_yaml(path: Path) -> dict[Any, Any]:
    """Đọc một workflow YAML thành dict; ném lỗi rõ ràng nếu không phải mapping."""
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert isinstance(data, dict), f"{path}: gốc YAML không phải mapping"
    return data


def _triggers(doc: dict[Any, Any]) -> dict[Any, Any]:
    """`on:` bị PyYAML (YAML 1.1) đọc thành khoá boolean `True` — trả đúng khối kích hoạt."""
    triggers = doc.get("on", doc.get(True, {}))
    assert isinstance(triggers, dict)
    return triggers


def _walk_key(node: Any, key: str) -> list[str]:
    """Duyệt đệ quy toàn cây YAML, gom mọi giá trị chuỗi của khoá `key` (`uses`/`run`)."""
    found: list[str] = []
    if isinstance(node, dict):
        for k, v in node.items():
            if k == key and isinstance(v, str):
                found.append(v)
            found.extend(_walk_key(v, key))
    elif isinstance(node, list):
        for item in node:
            found.extend(_walk_key(item, key))
    return found


# ---------------------------------------------------------------------------
# ci.yml
# ---------------------------------------------------------------------------


def test_ci_yml_has_nine_jobs() -> None:
    doc = _load_yaml(CI_YML)
    assert set(doc["jobs"]) == set(EXPECTED_JOBS)


def test_ci_yml_only_coverage_has_needs() -> None:
    doc = _load_yaml(CI_YML)
    for name, job in doc["jobs"].items():
        if name == "coverage":
            assert job.get("needs") == ["unit", "integration", "ml"]
        else:
            assert "needs" not in job, name


def test_ci_yml_no_continue_on_error() -> None:
    assert "continue-on-error" not in CI_YML.read_text(encoding="utf-8")


def test_ci_yml_coverage_job_has_no_always() -> None:
    doc = _load_yaml(CI_YML)
    coverage_job = doc["jobs"]["coverage"]
    assert "always()" not in str(coverage_job.get("if", ""))
    for step in coverage_job.get("steps", []):
        assert "always()" not in str(step.get("if", ""))


def test_ci_yml_uses_pinned_by_sha() -> None:
    doc = _load_yaml(CI_YML)
    uses_values = _walk_key(doc["jobs"], "uses")
    assert uses_values, "không tìm thấy dòng uses: nào"
    for uses in uses_values:
        assert _SHA_USES_RE.match(uses), f"uses trôi hoặc thiếu SHA 40 ký tự: {uses}"


def test_ci_yml_permissions_contents_read_only() -> None:
    doc = _load_yaml(CI_YML)
    assert doc.get("permissions") == {"contents": "read"}


def test_ci_yml_no_pull_request_target() -> None:
    doc = _load_yaml(CI_YML)
    assert "pull_request_target" not in _triggers(doc)


def test_ci_yml_every_job_calls_job_sh() -> None:
    doc = _load_yaml(CI_YML)
    for name in EXPECTED_JOBS:
        runs = _walk_key(doc["jobs"][name], "run")
        assert any(f"tools/ci/job.sh {name}" in r for r in runs), name


def test_ci_yml_run_steps_never_interpolate_event() -> None:
    doc = _load_yaml(CI_YML)
    for run_body in _walk_key(doc["jobs"], "run"):
        assert "${{ github.event" not in run_body, run_body


def test_ci_yml_checkout_steps_do_not_persist_credentials() -> None:
    """Không job nào push — token chỉ-đọc không cần sống trong `.git/config` suốt các bước sau
    (/merge-review lượt 1 #15)."""
    doc = _load_yaml(CI_YML)
    for name, job in doc["jobs"].items():
        for step in job.get("steps", []):
            if step.get("uses", "").startswith("actions/checkout@"):
                assert step.get("with", {}).get("persist-credentials") is False, f"{name}: {step}"


def test_ci_yml_build_job_uploads_trivy_sarif() -> None:
    """SARIF trivy phải sống qua artifact — container --rm không mount thì mất theo khi xoá
    (/merge-review lượt 1 #3). Bước upload dùng `if: always()` ở MỨC STEP (hợp lệ, [9] chỉ cấm
    `always()` mức job, không cấm bước riêng lẻ trong job)."""
    doc = _load_yaml(CI_YML)
    build_job = doc["jobs"]["build"]
    upload_steps = [
        step for step in build_job.get("steps", []) if step.get("uses", "").startswith("actions/upload-artifact@")
    ]
    assert upload_steps, "job build thiếu bước upload-artifact cho SARIF"
    sarif_step = upload_steps[0]
    assert "trivy" in str(sarif_step["with"]["path"]).lower()
    assert sarif_step.get("if") == "always()"


# ---------------------------------------------------------------------------
# job.sh — hợp các --steps với việc của job, đọc thật từ file (không chép tay)
# ---------------------------------------------------------------------------


def test_job_sh_verify_steps_cover_1_to_8_and_5b() -> None:
    text = JOB_SH.read_text(encoding="utf-8")
    found: set[str] = set()
    for m in _STEPS_ARG_RE.finditer(text):
        found.update(m.group(1).split(","))
    assert found == _ALL_VERIFY_STEPS, f"job.sh thiếu bước verify: {_ALL_VERIFY_STEPS - found}"
    # Bước 5 không đi qua `tools.verify.steps` (unit/integration/ml gọi coverage
    # run -m pytest --ci-split=<nhóm> trực tiếp) — xác nhận bằng chứng riêng.
    assert "coverage run -m pytest" in text


def test_job_sh_pins_docker_images_by_digest() -> None:
    text = JOB_SH.read_text(encoding="utf-8")
    for var in ("GITLEAKS_IMAGE", "TRIVY_IMAGE"):
        m = re.search(rf'{var}="([^"]+)"', text)
        assert m, f"thiếu hằng {var}"
        assert "@sha256:" in m.group(1), f"{var} không ghim digest: {m.group(1)}"


# ---------------------------------------------------------------------------
# job_lint_audit — pip-audit thoát 1 (có lỗ hổng) phải chuyển cho tools.ci.audit
# quyết, không tự "hỏng" (/merge-review lượt 1 #1, P1). Test nguồn thẳng job.sh
# thật (source, không chỉ gọi audit.py) với một `uvx` giả trên PATH.
# ---------------------------------------------------------------------------

_FAKE_UVX = """#!/usr/bin/env bash
# uvx gia: bo qua moi tham so that pip-audit nhan, chi tra ve theo bien moi
# truong ma test dat san — cach ly khoi mang/PyPI that.
printf '%s' "$FAKE_UVX_STDOUT"
exit "${FAKE_UVX_EXIT:-0}"
"""

_VULN_EXEMPTED_JSON = (
    '{"dependencies": [{"name": "demo-pkg", "version": "1.0.0", "vulns": '
    '[{"id": "GHSA-test-0001", "fix_versions": ["1.0.1"], "aliases": []}]}]}'
)
_VULN_UNWAIVED_JSON = (
    '{"dependencies": [{"name": "demo-pkg", "version": "1.0.0", "vulns": '
    '[{"id": "GHSA-test-0002", "fix_versions": ["1.0.1"], "aliases": []}]}]}'
)
_EXEMPT_ALLOWLIST = """
[[ignore]]
id = "GHSA-test-0001"
reason = "fixture cua test merge-review, khong phai loi hong that"
expires = 2099-12-31
"""
_EMPTY_ALLOWLIST = "# rong, khong mien gi\n"


def _run_job_lint_audit(
    tmp_path: Path, *, stdout: str, exit_code: int, allowlist: str
) -> subprocess.CompletedProcess[str]:
    """Nguồn `job.sh` thật rồi gọi thẳng `job_lint_audit` (không kèm ruff/mypy/gitleaks) với `uvx`
    giả trên PATH và `AUDIT_ALLOWLIST` trỏ vào allowlist tạm — đi đúng đường pip-audit →
    tools.ci.audit mà /merge-review lượt 1 #1 đòi, không chỉ gọi `audit.py` riêng."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_uvx = bin_dir / "uvx"
    fake_uvx.write_text(_FAKE_UVX, encoding="utf-8")
    fake_uvx.chmod(0o755)
    allowlist_file = tmp_path / "audit-allowlist.toml"
    allowlist_file.write_text(allowlist, encoding="utf-8")
    script = tmp_path / "run.sh"
    script.write_text(
        f'source "{JOB_SH}"\njob_lint_audit\necho "FAILED=$FAILED"\n[ "$FAILED" -eq 0 ]\n',
        encoding="utf-8",
    )
    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
    env["FAKE_UVX_STDOUT"] = stdout
    env["FAKE_UVX_EXIT"] = str(exit_code)
    env["AUDIT_ALLOWLIST"] = str(allowlist_file)
    return subprocess.run(  # noqa: S603 — script cục bộ dựng trong tmp_path, không nhận input người dùng
        ["bash", str(script)],  # noqa: S607 — "bash" có sẵn trên PATH runner
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_job_sh_pip_audit_exit_1_with_exempted_vuln_passes(tmp_path: Path) -> None:
    """Case thường: pip-audit thoát 1 (có lỗ hổng) nhưng lỗ hổng đã miễn trong allowlist → đạt —
    tools.ci.audit chạy tới và tự quyết, không bị chặn bởi mã thoát 1 của chính pip-audit."""
    result = _run_job_lint_audit(tmp_path, stdout=_VULN_EXEMPTED_JSON, exit_code=1, allowlist=_EXEMPT_ALLOWLIST)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "FAILED=0" in result.stdout


def test_job_sh_pip_audit_exit_1_with_unwaived_fixable_vuln_fails(tmp_path: Path) -> None:
    """Case lỗi: pip-audit thoát 1, lỗ hổng có bản sửa mà chưa miễn → hỏng (tools.ci.audit tự bắt)."""
    result = _run_job_lint_audit(tmp_path, stdout=_VULN_UNWAIVED_JSON, exit_code=1, allowlist=_EMPTY_ALLOWLIST)
    assert result.returncode != 0
    assert "FAILED=1" in result.stdout


def test_job_sh_pip_audit_exit_2_fails(tmp_path: Path) -> None:
    """Case lỗi: pip-audit thoát > 1 (lỗi thật của chính công cụ) → hỏng ngay ở bước pip-audit,
    tools.ci.audit không chạy tới (run_step chặn bước sau khi FAILED đã lên 1)."""
    result = _run_job_lint_audit(tmp_path, stdout="", exit_code=2, allowlist=_EMPTY_ALLOWLIST)
    assert result.returncode != 0
    assert "FAILED=1" in result.stdout


def test_job_sh_smoke_compose_uses_ci_yml_standalone() -> None:
    """Case lỗi (hồi quy): smoke KHÔNG được gộp `base.yml` — service `ml-gpu` của `base.yml` chỉ để
    `extends` (không `image`/`build`), gộp trực tiếp làm `docker compose config` hỏng ngay từ bước
    cấu hình (B0-08 đã kiểm `docker compose -f deploy/compose/ci.yml config -q` exit 0 một mình,
    mỗi service trong `ci.yml` tự `extends: file: base.yml` đúng phần nó cần — bao-cao-c2.md).
    """
    text = JOB_SH.read_text(encoding="utf-8")
    assert "deploy/compose/base.yml" not in text, "job.sh không được gộp base.yml vào project compose"
    assert "-f deploy/compose/ci.yml" in text


def test_job_sh_import_all_passes_service_env_file() -> None:
    """Case lỗi (hồi quy): `import_all` phải nhận env như service thật (`ci.yml`/`base.yml`) — chạy
    ảnh không env khiến `packages.messaging` ăn nhầm lỗi thiếu biến môi trường (fail-fast hợp lệ)
    thay vì lỗi thiếu thư viện thật mà `import_all` cần bắt (case [8])."""
    text = JOB_SH.read_text(encoding="utf-8")
    assert "--env-file deploy/compose/env.example" in text


def test_job_sh_unknown_job_exits_2() -> None:
    result = subprocess.run(  # noqa: S603 — gọi script cục bộ của chính repo, không nhận input người dùng
        ["bash", str(JOB_SH), "nope"],  # noqa: S607 — "bash" cố ý không full path, có sẵn trên PATH runner
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2


def test_job_sh_has_branch_for_every_ci_job() -> None:
    doc = _load_yaml(CI_YML)
    text = JOB_SH.read_text(encoding="utf-8")
    for name in doc["jobs"]:
        assert re.search(rf"^\s*{re.escape(name)}\)\s", text, re.MULTILINE), f"job.sh thiếu nhánh cho '{name}'"


# ---------------------------------------------------------------------------
# codeql.yml
# ---------------------------------------------------------------------------


def test_codeql_yml_uses_pinned_by_sha() -> None:
    doc = _load_yaml(CODEQL_YML)
    uses_values = _walk_key(doc["jobs"], "uses")
    assert uses_values
    for uses in uses_values:
        assert _SHA_USES_RE.match(uses), uses


def test_codeql_yml_analyzes_python_and_actions() -> None:
    doc = _load_yaml(CODEQL_YML)
    languages: set[str] = set()
    for job in doc["jobs"].values():
        matrix = job.get("strategy", {}).get("matrix", {})
        languages.update(matrix.get("language", []))
    assert languages == {"python", "actions"}


def test_codeql_yml_security_events_write_only_on_analyze_job() -> None:
    doc = _load_yaml(CODEQL_YML)
    assert doc.get("permissions", {}).get("security-events") is None
    for name, job in doc["jobs"].items():
        if job.get("permissions", {}).get("security-events") == "write":
            assert name == "analyze", f"job '{name}' không nên có security-events: write"
    assert doc["jobs"]["analyze"]["permissions"]["security-events"] == "write"


# ---------------------------------------------------------------------------
# dependabot.yml
# ---------------------------------------------------------------------------


def test_dependabot_yml_has_three_ecosystems() -> None:
    doc = _load_yaml(DEPENDABOT_YML)
    by_eco = {u["package-ecosystem"]: u for u in doc["updates"]}
    assert set(by_eco) == {"uv", "github-actions", "docker"}
    assert by_eco["uv"]["directory"] == "/"
    assert by_eco["github-actions"]["directory"] == "/"
    assert by_eco["docker"]["directory"] == "/deploy/docker"


def test_dependabot_commit_prefixes_pass_commit_msg_hook(tmp_path: Path) -> None:
    """`uv`/`github-actions` có `directory: "/"` — Dependabot không nối hậu tố thư mục, tiêu đề ngắn,
    đạt bình thường. `docker` (`directory: "/deploy/docker"`) bị tách ra test riêng dưới đây vì thực
    tế luôn dài hơn 72 ký tự (/merge-review lượt 1 #4)."""
    doc = _load_yaml(DEPENDABOT_YML)
    by_eco = {u["package-ecosystem"]: u for u in doc["updates"]}
    samples = {
        "uv": "bump schemathesis from 3.29.4 to 3.30.0",
        "github-actions": "bump actions/checkout from 7.0.0 to 7.0.1",
    }
    for eco, sample in samples.items():
        prefix = by_eco[eco]["commit-message"]["prefix"]
        header = f"{prefix}(deps): {sample}"
        msg_file = tmp_path / f"msg-{eco}.txt"
        msg_file.write_text(header + "\n", encoding="utf-8")
        result = subprocess.run(  # noqa: S603 — hook cục bộ của chính repo, không nhận input người dùng
            ["bash", str(COMMIT_MSG_HOOK), str(msg_file)],  # noqa: S607 — "bash" có sẵn trên PATH runner
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"{eco}: '{header}' bị hook từ chối: {result.stderr}"


def test_dependabot_docker_title_with_directory_suffix_exceeds_72_and_is_rejected(tmp_path: Path) -> None:
    """Case lỗi thật (/merge-review lượt 1 #4): hệ `docker` có `directory` khác `/`, Dependabot nối
    thêm " in /deploy/docker" vào tiêu đề (chữ thường "bump" — định dạng thật của Dependabot khi
    `commit-message.prefix` + `include: scope` cùng khai) → dòng đầu > 72 ký tự, hook `.githooks/
    commit-msg` từ chối đúng luật. Đây chính là lý do `commits.py` bỏ kiểm dòng đầu từng commit cho
    nhánh `dependabot/**` (squash lấy tiêu đề PR, không lấy dòng đầu commit riêng lẻ)."""
    doc = _load_yaml(DEPENDABOT_YML)
    by_eco = {u["package-ecosystem"]: u for u in doc["updates"]}
    prefix = by_eco["docker"]["commit-message"]["prefix"]
    sample = "bump nginxinc/nginx-unprivileged from 1.28.0-alpine to 1.29.1-alpine in /deploy/docker"
    header = f"{prefix}(deps): {sample}"
    assert len(header) > 72
    msg_file = tmp_path / "msg-docker.txt"
    msg_file.write_text(header + "\n", encoding="utf-8")
    result = subprocess.run(  # noqa: S603 — hook cục bộ của chính repo, không nhận input người dùng
        ["bash", str(COMMIT_MSG_HOOK), str(msg_file)],  # noqa: S607 — "bash" có sẵn trên PATH runner
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0


def test_dependabot_wrong_prefix_rejected_by_commit_msg_hook(tmp_path: Path) -> None:
    """Case lỗi: tiêu đề mang tiền tố **sai** hệ (không phải `build`/`ci` đã khai) bị hook từ chối."""
    msg_file = tmp_path / "msg-wrong-prefix.txt"
    msg_file.write_text("deps(uv): Bump schemathesis from 3.29.4 to 3.30.0\n", encoding="utf-8")
    result = subprocess.run(  # noqa: S603 — hook cục bộ của chính repo, không nhận input người dùng
        ["bash", str(COMMIT_MSG_HOOK), str(msg_file)],  # noqa: S607 — "bash" có sẵn trên PATH runner
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0


# ---------------------------------------------------------------------------
# .gitleaks.toml
# ---------------------------------------------------------------------------


def test_gitleaks_toml_exempts_only_env_example_by_path() -> None:
    """Case thường: `paths` chỉ miễn đúng một file — không miễn file test nào theo đường (K24).

    Miễn vĩnh viễn theo đường sẽ bỏ qua cả bí mật thật thêm vào sau này; bí mật giả trong test
    của B0-04/B0-06 được miễn hẹp hơn qua `commits` (xem
    `test_gitleaks_toml_exempts_known_secrets_by_commit_only`).
    """
    with GITLEAKS_TOML.open("rb") as f:
        data = tomllib.load(f)
    assert data["extend"]["useDefault"] is True

    allowlists = data.get("allowlist", [])
    if isinstance(allowlists, dict):
        allowlists = [allowlists]
    all_paths = [p for a in allowlists for p in a.get("paths", [])]

    assert all_paths == [r"^deploy/compose/env\.example$"]
    pattern = re.compile(all_paths[0])
    assert pattern.match("deploy/compose/env.example")
    assert not pattern.match("deploy/compose/env.example.bak")
    assert not pattern.match("secrets/deploy/compose/env.example")


def test_gitleaks_toml_exempts_known_secrets_by_commit_only() -> None:
    """Case thường: bí mật giả trong test của B0-04/B0-06 miễn qua `commits` (SHA cố định), không qua `paths`.

    Miễn theo commit cụ thể (đã đóng băng, không đổi) không bao giờ áp dụng cho một commit MỚI
    thêm vào cùng file đó — khác miễn theo đường (áp dụng cho mọi commit, kể cả bí mật thật sau này).
    """
    with GITLEAKS_TOML.open("rb") as f:
        data = tomllib.load(f)
    allowlists = data.get("allowlist", [])
    if isinstance(allowlists, dict):
        allowlists = [allowlists]
    all_commits = {sha for a in allowlists for sha in a.get("commits", [])}
    assert all_commits == {
        "eb40a3c513d685ffd48807986badb2a3dbcc2584",
        "1b97b24564d433c356d8d6385ab11b4a90fa8a69",
    }
    for sha in all_commits:
        assert re.fullmatch(r"[0-9a-f]{40}", sha), sha
