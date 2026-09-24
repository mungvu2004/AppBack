"""Test tĩnh cho bốn Dockerfile của B0-08 (hợp đồng §1, prompt [6]/[8]).

Các file `deploy/docker/{api,worker,ml,web}.Dockerfile` thuộc worker P/W khác,
chưa hợp nhất vào nhánh này — mọi test ở đây `fail` với "thiếu <file>" tới khi đó,
đó là kết quả dự kiến (xem `changes/B0-08.md`).
"""

from __future__ import annotations

import re

import pytest

from deploy.tests.dockerfile_reader import (
    DockerInstruction,
    last_stage_instructions,
    parse_dockerfile,
)
from deploy.tests.support import require_path

IMAGES = ("api", "worker", "ml", "web")
# opencv-contrib-python cũng là bản GUI (K29, review 2026-09-22 #13) — bản cũ chỉ
# bắt "opencv-python" nên bỏ lọt "opencv-contrib-python" (không chứa chuỗi con
# "opencv-python" liên tục).
_UV_PYTHON_RE = re.compile(r"\buv:(?:\d+(?:\.\d+)*-)?python(\d+\.\d+)")
_PYTHON_BASE_RE = re.compile(r"(?:^|/)python:(\d+\.\d+)(?:\.\d+)?-")
_REQUIRES_PYTHON_RE = re.compile(r'^requires-python = ">=(\d+\.\d+)', re.MULTILINE)
_OPENCV_BAD = re.compile(r"opencv(?:-contrib)?-python(?!-headless)\b")
_USER_RE = re.compile(r"^10001(:\d+)?$")
_NODE_IMAGE_RE = re.compile(r"(?:^|/)node:")
_PNPM_NPM_PIN_RE = re.compile(r"npm\s+(?:install|i)\s+(?:-g|--global)\s+pnpm@\d+\.\d+\.\d+")
_TORCH_PIN_RE = re.compile(r'"torch==([0-9.]+)\+')
_TORCHVISION_PIN_RE = re.compile(r'"torchvision==([0-9.]+)\+')
_TORCH_LOCK_RE = re.compile(r'name = "torch"\nversion = "([0-9.]+)\+cpu"')
_TORCHVISION_LOCK_RE = re.compile(r'name = "torchvision"\nversion = "([0-9.]+)\+cpu"')


def _load(image: str) -> tuple[list, list[DockerInstruction]]:
    """Nạp và phân tích `deploy/docker/<image>.Dockerfile`; `fail` nếu chưa có file."""
    path = require_path(f"deploy/docker/{image}.Dockerfile")
    return parse_dockerfile(path)


def _copy_sources(instructions: list[DockerInstruction]) -> list[str]:
    """Trả danh sách nguồn (mọi token trừ cờ `--…` và token cuối cùng là đích) của
    mọi lệnh `COPY`/`ADD`."""
    sources: list[str] = []
    for instr in instructions:
        if instr.name not in ("COPY", "ADD"):
            continue
        tokens = [t for t in instr.args.split() if not t.startswith("--")]
        sources.extend(tokens[:-1])
    return sources


@pytest.mark.parametrize("image", IMAGES)
def test_dockerfile_final_stage_runs_as_10001(image: str) -> None:
    """Tầng cuối kết thúc bằng `USER 10001`/`10001:<gid>`, sau đó không đổi `USER` nữa."""
    stages, instructions = _load(image)
    last = last_stage_instructions(instructions, stages)
    user_instrs = [i for i in last if i.name == "USER"]
    assert user_instrs, f"{image}: tầng cuối thiếu USER"
    # USER cuối cùng là user hiệu lực khi container chạy — "sau đó không đổi USER"
    # nghĩa là chính lệnh USER cuối này phải là 10001, không có lệnh nào ghi đè nó.
    assert _USER_RE.match(user_instrs[-1].args), f"{image}: USER cuối phải là 10001 hoặc 10001:<gid>"


@pytest.mark.parametrize("image", IMAGES)
def test_dockerfile_no_latest_or_missing_tag(image: str) -> None:
    """`FROM` luôn có tag cụ thể (không `latest`, không thiếu tag), trừ khi tham chiếu
    lại một tầng trước đó bằng tên (`AS <tên>`)."""
    stages, _ = _load(image)
    known_stage_names = {s.name for s in stages if s.name}
    for stage in stages:
        base = stage.base
        if base in known_stage_names:
            continue
        assert ":" in base, f"{image}: FROM {base!r} thiếu tag"
        tag = base.rsplit(":", 1)[1].split("@")[0]
        assert tag != "latest", f"{image}: FROM {base!r} dùng tag latest"


