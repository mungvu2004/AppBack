"""Job `commits` (B0-09): kiểm tiêu đề PR, dòng đầu mỗi commit, tên nhánh và trailer `Prompt:`.

Đầu vào chỉ qua biến môi trường (BE-00 §13.2, prompt B0-09 [6]): `EVENT`
(`pull_request`|`push`), `PR_TITLE`, `HEAD_REF`, `BASE_SHA`, `HEAD_SHA`. Gọi lại
đúng `.githooks/commit-msg` của checkout chứa mã này (không viết regex dòng
đầu thứ hai) nên luật Conventional Commits chỉ sống ở một nơi. Fail-closed:
biến thiếu, `EVENT` lạ, SHA không phải hex 40 → thoát 1 trước khi chạm git.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_ZERO_SHA = "0" * 40
_BRANCH_RE = re.compile(r"^(feature|fix|chore|docs|refactor|test)/[a-z0-9][a-z0-9._-]*$")
_PROMPT_CODE_RE = re.compile(r"^[a-z][0-9]+-[0-9]+[a-z]?")
_FIELD_SEP = "\x1f"
_GIT_TIMEOUT = 30
_HOOK_TIMEOUT = 10


class GitCommandError(RuntimeError):
    """Lệnh git thất bại (SHA không tồn tại, không phải repo…); giữ nguyên stderr để không nuốt lỗi (R-16)."""


@dataclass(frozen=True)
class Inputs:
    """Biến môi trường đã xác thực cho một lượt kiểm; bất biến của job `commits`."""

    event: str
    pr_title: str
    head_ref: str
    base_sha: str
    head_sha: str


def hook_path() -> Path:
    """Trả đường `.githooks/commit-msg` của chính checkout chứa module này (không phải repo đang kiểm)."""
    return Path(__file__).resolve().parents[2] / ".githooks" / "commit-msg"


def load_inputs(env: Mapping[str, str]) -> Inputs:
    """Đọc và xác thực biến môi trường theo sự kiện; thiếu/lạ/sai dạng → `ValueError` (fail-closed, R-17).

    `workflow_dispatch` (lượt chạy tay, `ci.yml` khai trigger) đi cùng nhánh với `push`: `main()` chỉ
    tách riêng `pull_request`, còn lại (`push`, `workflow_dispatch`) đều chỉ kiểm dòng đầu các commit
    trong khoảng — /merge-review lượt 1 #2, trước đó `workflow_dispatch` bị từ chối thẳng ở đây làm
    mọi lượt chạy tay đỏ oan.
    """
    event = env.get("EVENT", "")
    if event not in ("pull_request", "push", "workflow_dispatch"):
        raise ValueError(f"EVENT không hợp lệ: {event!r} (cần 'pull_request', 'push' hoặc 'workflow_dispatch')")

    base_sha = env.get("BASE_SHA", "")
    head_sha = env.get("HEAD_SHA", "")
    if event != "pull_request" and not base_sha:
        # workflow_dispatch (và push của nhánh mới) không luôn có BASE_SHA thật
        # (github.event.before không tồn tại cho workflow_dispatch) — coi rỗng
        # như "không có base", chỉ kiểm HEAD_SHA, giống push với BASE_SHA toàn
        # 0 đã có sẵn (commit_headers). PR luôn có base thật nên không nới ở đây.
        base_sha = _ZERO_SHA
    if not _SHA_RE.match(head_sha):
        raise ValueError(f"HEAD_SHA phải là hex 40 ký tự: {head_sha!r}")
    if not _SHA_RE.match(base_sha):
        raise ValueError(f"BASE_SHA phải là hex 40 ký tự: {base_sha!r}")

    pr_title = env.get("PR_TITLE", "")
    head_ref = env.get("HEAD_REF", "")
    if event == "pull_request":
        if not pr_title.strip():
            raise ValueError("thiếu PR_TITLE cho sự kiện pull_request")
        if not head_ref.strip():
            raise ValueError("thiếu HEAD_REF cho sự kiện pull_request")
    return Inputs(event=event, pr_title=pr_title, head_ref=head_ref, base_sha=base_sha, head_sha=head_sha)


def _run_git(args: list[str]) -> str:
    """Gọi `git` ở cwd hiện tại với timeout tường minh (R-24); lỗi git nổi lên nguyên văn (R-16)."""
    result = subprocess.run(  # noqa: S603 — "git" cố định, đối số do module này dựng, không nhận shell người dùng
        ["git", *args],  # noqa: S607 — thực thi "git" qua PATH, không phải input người dùng
        capture_output=True,
        text=True,
        timeout=_GIT_TIMEOUT,
        check=False,
    )
    if result.returncode != 0:
        raise GitCommandError(f"git {' '.join(args)} lỗi:\n{result.stderr}")
    return result.stdout


def check_header_line(hook: Path, header: str) -> bool:
    """Ghi `header` ra file tạm rồi gọi lại `.githooks/commit-msg`; True khi hook thoát 0."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        msg_file = Path(tmp_dir) / "COMMIT_MSG"
        msg_file.write_text(header + "\n", encoding="utf-8")
        result = subprocess.run(  # noqa: S603 — "bash" cố định, hook và file tạm đều do module này tạo
            ["bash", str(hook), str(msg_file)],  # noqa: S607 — thực thi "bash" qua PATH, không phải input người dùng
            capture_output=True,
            text=True,
            timeout=_HOOK_TIMEOUT,
            check=False,
        )
    return result.returncode == 0


