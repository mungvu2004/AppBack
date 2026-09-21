"""App Celery của test "worker chết giữa task" (FIX-020, NO-022) — chỉ nhập trong tiến trình con.

`celery -A packages.messaging.tests.worker_probe worker -P prefork -c 1` chạy task `hang`:
mỗi lượt giao ghi PID của tiến trình con vào Redis an toàn rồi treo, để test `SIGKILL`
đúng tiến trình đang chạy task. Tiến trình test **không** nhập module này: `create_celery`
đặt `DB_AFTER_COMMIT_INLINE` và gắn app hiện hành cho cả tiến trình nhập nó.
"""

import os
import time
from typing import Final

from packages.messaging.celery_app import create_celery
from packages.messaging.redis import safe_redis_sync
from packages.messaging.tasks import TaskPayload, define_task

TASK_NAME: Final = "tests.crash.hang"
KEY_TTL_S: Final = 300
HANG_S: Final = 120.0
"""Dài hơn mọi trần chờ của test: task chỉ kết thúc vì bị giết."""

app = create_celery("worker-probe")


class CrashJob(TaskPayload):
    """Payload của task treo; `run_id` tách khoá Redis của từng lượt test."""

    schema_version: int = 1
    run_id: str


def pids_key(run_id: str) -> str:
    """Danh sách PID của các lượt giao đã vào thân task."""
    return f"probe:{run_id}:pids"


def failed_key(run_id: str) -> str:
    """Mã hỏng mà `on_failed` ghi lại."""
    return f"probe:{run_id}:failed"


def record_failure(payload: CrashJob, code: str) -> None:
    """`on_failed` chạy trong tiến trình con: ghi mã vào Redis để test đọc được."""
    client = safe_redis_sync()
    try:
        client.set(failed_key(payload.run_id), code, ex=KEY_TTL_S)
    finally:
        client.close()


@define_task(name=TASK_NAME, payload=CrashJob, on_failed=record_failure)
def hang(payload: CrashJob) -> None:
    """Ghi PID của lượt giao này rồi treo cho tới khi bị giết."""
    client = safe_redis_sync()
    try:
        client.rpush(pids_key(payload.run_id), os.getpid())
        client.expire(pids_key(payload.run_id), KEY_TTL_S)
    finally:
        client.close()
    time.sleep(HANG_S)