@pytest.mark.parametrize("image", IMAGES)
def test_dockerfile_no_gui_opencv(image: str) -> None:
    """Không chuỗi `opencv-python` nào xuất hiện ngoài `opencv-python-headless` (K29).

    Lệnh `RUN` kiểm `importlib.metadata` của `ml` nêu đúng tên gói cấm để khẳng định
    nó **vắng mặt** — đó là bằng chứng tuân thủ, không phải một lượt cài đặt, nên loại
    khỏi quét theo cả **lệnh** (đã gộp dòng nối `\\`), không theo từng dòng thô — lệnh
    thường viết `python -c "..."` nhiều dòng, `importlib.metadata` và `opencv-python`
    có thể ở hai dòng khác nhau trong cùng một lệnh (xem
    `test_dockerfile_ml_has_pinned_fetch_and_export_and_arg_variant`)."""
    _, instructions = _load(image)
    for instr in instructions:
        if "importlib.metadata" in instr.args:
            continue
        assert not _OPENCV_BAD.search(instr.args), f"{image}: có opencv-python không phải bản headless ({instr.args!r})"


@pytest.mark.parametrize("image", IMAGES)
def test_dockerfile_build_stage_packages_testing_only_pyproject(image: str) -> None:
    """Tầng dựng (không phải tầng cuối) được `COPY packages/testing/pyproject.toml …`
    — chỉ tệp đó — để `uv sync --locked` thấy đủ workspace mà không đem mã kiểm thử
    vào build context (`.dockerignore` chừa đúng ngoại lệ này)."""
    stages, instructions = _load(image)
    last_index = stages[-1].index if stages else -1
    build_instructions = [i for i in instructions if i.stage != last_index]
    for source in _copy_sources(build_instructions):
        if "packages/testing" not in source:
            continue
        assert source.endswith("pyproject.toml"), (
            f"{image}: tầng dựng COPY/ADD nguồn {source!r} thuộc packages/testing vượt quá pyproject.toml"
        )


@pytest.mark.parametrize("image", IMAGES)
def test_dockerfile_final_stage_no_packages_testing_at_all(image: str) -> None:
    """Tầng cuối (ảnh chạy thật) không có `COPY`/`ADD` nào có nguồn thuộc
    `packages/testing` — kể cả `pyproject.toml` — vì `/app/packages/testing` không
    được tồn tại trong ảnh chạy (hợp đồng B0-08 §1)."""
    stages, instructions = _load(image)
    last = last_stage_instructions(instructions, stages)
    for source in _copy_sources(last):
        assert "packages/testing" not in source, f"{image}: tầng cuối vẫn chép {source!r} thuộc packages/testing"


@pytest.mark.parametrize("image", ["api", "worker", "ml"])
def test_dockerfile_final_stage_no_bulk_packages_copy(image: str) -> None:
    """Tầng cuối không `COPY --from=<tầng dựng> …/packages /app/packages` nguyên khối
    (mới chỉ chép từng gói một tránh mang cả thư mục `packages/testing` rỗng theo) —
    hợp đồng B0-08 §1 ("bản CHỐT 1")."""
    stages, instructions = _load(image)
    last = last_stage_instructions(instructions, stages)
    for source in _copy_sources(last):
        assert source.rstrip("/").rsplit("/", 1)[-1] != "packages", (
            f"{image}: tầng cuối chép nguyên khối {source!r} thay vì từng gói con"
        )


@pytest.mark.parametrize("image", ["api", "worker", "ml"])
def test_dockerfile_python_image_no_copy_dot(image: str) -> None:
    """Ảnh Python không `COPY . …` (chỉ chép venv + mã cần thiết, không cả cây)."""
    _, instructions = _load(image)
    for source in _copy_sources(instructions):
        assert source not in (".", "./"), f"{image}: COPY nguồn là toàn bộ context ({source!r})"


