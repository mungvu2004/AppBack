"""Quét tĩnh `notify.yml` và chạy thật thân của nó (B0-10 [8] "Quét notify.yml",
"Thân tin cảnh báo").

Hai đoạn `run:` được trích thẳng từ YAML rồi chạy bằng `bash` thật: điều kiện gửi
(bảng B0-10 [6]) và bước gửi JSON qua `HttpStub` — không chép lại logic vào test.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from deploy.scripts.tests.support import REPO_ROOT, HttpStub, Reply, run_script

CI_YML = REPO_ROOT / ".github" / "workflows" / "ci.yml"
DEPLOY_YML = REPO_ROOT / ".github" / "workflows" / "deploy.yml"
RESTORE_DRILL_YML = REPO_ROOT / ".github" / "workflows" / "restore-drill.yml"
NOTIFY_YML = REPO_ROOT / ".github" / "workflows" / "notify.yml"


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


def _workflow_names(*paths: Path) -> set[str]:
    """`name:` thật của các workflow — nguồn duy nhất cho `workflow_run.workflows` (không chép tay)."""
    return {_load_yaml(p)["name"] for p in paths}


def test_notify_watches_exact_names_of_ci_deploy_restore_drill() -> None:
    doc = _load_yaml(NOTIFY_YML)
    watched = set(_triggers(doc)["workflow_run"]["workflows"])
    assert watched == _workflow_names(CI_YML, DEPLOY_YML, RESTORE_DRILL_YML)


def test_notify_permissions_empty_and_no_checkout() -> None:
    doc = _load_yaml(NOTIFY_YML)
    assert doc.get("permissions") == {}
    uses_values = _walk_key(doc["jobs"], "uses")
    assert not any(u.startswith("actions/checkout@") for u in uses_values)


def test_notify_run_steps_never_interpolate_event_directly() -> None:
    """Mọi giá trị `github.event.workflow_run.*` phải đi qua `env:`, không nội suy thẳng vào `run:`
    (lượt được báo có thể tới từ PR fork, mang secret của job notify)."""
    doc = _load_yaml(NOTIFY_YML)
    for run_body in _walk_key(doc["jobs"], "run"):
        assert "${{ github.event." not in run_body, run_body


# ---------------------------------------------------------------------------
# Điều kiện gửi — chạy thật đoạn bash quyết định, không chép bảng case vào Python
# ---------------------------------------------------------------------------


def _decision_script() -> str:
    """Thân `run:` của bước quyết định gửi (chứa `case "$WORKFLOW_NAME"`), trích từ YAML thật."""
    doc = _load_yaml(NOTIFY_YML)
    for step in doc["jobs"]["notify"]["steps"]:
        run_body = step.get("run", "")
        if 'case "$WORKFLOW_NAME"' in run_body:
            return run_body
    raise AssertionError("không tìm thấy bước quyết định gửi (case $WORKFLOW_NAME)")


def _run_decision(tmp_path: Path, *, workflow: str, conclusion: str, head_branch: str) -> bool:
    """Chạy thật đoạn quyết định với biến `env:` như GitHub đặt; trả `True` nếu bước đặt `SEND_ALERT=1`
    vào `$GITHUB_ENV` (đúng cơ chế GitHub Actions dùng để truyền biến sang bước sau)."""
    github_env = tmp_path / "github_env"
    github_env.write_text("", encoding="utf-8")
    script = tmp_path / "decision.sh"
    script.write_text("set -euo pipefail\n" + _decision_script(), encoding="utf-8")
    result = run_script(
        script,
        env={
            "WORKFLOW_NAME": workflow,
            "CONCLUSION": conclusion,
            "HEAD_BRANCH": head_branch,
            "GITHUB_ENV": str(github_env),
        },
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return "SEND_ALERT=1" in github_env.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("workflow", "conclusion", "head_branch", "expected_send"),
    [
        ("CI", "failure", "main", True),
        ("CI", "failure", "feature/x", False),
        ("CI", "success", "main", False),
        ("Deploy", "success", "main", True),
        ("Deploy", "failure", "main", True),
        ("Deploy", "cancelled", "main", False),
        ("Restore drill", "failure", "main", True),
        ("Restore drill", "success", "main", False),
    ],
)
def test_notify_send_decision_matches_prompt_table(
    tmp_path: Path, workflow: str, conclusion: str, head_branch: str, expected_send: bool
) -> None:
    assert _run_decision(tmp_path, workflow=workflow, conclusion=conclusion, head_branch=head_branch) is expected_send


# ---------------------------------------------------------------------------
# Bước gửi — HttpStub thật, thiếu webhook, máy chủ 500
# ---------------------------------------------------------------------------

_SHA = "0123456789abdeadbeef"


def _send_script() -> str:
    """Thân `run:` của bước gửi (POST `ALERT_WEBHOOK_URL`), trích từ YAML thật."""
    doc = _load_yaml(NOTIFY_YML)
    for step in doc["jobs"]["notify"]["steps"]:
        run_body = step.get("run", "")
        if "ALERT_WEBHOOK_URL" in run_body and "curl" in run_body:
            return run_body
    raise AssertionError("không tìm thấy bước gửi (curl ALERT_WEBHOOK_URL)")


def _run_send(tmp_path: Path, *, webhook_url: str) -> Any:
    script = tmp_path / "send.sh"
    script.write_text("set -euo pipefail\n" + _send_script(), encoding="utf-8")
    return run_script(
        script,
        env={
            "WORKFLOW_NAME": "Deploy",
            "CONCLUSION": "failure",
            "HEAD_BRANCH": "main",
            "HEAD_SHA": _SHA,
            "HTML_URL": "https://github.com/mungvu2004/AppBack/actions/runs/1",
            "ALERT_WEBHOOK_URL": webhook_url,
        },
        timeout=30,
    )


def test_notify_send_posts_json_with_matching_text_and_content(tmp_path: Path) -> None:
    with HttpStub() as stub:
        result = _run_send(tmp_path, webhook_url=stub.url)
        assert result.returncode == 0, result.stdout + result.stderr
        assert len(stub.posts) == 1
        _path, body = stub.posts[0]
        payload = json.loads(body)
    assert payload["text"] == payload["content"]
    message = payload["text"]
    assert "\n" not in message
    assert "Deploy" in message
    assert _SHA[:12] in message
    assert "https://github.com/mungvu2004/AppBack/actions/runs/1" in message


def test_notify_send_missing_webhook_url_skips_without_posting(tmp_path: Path) -> None:
    result = _run_send(tmp_path, webhook_url="")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "::notice::" in result.stdout


def test_notify_send_server_error_warns_but_exits_zero(tmp_path: Path) -> None:
    with HttpStub(post_reply=Reply(status=500)) as stub:
        result = _run_send(tmp_path, webhook_url=stub.url)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "::warning::" in result.stdout
