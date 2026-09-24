"""Test `deploy/scripts/deploy.sh` — thứ tự đổi container, hỏng migrate/smoke/timeout."""

from __future__ import annotations

import re
import time
from pathlib import Path

from deploy.scripts.tests.support import REPO_ROOT, HttpStub, Reply, fake_bin, read_log, run_script

SCRIPT = REPO_ROOT / "deploy" / "scripts" / "deploy.sh"

SMOKE_ROUTES = {
    "/api/health": Reply(200),
    "/api/ready": Reply(200),
    "/": Reply(200, headers={"Content-Security-Policy": "default-src 'self'"}),
    "/draco/draco_decoder.wasm": Reply(200, body=b"wasm"),
    "/api/nope": Reply(404, body=b'{"code":"NOT_FOUND"}'),
}

# `docker` giả: theo dõi tập container `api` bằng file trạng thái $DOCKER_STATE.
# Chỉ để kiểm thứ tự lệnh (B0-10 [8]) — không thay Docker thật.
_DOCKER_BODY = """
state="$DOCKER_STATE"
mkdir -p "$state"
ids_file="$state/ids"
touch "$ids_file"

if [[ "$1 $2" == "compose pull" ]]; then
  exit 0
fi
if [[ "$1 $2 $3 $4" == "compose run --rm migrate" ]]; then
  exit "${DOCKER_MIGRATE_EXIT:-0}"
fi
if [[ "$1 $2 $3 $4" == "compose ps -q api" ]]; then
  cat "$ids_file"
  exit 0
fi
if [[ "$1 $2" == "compose up" ]]; then
  scale2=0
  next_is_scale=0
  for a in "$@"; do
    if [[ "$next_is_scale" == "1" ]]; then
      [[ "$a" == "api=2" ]] && scale2=1
      next_is_scale=0
    fi
    [[ "$a" == "--scale" ]] && next_is_scale=1
  done
  if [[ "$scale2" == "1" && "${DOCKER_SCALE2_NO_NEW:-0}" == "1" ]]; then
    exit 0
  fi
  if [[ "$scale2" == "1" ]]; then
    n=0
    [[ -f "$state/counter" ]] && n="$(cat "$state/counter")"
    n=$((n + 1))
    echo "$n" > "$state/counter"
    id="c$n"
    echo "$id" >> "$ids_file"
    if [[ "${DOCKER_UNHEALTHY:-0}" == "1" ]]; then
      echo "starting" > "$state/health_$id"
    else
      echo "healthy" > "$state/health_$id"
    fi
  fi
  exit 0
fi
if [[ "$1" == "inspect" ]]; then
  id="${*: -1}"
  cat "$state/health_$id" 2>/dev/null || echo "starting"
  exit 0
fi
if [[ "$1" == "stop" ]]; then
  exit 0
fi
if [[ "$1" == "rm" ]]; then
  id="${*: -1}"
  grep -vxF "$id" "$ids_file" > "$ids_file.tmp" 2>/dev/null || true
  mv "$ids_file.tmp" "$ids_file" 2>/dev/null || true
  rm -f "$state/health_$id"
  exit 0
fi
exit 0
"""


def _fake_docker(tmp_path: Path) -> tuple[Path, Path]:
    """Đặt `docker` giả đầu PATH; trả (bin_dir, docker_state_dir)."""
    bin_dir = fake_bin(tmp_path / "bin", {"docker": _DOCKER_BODY})
    state = tmp_path / "docker-state"
    state.mkdir()
    return bin_dir, state


def test_deploy_dry_run_prints_order_without_docker(tmp_path: Path) -> None:
    """--dry-run in đúng thứ tự pull → migrate → scale api=2 → healthy → chờ settle DNS →
    xoá cũ → smoke, không gọi docker, không ghi current_tag. Review round 2 N6: bước chờ
    nginx tự dịch lại DNS (thêm ở lib.sh cho NO-116) trước đây bị thiếu khỏi kế hoạch in ra."""
    appback_dir = tmp_path / "opt-appback"
    appback_dir.mkdir()
    env = {"APPBACK_DIR": str(appback_dir)}
    result = run_script(SCRIPT, ["sha-abc123456789", "--dry-run"], env=env)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    order = ["pull", "migrate", "scale api=2", "healthy", "dịch lại DNS", "xoá", "smoke"]
    positions = [out.find(word) for word in order]
    assert all(p != -1 for p in positions), out
    assert positions == sorted(positions)
    assert not (appback_dir / "current_tag").exists()
    assert not (appback_dir / "previous_tag").exists()