def test_dockerfile_api_only_copies_pyproject_from_ml_and_worker() -> None:
    """`api`: nguồn `COPY` thuộc `apps/ml`/`apps/worker` chỉ được là `…/pyproject.toml`,
    và không xuất hiện ở tầng cuối (chỉ cần cho `uv sync --locked` thấy workspace)."""
    stages, instructions = _load("api")
    for source in _copy_sources(instructions):
        if "apps/ml" in source or "apps/worker" in source:
            assert source.endswith("pyproject.toml"), f"api: COPY {source!r} vượt quá pyproject.toml"
    last = last_stage_instructions(instructions, stages)
    for source in _copy_sources(last):
        assert "apps/ml" not in source, f"api: tầng cuối vẫn còn nguồn {source!r} của apps/ml"
        assert "apps/worker" not in source, f"api: tầng cuối vẫn còn nguồn {source!r} của apps/worker"


def test_dockerfile_worker_copies_apps_api() -> None:
    """`worker` chép `apps/api` (lịch `apps/api/*/jobs.py`, import-linter không cho
    `apps.worker` nhập `fastapi` — hợp đồng B0-08 §1)."""
    _, instructions = _load("worker")
    sources = _copy_sources(instructions)
    assert any("apps/api" in s for s in sources), "worker: thiếu COPY apps/api"


def test_dockerfile_ml_has_pinned_fetch_and_export_and_arg_variant() -> None:
    """`ml`: có `RUN` chạy `pinned fetch --dest /opt/models` và `export_pinned --dest
    /opt/models`, có `ARG ML_VARIANT=cpu`, có kiểm `importlib.metadata` không có
    `opencv-python` trong venv chạy (uv không cài `pip`)."""
    _, instructions = _load("ml")
    run_text = " ".join(i.args for i in instructions if i.name == "RUN")
    assert "packages.ml_contracts.pinned fetch --dest /opt/models" in run_text, "ml: thiếu pinned fetch"
    assert "apps.ml.runtime.export_pinned --dest /opt/models" in run_text, "ml: thiếu export_pinned"
    arg_text = [i.args for i in instructions if i.name == "ARG"]
    assert "ML_VARIANT=cpu" in arg_text, "ml: thiếu ARG ML_VARIANT=cpu"
    assert "importlib.metadata" in run_text, "ml: thiếu kiểm importlib.metadata"
    assert "opencv-python" in run_text, "ml: kiểm importlib.metadata thiếu tên gói opencv-python"
    assert "opencv-contrib-python" in run_text, (
        "ml: kiểm importlib.metadata thiếu tên gói opencv-contrib-python (K29, review 2026-09-22 #13)"
    )


def test_dockerfile_ml_cuda_torch_versions_match_uv_lock() -> None:
    """Phiên bản `torch`/`torchvision` ghim cho biến thể CUDA của `ml.Dockerfile`
    phải bằng `version` của `uv.lock` (bỏ hậu tố `+cpu`) — lock nâng torch mà ảnh
    `cuda` không đổi theo thì lặng lẽ cài bản cũ (`--no-deps`), lệch ABI với
    `torchvision`/`ultralytics` (review 2026-09-22 #7)."""
    _, instructions = _load("ml")
    run_text = " ".join(i.args for i in instructions if i.name == "RUN")
    torch_pin = _TORCH_PIN_RE.search(run_text)
    torchvision_pin = _TORCHVISION_PIN_RE.search(run_text)
    assert torch_pin, "ml.Dockerfile: không thấy torch==<version>+ trong RUN"
    assert torchvision_pin, "ml.Dockerfile: không thấy torchvision==<version>+ trong RUN"

    lock_text = require_path("uv.lock").read_text(encoding="utf-8")
    torch_lock = _TORCH_LOCK_RE.search(lock_text)
    torchvision_lock = _TORCHVISION_LOCK_RE.search(lock_text)
    assert torch_lock, "uv.lock: không thấy version của gói torch"
    assert torchvision_lock, "uv.lock: không thấy version của gói torchvision"

    assert torch_pin.group(1) == torch_lock.group(1), (
        f"ml.Dockerfile ghim torch=={torch_pin.group(1)}, uv.lock khoá {torch_lock.group(1)}+cpu"
    )
    assert torchvision_pin.group(1) == torchvision_lock.group(1), (
        f"ml.Dockerfile ghim torchvision=={torchvision_pin.group(1)}, uv.lock khoá {torchvision_lock.group(1)}+cpu"
    )


