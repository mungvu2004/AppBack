"""NO-281 — container dịch vụ của một phiên pytest bị giết cứng được dọn ở lượt sau, theo nhãn chủ.

Ryuk đã tắt (FIX-114) nên không ai dọn container của phiên chết giữa chừng. Mỗi container dịch vụ mang
nhãn `OWNER_LABEL` = `<hostname>:<pid tiến trình điều khiển>`; lượt dựng dịch vụ đầu tiên của phiên kế
xoá container có chủ đã chết và **giữ** container của phiên còn sống (cả phiên ở container verify khác).
Docker thật (K23): container chỉ `create`, không chạy, nên rẻ.
"""

import os
import socket
import subprocess
import sys
import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from pathlib import Path
from unittest.mock import patch

import pytest
from docker.errors import NotFound  # type: ignore[import-untyped]  # không có stub
from testcontainers.core.docker_client import DockerClient  # type: ignore[import-untyped]  # không có stub

from packages.testing.fixtures import services
from packages.testing.fixtures.services import OWNER_LABEL, REDIS_IMAGE, sweep_orphans


def _dead_pid() -> int:
    """Pid của một tiến trình vừa kết thúc trên máy này.

    Dưới `-n`, pid có thể bị tiến trình khác dùng lại ngay (pid_max hàng triệu, cực hiếm) — khi đó
    container được *giữ* (hướng an toàn) và test đỏ giả; chấp nhận, không thử lại.
    """
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    return proc.pid


@pytest.fixture
def labelled() -> Iterator[dict[str, str]]:
    """Một container (dựng, không chạy) cho mỗi kiểu chủ; trả {kiểu: id}; dọn phần còn lại sau test.

    "live_container": chủ là hostname của một container **đang chạy** khác (Redis tạm) — như phiên ở
    một container verify-run khác còn sống.
    """
    client = DockerClient().client
    running = services.ephemeral_redis("noeviction")
    host = socket.gethostname()
    owners = {
        "dead_local": f"{host}:{_dead_pid()}",
        "live_local": services.session_owner(),
        "gone_container": "0123456789ab:1",
        "live_container": f"{running.get_wrapped_container().id[:12]}:1",
        "unknown_host": "ci-runner-7:1",
        "bad_label": f"{host}:not-a-pid",
    }
    ids = {
        kind: client.containers.create(REDIS_IMAGE, labels={OWNER_LABEL: owner}).id for kind, owner in owners.items()
    }
    try:
        yield ids
    finally:
        try:
            for container_id in ids.values():
                with suppress(NotFound):
                    client.containers.get(container_id).remove(force=True)
        finally:
            running.stop()


def _exists(container_id: str) -> bool:
    """Container còn trên Docker không."""
    try:
        DockerClient().client.containers.get(container_id)
    except NotFound:
        return False
    return True


def test_sweep_orphans__removes_dead_owner_keeps_live(labelled: dict[str, str]) -> None:
    """Chủ chết (pid mất cùng máy, container verify đã biến mất) → xoá; chủ sống hoặc không xác định → giữ.

    Khẳng định trên **trạng thái Docker**, không trên danh sách trả về: tiến trình xdist hay phiên verify
    khác có thể dọn cùng lúc (hành vi đúng — `NotFound` được nuốt), và khi đó id nằm ở danh sách của họ.
    """
    sweep_orphans()

    assert not _exists(labelled["dead_local"])
    assert not _exists(labelled["gone_container"])
    assert all(_exists(labelled[kind]) for kind in ("live_local", "live_container", "unknown_host", "bad_label"))


def test_session_owner__xdist_worker_points_at_controller(monkeypatch: pytest.MonkeyPatch) -> None:
    """Trong tiến trình xdist, chủ là tiến trình điều khiển (cha) — sống tới hết cả lượt `-n`."""
    monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw3")
    assert services.session_owner().endswith(f":{os.getppid()}")
    monkeypatch.delenv("PYTEST_XDIST_WORKER")
    assert services.session_owner().endswith(f":{os.getpid()}")


def test_start__labels_service_container_with_owner() -> None:
    """Container dựng qua fixture mang nhãn chủ **và** vẫn giữ nhãn phiên của testcontainers."""
    container = services.ephemeral_redis("noeviction")
    try:
        labels = container.get_wrapped_container().labels
        assert labels[OWNER_LABEL] == services.session_owner()
        assert "org.testcontainers.session-id" in labels
    finally:
        container.stop()


def test_remove_container__concurrent_removal_both_succeed() -> None:
    """Hai người dọn cùng xoá một container mồ côi → không ai ném, container biến mất (review DEBT-02 #2).

    Container **chạy** (xoá cứng phải giết rồi chờ, cửa sổ "removal in progress" rộng hơn container chỉ
    `create`) và vài cái nối nhau để hai luồng đụng nhau ít nhất một lần: người tới sau nhận 409 hoặc 404.
    """
    client = DockerClient().client
    owner = f"{socket.gethostname()}:{_dead_pid()}"
    ids = [client.containers.run(REDIS_IMAGE, detach=True, labels={OWNER_LABEL: owner}).id for _ in range(4)]
    barrier = threading.Barrier(2, timeout=60)

    def remove_all() -> None:
        """Chờ luồng kia rồi xoá lần lượt mọi container."""
        barrier.wait()
        for container_id in ids:
            services._remove_container(container_id)

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(remove_all) for _ in range(2)]
        for future in futures:
            future.result()
        assert not any(_exists(container_id) for container_id in ids)
    finally:
        for container_id in ids:
            with suppress(NotFound):
                client.containers.get(container_id).remove(force=True)


def test_owner_alive__overflowing_pid_label_is_kept() -> None:
    """Pid vượt `pid_t` trong nhãn hỏng → không biết chủ → giữ, không nổ `OverflowError` (review DEBT-02 #17)."""
    assert services._owner_alive(f"{socket.gethostname()}:{2**70}", client=None)


def test_sweep_once__one_sweep_per_session(tmp_path: Path) -> None:
    """Mọi tiến trình của cùng phiên gọi `_sweep_once` → chỉ người đầu quét; phiên khác thì quét lại (#2).

    `__wrapped__` bỏ `@cache` để giả lập tiến trình xdist khác (mỗi tiến trình một cache).
    """
    with (
        patch.object(services, "_SWEEP_STATE", tmp_path / "sweep.owner"),
        patch.object(services, "sweep_orphans") as sweep,
    ):
        services._sweep_once.__wrapped__()
        services._sweep_once.__wrapped__()
        assert sweep.call_count == 1
        (tmp_path / "sweep.owner").write_text("other-host:1", encoding="utf-8")
        services._sweep_once.__wrapped__()
        assert sweep.call_count == 2