def test_deploy_dry_run_invalid_tag_exits_2(tmp_path: Path) -> None:
    """Tag sai mẫu → thoát 2, kể cả với --dry-run."""
    env = {"APPBACK_DIR": str(tmp_path)}
    result = run_script(SCRIPT, ["BAD TAG!", "--dry-run"], env=env)
    assert result.returncode == 2


def test_deploy_success_runs_in_order_and_writes_tags(tmp_path: Path) -> None:
    """Chạy thật với docker giả: log đúng thứ tự, current_tag/previous_tag ghi đúng."""
    appback_dir = tmp_path / "opt-appback"
    appback_dir.mkdir()
    (appback_dir / "current_tag").write_text("sha-old00000001", encoding="utf-8")
    bin_dir, state = _fake_docker(tmp_path)
    (state / "ids").write_text("old1\n", encoding="utf-8")
    log = tmp_path / "docker.log"

    with HttpStub(SMOKE_ROUTES) as stub:
        env = {
            "APPBACK_DIR": str(appback_dir),
            "APPBACK_BASE_URL": stub.url,
            "APPBACK_HEALTH_TIMEOUT_S": "5",
            "APPBACK_HEALTH_POLL_S": "1",
            "DOCKER_STATE": str(state),
            "FAKE_LOG": str(log),
        }
        result = run_script(SCRIPT, ["sha-new00000001"], env=env, bin_dir=bin_dir)

    assert result.returncode == 0, result.stderr
    lines = list(read_log(log))
    idx = {
        "pull": next(i for i, ln in enumerate(lines) if "pull" in ln),
        "migrate": next(i for i, ln in enumerate(lines) if "migrate" in ln),
        "scale2": next(i for i, ln in enumerate(lines) if "scale api=2" in ln),
        "healthy_check": next(i for i, ln in enumerate(lines) if ln.startswith("docker inspect")),
        "rm_old": next(i for i, ln in enumerate(lines) if ln == "docker rm old1"),
        "scale1": next(i for i, ln in enumerate(lines) if "scale api=1" in ln),
    }
    assert idx["pull"] < idx["migrate"] < idx["scale2"] < idx["healthy_check"] < idx["rm_old"] < idx["scale1"]
    assert (appback_dir / "current_tag").read_text(encoding="utf-8") == "sha-new00000001"
    assert (appback_dir / "previous_tag").read_text(encoding="utf-8") == "sha-old00000001"


def test_deploy_migrate_failure_does_not_touch_containers(tmp_path: Path) -> None:
    """Migrate hỏng → không có up/stop/rm sau migrate, thoát khác 0."""
    appback_dir = tmp_path / "opt-appback"
    appback_dir.mkdir()
    bin_dir, state = _fake_docker(tmp_path)
    (state / "ids").write_text("old1\n", encoding="utf-8")
    log = tmp_path / "docker.log"
    env = {
        "APPBACK_DIR": str(appback_dir),
        "DOCKER_STATE": str(state),
        "DOCKER_MIGRATE_EXIT": "1",
        "FAKE_LOG": str(log),
    }
    result = run_script(SCRIPT, ["sha-new00000001"], env=env, bin_dir=bin_dir)
    assert result.returncode != 0
    lines = list(read_log(log))
    migrate_idx = next(i for i, ln in enumerate(lines) if "migrate" in ln)
    assert all("up" not in ln and "stop" not in ln and " rm " not in f" {ln} " for ln in lines[migrate_idx + 1 :])


