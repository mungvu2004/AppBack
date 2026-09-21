"""Worker thật chết giữa task: giao lại qua `task_reject_on_worker_lost`, quá trần thì `WORKER_LOST`.

Worker chạy trong **tiến trình con** (`celery … worker -P prefork -c 1`, app ở `worker_probe.py`):
`SIGKILL` tiến trình con đang chạy task là đúng cảnh "worker chết" của production — tiến trình
cha thấy `WorkerLostError`, trả thông điệp về hàng, tiến trình con mới nhận lại cùng `task_id`
(FIX-020, NO-022). Worker chỉ nghe hàng của task đang kiểm; hàng được dọn đầu và cuối test
(BE-00 §7 "Test task"). Mọi lượt chờ đọc **trạng thái** trong Redis, có trần, không `sleep` đoán.
"""

import os
import signal
import subprocess
import sys
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import partial
from pathlib import Path
from typing import Final

from packages.messaging.celery_app import DEFAULT_QUEUE, producer_app
from packages.messaging.redis import SyncRedis, broker_redis_sync, safe_redis_sync, sync_result
from packages.messaging.tasks import MAX_DELIVERIES, WORKER_LOST

REPO_ROOT: Final = Path(__file__).resolve().parents[3]
PROBE_APP: Final = "packages.messaging.tests.worker_probe"
# Trùng với `worker_probe.py`: tiến trình test không nhập module đó (docstring của nó nói vì sao).
TASK_NAME: Final = "tests.crash.hang"
WAIT_S: Final = 60.0
"""Trần cho mỗi lượt chờ: tiến trình con mới + giao lại mất ~1 s, trần chỉ để test không treo."""
STOP_S: Final = 20.0
POLL_S: Final = 0.1


def wait_for[T](read: Callable[[], T | None], what: str, log: Path) -> T:
    """Đọc lặp tới khi có giá trị; hết trần thì hỏng, kèm đuôi log của worker để gỡ lỗi."""
    deadline = time.monotonic() + WAIT_S
    while time.monotonic() < deadline:
        value = read()
        if value is not None:
            return value
        time.sleep(POLL_S)
    tail = log.read_text(encoding="utf-8", errors="replace")[-4000:]
    raise AssertionError(f"quá {WAIT_S} s mà chưa: {what}\n--- log worker ---\n{tail}")


def nth_pid(client: SyncRedis, key: str, delivery: int) -> int | None:
    """PID của lượt giao thứ `delivery` (đếm từ 1), `None` khi lượt đó chưa vào thân task."""
    pids = sync_result(client.lrange(key, 0, -1), list)
    return int(pids[delivery - 1]) if len(pids) >= delivery else None


@contextmanager
def probe_worker(log: Path) -> Iterator[None]:
    """Worker prefork một tiến trình con, nghe đúng `default`; dừng cả nhóm tiến trình khi xong.

    Nhóm tiến trình riêng (`start_new_session`): test hỏng giữa chừng thì `SIGKILL` cả nhóm,
    không để tiến trình con mồ côi treo tiếp trong container.
    """
    command = [sys.executable, "-m", "celery", "-A", PROBE_APP, "worker", "-Q", DEFAULT_QUEUE]
    command += ["-P", "prefork", "-c", "1", "--without-heartbeat", "--without-mingle", "--without-gossip"]
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    with log.open("wb") as out:
        worker = subprocess.Popen(  # noqa: S603 — lệnh cố định: python của môi trường + app trong repo
            [*command, "-l", "INFO"],
            cwd=REPO_ROOT,
            env=env,
            stdout=out,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            yield
        finally:
            os.killpg(worker.pid, signal.SIGTERM)
            try:
                worker.wait(timeout=STOP_S)
            except subprocess.TimeoutExpired:
                os.killpg(worker.pid, signal.SIGKILL)
                worker.wait(timeout=STOP_S)


def test_a_worker_killed_mid_task_is_redelivered_until_worker_lost(messaging_env: None, tmp_path: Path) -> None:
    """Mỗi lần tiến trình con bị giết, thông điệp quay lại hàng; lượt thứ `MAX_DELIVERIES + 1`
    không chạy thân nữa mà báo `WORKER_LOST` cho `on_failed` rồi ack (BE-00 §7)."""
    run_id = f"crash-{uuid.uuid4().hex}"
    task_id = f"tid-{run_id}"
    pids_key, failed_key = f"probe:{run_id}:pids", f"probe:{run_id}:failed"
    broker, safe = broker_redis_sync(), safe_redis_sync()
    log = tmp_path / "worker.log"
    try:
        broker.delete(DEFAULT_QUEUE)
        with probe_worker(log):
            body = {"schema_version": 1, "run_id": run_id}
            producer_app().send_task(TASK_NAME, args=[body], queue=DEFAULT_QUEUE, task_id=task_id, retry=False)
            for delivery in range(1, MAX_DELIVERIES + 1):
                pid = wait_for(partial(nth_pid, safe, pids_key, delivery), f"lượt giao {delivery} vào thân", log)
                os.kill(pid, signal.SIGKILL)
            code = wait_for(partial(safe.get, failed_key), "on_failed nhận mã hỏng", log)

        assert code == WORKER_LOST
        pids = sync_result(safe.lrange(pids_key, 0, -1), list)
        assert len(pids) == MAX_DELIVERIES
        assert len(set(pids)) == MAX_DELIVERIES
    finally:
        broker.delete(DEFAULT_QUEUE)
        safe.delete(pids_key, failed_key, f"delivery:{task_id}")
        broker.close()
        safe.close()
