"""Test `deploy/scripts/rollback.sh` — không migrate, mặc định previous_tag, tag ghi đè."""

from __future__ import annotations

from pathlib import Path

from deploy.scripts.tests.support import REPO_ROOT, HttpStub, Reply, fake_bin, read_log, run_script

SCRIPT = REPO_ROOT / "deploy" / "scripts" / "rollback.sh"

SMOKE_ROUTES = {
    "/api/health": Reply(200),
    "/api/ready": Reply(200),
    "/": Reply(200, headers={"Content-Security-Policy": "default-src 'self'"}),
    "/draco/draco_decoder.wasm": Reply(200, body=b"wasm"),
    "/api/nope": Reply(404, body=b'{"code":"NOT_FOUND"}'),
}

# `docker` giả tối giản: mọi container luôn healthy ngay — chỉ để kiểm rollback
# không gọi migrate/alembic và ghi đúng tag, không mô phỏng timeout (test_deploy.py lo việc đó).
_DOCKER_BODY = """
state="$DOCKER_STATE"
mkdir -p "$state"
ids_file="$state/ids"
touch "$ids_file"

if [[ "$1 $2" == "compose pull" ]]; then
  exit 0
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
  if [[ "$scale2" == "1" ]]; then
    n=0
    [[ -f "$state/counter" ]] && n="$(cat "$state/counter")"
    n=$((n + 1))
    echo "$n" > "$state/counter"
    id="c$n"
    echo "$id" >> "$ids_file"
    echo "healthy" > "$state/health_$id"
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
    (state / "ids").write_text("old1\n", encoding="utf-8")
    return bin_dir, state


def test_rollback_no_tag_and_no_previous_tag_exits_2(tmp_path: Path) -> None:
    """Không đối số và không có previous_tag → thoát 2."""
    appback_dir = tmp_path / "opt-appback"
    appback_dir.mkdir()
    env = {"APPBACK_DIR": str(appback_dir)}
    result = run_script(SCRIPT, [], env=env)
    assert result.returncode == 2


def test_rollback_uses_previous_tag_and_never_migrates(tmp_path: Path) -> None:
    """Mặc định đọc previous_tag, log không có migrate/alembic, ghi current_tag."""
    appback_dir = tmp_path / "opt-appback"
    appback_dir.mkdir()
    (appback_dir / "previous_tag").write_text("sha-prev0000001", encoding="utf-8")
    bin_dir, state = _fake_docker(tmp_path)
    log = tmp_path / "docker.log"

    with HttpStub(SMOKE_ROUTES) as stub:
        env = {
            "APPBACK_DIR": str(appback_dir),
            "APPBACK_BASE_URL": stub.url,
            "APPBACK_HEALTH_TIMEOUT_S": "5",
            "DOCKER_STATE": str(state),
            "FAKE_LOG": str(log),
        }
        result = run_script(SCRIPT, [], env=env, bin_dir=bin_dir)

    assert result.returncode == 0, result.stderr
    lines = list(read_log(log))
    assert lines, "docker giả phải được gọi"
    assert not any("migrate" in ln or "alembic" in ln for ln in lines)
    assert (appback_dir / "current_tag").read_text(encoding="utf-8") == "sha-prev0000001"


def test_rollback_explicit_tag_wins_over_previous_tag(tmp_path: Path) -> None:
    """Tag chỉ định trên dòng lệnh thắng nội dung previous_tag."""
    appback_dir = tmp_path / "opt-appback"
    appback_dir.mkdir()
    (appback_dir / "previous_tag").write_text("sha-prev0000001", encoding="utf-8")
    bin_dir, state = _fake_docker(tmp_path)
    log = tmp_path / "docker.log"

    with HttpStub(SMOKE_ROUTES) as stub:
        env = {
            "APPBACK_DIR": str(appback_dir),
            "APPBACK_BASE_URL": stub.url,
            "APPBACK_HEALTH_TIMEOUT_S": "5",
            "DOCKER_STATE": str(state),
            "FAKE_LOG": str(log),
        }
        result = run_script(SCRIPT, ["sha-explicit01"], env=env, bin_dir=bin_dir)

    assert result.returncode == 0, result.stderr
    assert (appback_dir / "current_tag").read_text(encoding="utf-8") == "sha-explicit01"