def test_dockerfile_web_installs_pnpm_without_corepack() -> None:
    """Tầng build của `web` cài pnpm bằng `npm install -g pnpm@<bản ghim đầy đủ>`, không corepack.

    Ảnh node của Docker Hub không còn kèm corepack (đo thật trên bản đang ghim,
    `node:26-bookworm-slim` = node v26.9.0, npm 11.19.1: `/usr/local/bin` chỉ có
    `node`, `npm`, `npx`). `RUN corepack enable` vì thế thoát 127 và ảnh `web`
    không build được — CI job `build` đỏ (NO-174, FIX-100; dependabot `3c266b8`
    nâng dòng node mà không đụng lệnh cài pnpm). npm luôn có sẵn trong mọi ảnh
    node, nên không có lý do quay lại corepack: test cấm hẳn chuỗi đó.
    Bản pnpm phải ghim đủ ba số — `pnpm@9` để npm tự chọn bản vá mới nhất thì
    `pnpm install --frozen-lockfile` mất tính lặp lại giữa hai lần build.
    """
    stages, instructions = _load("web")
    node_stages = [s.index for s in stages if _NODE_IMAGE_RE.search(s.base)]
    assert node_stages, "web: không thấy tầng nào FROM node:<bản>"
    for index in node_stages:
        run_text = " ".join(i.args for i in instructions if i.name == "RUN" and i.stage == index)
        assert "corepack" not in run_text, (
            f"web: tầng node #{index} còn dùng corepack — ảnh node đang ghim không có lệnh này "
            "(thoát 127); cài bằng `npm install -g pnpm@<bản>`"
        )
        assert _PNPM_NPM_PIN_RE.search(run_text), (
            f"web: tầng node #{index} thiếu `npm install -g pnpm@<x.y.z>` với bản ghim đủ ba số"
        )


def _root_requires_python_minor() -> str:
    """Minor Python mà cả workspace ghim, đọc từ `requires-python` của `pyproject.toml` gốc."""
    source = require_path("pyproject.toml").read_text(encoding="utf-8")
    m = _REQUIRES_PYTHON_RE.search(source)
    assert m, "pyproject.toml gốc: không đọc được requires-python"
    return m.group(1)


def test_dockerfile_python_minor_matches_across_stages_and_workspace() -> None:
    """Mọi tầng Python trong `deploy/docker/**` phải cùng một minor với `requires-python`.

    Tầng dựng (`ghcr.io/astral-sh/uv:[<bản uv>-]pythonX.Y-…`) tạo venv ở
    `/opt/venv/lib/pythonX.Y/site-packages` với C extension `cpython-XY-…so`; tầng
    chạy (`python:A.B-slim-…`) chỉ tìm ở `pythonA.B`. Lệch một minor là **mọi** gói
    biến mất, dù `docker build` vẫn thoát 0: dependabot `44b299f` nâng riêng tầng
    chạy 3.12 → 3.14 và `compose run migrate` chết với `ModuleNotFoundError: No
    module named 'alembic'` trong khi `/opt/venv/bin/alembic` vẫn nằm đó (NO-177,
    FIX-104). Không cổng nào bắt được vì bản thân lệnh build vẫn đạt.

    `uv.lock` khoá theo đúng minor này (`requires-python = "==3.12.*"`), nên nâng
    minor là việc có chủ đích kèm relock — không phải một bản vá gom nhóm.
    Quét theo thư mục chứ không theo danh sách ảnh: Dockerfile mới cũng chịu luật.
    """
    expected = _root_requires_python_minor()
    docker_dir = require_path("deploy/docker")
    dockerfiles = sorted(docker_dir.glob("*.Dockerfile"))
    assert dockerfiles, "deploy/docker: không có Dockerfile nào"

    checked = 0
    for path in dockerfiles:
        stages, _ = parse_dockerfile(path)
        for stage in stages:
            for label, regex in (("tầng dựng uv", _UV_PYTHON_RE), ("tầng chạy python", _PYTHON_BASE_RE)):
                m = regex.search(stage.base)
                if not m:
                    continue
                checked += 1
                assert m.group(1) == expected, (
                    f"{path.name} tầng #{stage.index} ({label}) dùng Python {m.group(1)}, "
                    f"lệch requires-python {expected} của pyproject.toml gốc — venv sẽ không đọc được"
                )
    # 7 = api/worker/ml (uv + python mỗi ảnh) + tầng uv của verify.Dockerfile (tag có bản uv).
    assert checked >= 7, f"chỉ soi được {checked} tầng Python, quá ít — regex có thể đã hỏng"


