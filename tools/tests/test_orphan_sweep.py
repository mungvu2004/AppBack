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
from collections.abc import Iterator
from contextlib import suppress

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