def commit_headers(base_sha: str, head_sha: str) -> list[tuple[str, str]]:
    """Liệt kê `(sha, dòng đầu)` trong `base_sha..head_sha`, bỏ commit merge; `base_sha` toàn 0 → chỉ `head_sha`."""
    fmt = f"--format=%H{_FIELD_SEP}%s"
    if base_sha == _ZERO_SHA:
        out = _run_git(["log", "--no-merges", "-n", "1", fmt, head_sha])
    else:
        out = _run_git(["log", "--no-merges", fmt, f"{base_sha}..{head_sha}"])
    commits = []
    for line in out.splitlines():
        if not line:
            continue
        sha, _, subject = line.partition(_FIELD_SEP)
        commits.append((sha, subject))
    return commits


def check_branch_name(head_ref: str) -> str | None:
    """Kiểm mẫu tên nhánh `<loại>/<mô tả>`; `dependabot/**` được miễn hoàn toàn (kể cả trailer)."""
    if head_ref.startswith("dependabot/"):
        return None
    if not _BRANCH_RE.match(head_ref):
        return f"tên nhánh không hợp lệ: {head_ref}"
    return None


def prompt_code_from_branch(head_ref: str) -> str | None:
    """Trích mã prompt (`b0-02`…) ở đầu phần sau `/`; nhánh không mang mã hoặc `dependabot/**` → None."""
    if head_ref.startswith("dependabot/") or "/" not in head_ref:
        return None
    _, _, rest = head_ref.partition("/")
    match = _PROMPT_CODE_RE.match(rest)
    return match.group(0).upper() if match else None


def _commit_shas_in_range(base_sha: str, head_sha: str) -> list[str]:
    """Liệt kê SHA đầy đủ trong khoảng, kể cả merge — trailer đọc trên toàn bộ lịch sử nhánh."""
    out = _run_git(["log", "--format=%H", f"{base_sha}..{head_sha}"])
    return [line for line in out.splitlines() if line]


def _prompt_trailer(sha: str) -> str:
    """Trả giá trị trailer `Prompt:` của một commit, chuỗi rỗng nếu không có."""
    return _run_git(["log", "-1", "--format=%(trailers:key=Prompt,valueonly)", sha]).strip()


def check_trailers(base_sha: str, head_sha: str, prompt_code: str | None) -> list[str]:
    """Đòi ≥1 commit trong khoảng mang `Prompt: <prompt_code>`; mọi trailer khác mã đều là lỗi riêng."""
    if prompt_code is None:
        return []
    failures = []
    matched = False
    for sha in _commit_shas_in_range(base_sha, head_sha):
        value = _prompt_trailer(sha)
        if not value:
            continue
        if value.upper() == prompt_code:
            matched = True
        else:
            failures.append(f"{sha[:12]} Prompt: {value} lệch mã nhánh {prompt_code}")
    if not matched:
        failures.append(f"nhánh mang mã {prompt_code} nhưng không commit nào có trailer Prompt: {prompt_code}")
    return failures


def _check_commit_headers(hook: Path, base_sha: str, head_sha: str) -> list[str]:
    """Kiểm dòng đầu của mọi commit không-merge trong khoảng; trả các dòng hỏng đã định dạng."""
    failures = []
    for sha, subject in commit_headers(base_sha, head_sha):
        if not check_header_line(hook, subject):
            failures.append(f"{sha[:12]} {subject}")
    return failures


def _check_pull_request(inputs: Inputs, hook: Path) -> list[str]:
    """Toàn bộ luật riêng của `pull_request`: tiêu đề PR, dòng đầu commit, tên nhánh, trailer.

    `dependabot/**` bỏ kiểm dòng đầu **từng commit**: Dependabot nối thêm " in <thư mục>" vào tiêu
    đề khi hệ khác `/` (hệ `docker` ở `dependabot.yml` là `/deploy/docker`), làm dòng đầu commit dễ
    vượt 72 ký tự dù không sai gì — squash sau này lấy tiêu đề PR (vẫn kiểm ở dòng trên), không lấy
    từng dòng đầu commit riêng lẻ, nên kiểm chúng ở đây là kiểm nhầm thứ không lên `main`
    (/merge-review lượt 1 #4).
    """
    failures = []
    if not check_header_line(hook, inputs.pr_title):
        failures.append(f"tiêu đề PR: {inputs.pr_title}")
    if not inputs.head_ref.startswith("dependabot/"):
        failures.extend(_check_commit_headers(hook, inputs.base_sha, inputs.head_sha))
    branch_failure = check_branch_name(inputs.head_ref)
    if branch_failure:
        failures.append(branch_failure)
    prompt_code = prompt_code_from_branch(inputs.head_ref)
    failures.extend(check_trailers(inputs.base_sha, inputs.head_sha, prompt_code))
    return failures


def main(argv: list[str] | None = None) -> int:
    """Điểm vào job `commits`; đọc `os.environ`, in mọi dòng hỏng ra stderr, thoát 1 nếu có lỗi."""
    del argv  # đầu vào chỉ qua biến môi trường (giao diện cố định của hợp đồng B0-09)
    try:
        inputs = load_inputs(os.environ)
    except ValueError as exc:
        sys.stderr.write(f"commits: {exc}\n")
        return 1

    hook = hook_path()
    try:
        if inputs.event == "pull_request":
            failures = _check_pull_request(inputs, hook)
        else:
            failures = _check_commit_headers(hook, inputs.base_sha, inputs.head_sha)
    except GitCommandError as exc:
        sys.stderr.write(f"commits: {exc}\n")
        return 1

    for line in failures:
        sys.stderr.write(line + "\n")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
