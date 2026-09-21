"""Dựng runner Node: `npm ci` song song, đổi tên nguyên tử, lỗi tiến trình (B0-07 [6], [8] "Node")."""

import json
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from tools.contract import runner_client
from tools.contract.runner_client import RunnerError


def test_parallel_installs_into_the_same_target_both_finish(contract_build: Path, tmp_path: Path) -> None:
    """Hai lượt `npm ci` lạnh cùng lúc vào cùng thư mục đích: cả hai xong, đích dùng được.

    Kho npm trỏ về kho thật (đã ấm nhờ `contract_build`), nên test không tải mạng.
    """
    node_dir = tmp_path / "node"
    cache = runner_client.node_dir_from_env() / "npm-cache"
    barrier = threading.Barrier(2)

    def install() -> Path:
        """Một lượt verify lạnh; hai lượt cùng qua rào rồi mới thấy đích chưa có."""
        barrier.wait()
        return runner_client.ensure_node_modules(node_dir, cache_dir=cache)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(install) for _ in range(2)]
        results = [future.result(timeout=runner_client.NPM_TIMEOUT_S) for future in futures]
    target = node_dir / runner_client.lock_digest()
    assert results == [target, target]
    assert sorted(path.name for path in node_dir.iterdir()) == [target.name]
    node = runner_client.executable("node")
    runner_client.run_process([node, "--import", "tsx", "-e", "1"], cwd=target, timeout_s=60)


def test_existing_target_is_reused_without_npm(tmp_path: Path) -> None:
    """Đích đã có (lượt trước đã cài và kiểm xong) → trả ngay, không chạy `npm`."""
    target = tmp_path / runner_client.lock_digest()
    target.mkdir()
    assert runner_client.ensure_node_modules(tmp_path) == target


@pytest.mark.usefixtures("appfront_dir")
def test_failed_install_leaves_no_target(tmp_path: Path) -> None:
    """`npm ci` hỏng (lock lệch `package.json`) → `RunnerError`, không để lại đích hay thư mục tạm."""
    package = tmp_path / "package"
    package.mkdir()
    lock = {"name": "x", "lockfileVersion": 3, "requires": True, "packages": {"": {"name": "x"}}}
    (package / "package-lock.json").write_text(json.dumps(lock), encoding="utf-8")
    (package / "package.json").write_text(
        json.dumps({"name": "x", "dependencies": {"zod": "3.23.8"}}), encoding="utf-8"
    )
    node_dir = tmp_path / "node"
    with pytest.raises(RunnerError, match=r"npm thoát \d+"):
        runner_client.ensure_node_modules(node_dir, cache_dir=tmp_path / "cache", package_dir=package)
    assert list(node_dir.iterdir()) == []


def test_publish_keeps_the_winner(tmp_path: Path) -> None:
    """Đổi tên thua cuộc (đích đã có) không ném; đích không có mà đổi tên hỏng thì ném."""
    target, staging = tmp_path / "dich", tmp_path / "tam"
    (target / "node_modules").mkdir(parents=True)
    (staging / "node_modules").mkdir(parents=True)
    runner_client.publish(staging, target)
    assert (target / "node_modules").is_dir()
    with pytest.raises(OSError, match="khong-co"):
        runner_client.publish(tmp_path / "khong-co", tmp_path / "dich-khac")


@pytest.mark.usefixtures("appfront_dir")
def test_process_errors_become_runner_errors(tmp_path: Path) -> None:
    """Thoát khác 0 và quá trần đều thành `RunnerError` kèm lý do."""
    node = runner_client.executable("node")
    with pytest.raises(RunnerError, match="thoát 3"):
        runner_client.run_process([node, "-e", "process.exit(3)"], cwd=tmp_path, timeout_s=30)
    with pytest.raises(RunnerError, match=r"quá 0\.5 s"):
        runner_client.run_process([node, "-e", "setTimeout(() => {}, 30000)"], cwd=tmp_path, timeout_s=0.5)


def test_missing_executable_is_reported() -> None:
    """Lệnh không có trên PATH → `RunnerError` (không `FileNotFoundError` trần)."""
    with pytest.raises(RunnerError, match="khong-co-lenh"):
        runner_client.executable("khong-co-lenh-b0-07")


def test_unknown_command_fails(contract_build: Path) -> None:
    """Lệnh runner lạ: runner thoát 2 → `RunnerError`."""
    with pytest.raises(RunnerError, match="thoát 2"):
        runner_client.run_command(contract_build, "khong-co", {})


def test_non_json_output_fails(contract_build: Path, tmp_path: Path) -> None:
    """Runner in ra thứ không phải JSON → `RunnerError`."""
    build = tmp_path / "build"
    build.mkdir()
    shutil.copyfile(contract_build / "package.json", build / "package.json")
    (build / "node_modules").symlink_to((contract_build / "node_modules").resolve(), target_is_directory=True)
    (build / "runner.ts").write_text("process.stdout.write('khong phai json');\n", encoding="utf-8")
    with pytest.raises(RunnerError, match="không phải JSON"):
        runner_client.run_command(build, "smoke", {})
    assert [path.name for path in build.glob("*.json")] == ["package.json"]


def test_missing_f00a_is_an_error(tmp_path: Path) -> None:
    """AppFront không có `src/api/schemas/common.ts` → `AppFrontMissingError`."""
    with pytest.raises(runner_client.AppFrontMissingError, match="thiếu F-00a"):
        runner_client.build_layout(tmp_path, tmp_path / "node", tmp_path / "build")


def test_layout_refuses_a_non_empty_directory(appfront_dir: Path, tmp_path: Path) -> None:
    """`build_dir` đã có nội dung → `RunnerError`, không xoá gì (gõ nhầm `--build-dir` không mất nguồn)."""
    keep = tmp_path / "build" / "giu.txt"
    keep.parent.mkdir()
    keep.write_text("giu", encoding="utf-8")
    with pytest.raises(RunnerError, match="không rỗng"):
        runner_client.build_layout(appfront_dir, runner_client.node_dir_from_env(), keep.parent)
    assert keep.read_text(encoding="utf-8") == "giu"


def test_layout_resolves_alias_and_single_zod(contract_build: Path, appfront_dir: Path) -> None:
    """Bố cục có `src` chép từ AppFront, `tsconfig` alias `@/*`, `node_modules` là symlink."""
    assert (contract_build / "src" / "api" / "schemas" / "common.ts").read_bytes() == (
        appfront_dir / "src" / "api" / "schemas" / "common.ts"
    ).read_bytes()
    assert json.loads((contract_build / "tsconfig.json").read_text(encoding="utf-8"))["compilerOptions"]["paths"] == {
        "@/*": ["./src/*"]
    }
    assert (contract_build / "node_modules").is_symlink()
    assert (contract_build / "node_modules" / "zod" / "package.json").is_file()