def test_dockerfile_web_has_draco_build_and_wasm_check() -> None:
    """`web`: tầng build chạy `pnpm draco` và kiểm `test -f dist/draco/draco_decoder.wasm`."""
    _, instructions = _load("web")
    run_text = " ".join(i.args for i in instructions if i.name == "RUN")
    assert "pnpm draco" in run_text, "web: thiếu pnpm draco"
    assert "test -f dist/draco/draco_decoder.wasm" in run_text, "web: thiếu kiểm draco_decoder.wasm"


def test_dockerfile_web_removes_base_image_default_server() -> None:
    """Tầng cuối `web` xoá `/etc/nginx/conf.d/default.conf` của ảnh nền — nó giữ
    `server_name localhost`, khớp `Host: localhost[:cổng]` TRƯỚC `app.conf`, nuốt
    `/api/*` (404 HTML) và mất CSP của SPA (review 2026-09-22 #1, probe Q1;
    `localhost` là URL `PUBLIC_BASE_URL`/e2e dùng). `rm` và đường `default.conf`
    phải cùng một lệnh `RUN` (không chỉ cùng xuất hiện đâu đó trong tầng — review
    2026-09-22 #19: assert cũ nối hết `RUN` của tầng thành một chuỗi rồi tìm
    chuỗi con "rm", khớp cả một `RUN` khác chỉ tình cờ chứa "rm" trong một từ)."""
    stages, instructions = _load("web")
    last = last_stage_instructions(instructions, stages)
    run_commands = [i.args for i in last if i.name == "RUN"]
    matches = [cmd for cmd in run_commands if "/etc/nginx/conf.d/default.conf" in cmd and re.search(r"\brm\b", cmd)]
    assert matches, "web: tầng cuối thiếu một RUN duy nhất vừa rm vừa nêu default.conf của ảnh nền"


def test_dockerfile_web_healthcheck_has_start_interval() -> None:
    """`HEALTHCHECK` của `web` khai `--start-interval=2s` (Docker 29.6, `docs/charter/ENV.md`
    §… đã đo nhận cờ này): `base.yml` bỏ healthcheck riêng của dev/ci (review
    2026-09-22 #3) nên `docker compose up --wait`/e2e F-14 giờ chờ đúng chu kỳ khởi
    động 2 s của ảnh thay vì 30 s mặc định của `--interval` (review 2026-09-22
    #20) — vẫn một nguồn healthcheck duy nhất (không thêm HEALTHCHECK thứ hai)."""
    _, instructions = _load("web")
    healthchecks = [i.args for i in instructions if i.name == "HEALTHCHECK"]
    assert len(healthchecks) == 1, "web: phải có đúng một HEALTHCHECK (một nguồn)"
    assert "--start-interval=2s" in healthchecks[0], "web: HEALTHCHECK thiếu --start-interval=2s"


def test_dockerfile_web_has_appfront_revision_label() -> None:
    """`web` gắn `LABEL org.opencontainers.image.revision.appfront=<sha>`."""
    _, instructions = _load("web")
    labels = [i.args for i in instructions if i.name == "LABEL"]
    assert any("org.opencontainers.image.revision.appfront" in label for label in labels), (
        "web: thiếu LABEL org.opencontainers.image.revision.appfront"
    )


_REQUIRED_IGNORE_ENTRIES = (
    ".git",
    ".venv",
    ".cache",
    "contract-samples",
    "**/tests",
    "**/__pycache__",
    "node_modules",
    "packages/testing",
)


def test_dockerignore_has_required_entries_and_narrow_testing_exception() -> None:
    """`.dockerignore` liệt kê đủ các mục bắt buộc; ngoại lệ `!packages/testing/…`
    (nếu có) chỉ được cho phép lại `pyproject.toml`."""
    path = require_path(".dockerignore")
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for entry in _REQUIRED_IGNORE_ENTRIES:
        assert entry in lines, f".dockerignore: thiếu {entry}"
    for line in lines:
        if line.startswith("!") and "packages/testing" in line:
            assert line.endswith("pyproject.toml"), (
                f".dockerignore: ngoại lệ {line!r} cho packages/testing vượt quá pyproject.toml"
            )