def test_deploy_smoke_failure_rolls_back_to_previous_tag(tmp_path: Path) -> None:
    """Smoke hỏng (HttpStub thiếu route) → log có lệnh rollback với tag từ previous_tag."""
    appback_dir = tmp_path / "opt-appback"
    appback_dir.mkdir()
    (appback_dir / "current_tag").write_text("sha-old00000001", encoding="utf-8")
    bin_dir, state = _fake_docker(tmp_path)
    (state / "ids").write_text("old1\n", encoding="utf-8")
    log = tmp_path / "docker.log"

    incomplete_routes = dict(SMOKE_ROUTES)
    del incomplete_routes["/draco/draco_decoder.wasm"]
    with HttpStub(incomplete_routes) as stub:
        env = {
            "APPBACK_DIR": str(appback_dir),
            "APPBACK_BASE_URL": stub.url,
            "APPBACK_HEALTH_TIMEOUT_S": "5",
            "APPBACK_HEALTH_POLL_S": "1",
            "DOCKER_STATE": str(state),
            "FAKE_LOG": str(log),
        }
        result = run_script(SCRIPT, ["sha-new00000001"], env=env, bin_dir=bin_dir)

    assert result.returncode != 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    lines = list(read_log(log))
    # rollback.sh gọi lại `docker compose pull` với IMAGE_TAG=previous_tag rồi đổi api một lần nữa.
    scale2_count = sum(1 for ln in lines if "scale api=2" in ln)
    assert scale2_count == 2, (
        f"scale2_count={scale2_count} lines={lines} stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert (
        not (appback_dir / "current_tag").exists()
        or (appback_dir / "current_tag").read_text(encoding="utf-8") != "sha-new00000001"
    )


def test_deploy_new_container_unhealthy_timeout_keeps_old_and_removes_new(tmp_path: Path) -> None:
    """Container mới không healthy tới timeout → không dừng container cũ, container mới bị xoá."""
    appback_dir = tmp_path / "opt-appback"
    appback_dir.mkdir()
    bin_dir, state = _fake_docker(tmp_path)
    (state / "ids").write_text("old1\n", encoding="utf-8")
    log = tmp_path / "docker.log"
    env = {
        "APPBACK_DIR": str(appback_dir),
        "APPBACK_HEALTH_TIMEOUT_S": "1",
        "APPBACK_HEALTH_POLL_S": "1",
        "DOCKER_STATE": str(state),
        "DOCKER_UNHEALTHY": "1",
        "FAKE_LOG": str(log),
    }
    result = run_script(SCRIPT, ["sha-new00000001"], env=env, bin_dir=bin_dir)
    assert result.returncode != 0
    lines = list(read_log(log))
    assert not any(ln.startswith("docker stop") and "old1" in ln for ln in lines)
    assert any(ln == "docker rm -f c1" for ln in lines)
    assert not (appback_dir / "current_tag").exists()


def test_deploy_scale2_creates_no_new_container_fails_fast_without_touching_old(tmp_path: Path) -> None:
    """Review round 1 P3 (RES-01): `--scale api=2` không thêm container nào (`new_id` rỗng)
    → hỏng ngay, KHÔNG chờ đủ `APPBACK_HEALTH_TIMEOUT_S` và không đụng container cũ."""
    appback_dir = tmp_path / "opt-appback"
    appback_dir.mkdir()
    bin_dir, state = _fake_docker(tmp_path)
    (state / "ids").write_text("old1\n", encoding="utf-8")
    log = tmp_path / "docker.log"
    env = {
        "APPBACK_DIR": str(appback_dir),
        "APPBACK_HEALTH_TIMEOUT_S": "120",
        "APPBACK_HEALTH_POLL_S": "1",
        "DOCKER_STATE": str(state),
        "DOCKER_SCALE2_NO_NEW": "1",
        "FAKE_LOG": str(log),
    }
    start = time.monotonic()
    result = run_script(SCRIPT, ["sha-new00000001"], env=env, bin_dir=bin_dir, timeout=15)
    elapsed = time.monotonic() - start

    assert result.returncode != 0
    assert elapsed < 10, f"đợi hết {elapsed:.1f}s — chưa chặn new_id rỗng"
    lines = list(read_log(log))
    assert not any(ln.startswith("docker stop") and "old1" in ln for ln in lines)
    assert not (appback_dir / "current_tag").exists()


def test_deploy_respects_api_swap_settle_s(tmp_path: Path) -> None:
    """`APPBACK_API_SWAP_SETTLE_S` (R-05, mặc định sản xuất 11s — chờ nginx tự dịch lại DNS
    trước khi xoá container `api` cũ, NO-116) phải thật sự được `sleep`: đặt giá trị nhỏ khác 0
    và đo thời gian, để không ai âm thầm xoá dòng `sleep` trong `swap_api` mà test khác (mặc
    định 0 qua `run_script`) không bắt được."""
    appback_dir = tmp_path / "opt-appback"
    appback_dir.mkdir()
    (appback_dir / "current_tag").write_text("sha-old00000001", encoding="utf-8")
    bin_dir, state = _fake_docker(tmp_path)
    (state / "ids").write_text("old1\n", encoding="utf-8")
    log = tmp_path / "docker.log"

    with HttpStub(SMOKE_ROUTES) as stub:
        env = {
            "APPBACK_DIR": str(appback_dir),
            "APPBACK_BASE_URL": stub.url,
            "APPBACK_HEALTH_TIMEOUT_S": "5",
            "APPBACK_HEALTH_POLL_S": "1",
            "APPBACK_API_SWAP_SETTLE_S": "2",
            "DOCKER_STATE": str(state),
            "FAKE_LOG": str(log),
        }
        start = time.monotonic()
        result = run_script(SCRIPT, ["sha-new00000001"], env=env, bin_dir=bin_dir, timeout=30)
        elapsed = time.monotonic() - start

    assert result.returncode == 0, result.stderr
    assert elapsed >= 2, f"elapsed={elapsed:.1f}s — swap_api không còn sleep theo APPBACK_API_SWAP_SETTLE_S"


_NGINX_TEMPLATES = (
    REPO_ROOT / "deploy" / "nginx" / "templates" / "dev" / "app.conf.template",
    REPO_ROOT / "deploy" / "nginx" / "templates" / "prod" / "app.conf.template",
)


def test_deploy_default_swap_settle_s_covers_nginx_resolver_ttl() -> None:
    """Review round 2 N3 (R-05): ràng buộc "mặc định >= TTL cache DNS của nginx + biên an
    toàn" (comment `lib.sh`) chưa có test nào chốt trước đây — B0-08 nâng `resolver …
    valid=…` mà không ai sửa mặc định ở đây thì cổng vẫn xanh, deploy lại 502 thật. Trích
    `valid=(\\d+)s` thẳng từ CẢ HAI template thật (chỉ đọc, không sửa — thuộc B0-08) và đối
    chiếu với mặc định `${APPBACK_API_SWAP_SETTLE_S:-N}` trích thẳng từ `lib.sh`, không chép
    tay hằng số nào ở hai phía."""
    lib_sh = (REPO_ROOT / "deploy" / "scripts" / "lib.sh").read_text(encoding="utf-8")
    m = re.search(r'^: "\$\{APPBACK_API_SWAP_SETTLE_S=(\d+)\}"$', lib_sh, re.MULTILINE)
    assert m, 'không tìm thấy dòng khai báo : "${APPBACK_API_SWAP_SETTLE_S=N}" trong lib.sh'
    default_settle_s = int(m.group(1))
    assert "APPBACK_API_SWAP_SETTLE_S:-" not in lib_sh, (
        "lib.sh: còn bản sao mặc định dạng ${APPBACK_API_SWAP_SETTLE_S:-N} — phải dùng biến trần (NO-120)"
    )

    # README là bản thứ ba của cùng hằng số (NO-120): đọc từ bảng biến môi trường,
    # không chép tay, để tài liệu không trôi khỏi lib.sh.
    readme = (REPO_ROOT / "deploy" / "scripts" / "README.md").read_text(encoding="utf-8")
    rm = re.search(r"\| `APPBACK_API_SWAP_SETTLE_S` \| `(\d+)` \|", readme)
    assert rm, "README.md: không tìm thấy dòng bảng của APPBACK_API_SWAP_SETTLE_S"
    assert int(rm.group(1)) == default_settle_s, f"README.md ghi mặc định {rm.group(1)}, lib.sh khai {default_settle_s}"

    ttls: list[int] = []
    for template in _NGINX_TEMPLATES:
        text = template.read_text(encoding="utf-8")
        tm = re.search(r"resolver\s+\S+\s+valid=(\d+)s", text)
        assert tm, f"không tìm thấy `resolver … valid=Ns` trong {template}"
        ttls.append(int(tm.group(1)))

    max_ttl = max(ttls)
    assert default_settle_s >= max_ttl + 1, (
        f"mặc định APPBACK_API_SWAP_SETTLE_S={default_settle_s} không đủ che TTL cache DNS "
        f"lớn nhất của nginx ({max_ttl}s) + 1s biên an toàn"
    )


def test_deploy_bad_tag_exits_2(tmp_path: Path) -> None:
    """Tag không khớp mẫu hợp đồng §2 → thoát 2."""
    env = {"APPBACK_DIR": str(tmp_path)}
    result = run_script(SCRIPT, ["!!not-a-tag"], env=env)
    assert result.returncode == 2
