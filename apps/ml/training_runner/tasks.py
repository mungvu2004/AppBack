"""Task `ml.training.runner.start`: khởi chạy tiến trình con huấn luyện rồi ack (BE-00 §7).

`acks_late=False` vì thân task chỉ khởi chạy (BE-00 §7 "Tiến trình huấn luyện"): huấn luyện
thật chạy ở tiến trình con `apps.ml.training_runner.__main__`, không trong tiến trình Celery.
"""

import json
import logging
import subprocess
import sys
import threading
from typing import IO, Final, cast

from apps.ml.training_runner.errors import TRAINING_LAUNCH_FAILED
from apps.ml.training_runner.keys import FINISHED_TASK, START_TASK, cancel_key, claim_key, new_token
from apps.ml.training_runner.redis_sync import delete_if_owner, training_redis
from apps.ml.training_runner.settings import TrainingRunnerSettings
from packages.core.errors import AppError
from packages.messaging.celery_app import send_task
from packages.messaging.redis import SyncRedis, redis_errors, sync_result
from packages.messaging.tasks import PermanentError, define_task
from packages.ml_contracts.payloads import TrainingFinishedPayload, TrainJobPayload

__all__ = ["FINISHED_TASK", "on_failed", "start_training_runner", "subprocess", "sys", "training_redis"]

_log: Final = logging.getLogger(__name__)


def on_failed(payload: TrainJobPayload, code: str) -> None:
    """`define_task` gọi khi thân ném `PermanentError`: báo cầu nối job đã `failed`."""
    try:
        send_task(FINISHED_TASK, TrainingFinishedPayload(job_id=payload.job_id, status="failed", error_code=code))
    except AppError:
        _log.warning("training_send_failed", extra={"job_id": payload.job_id, "task": FINISHED_TASK, "error": code})


@define_task(name=START_TASK, payload=TrainJobPayload, on_failed=on_failed, acks_late=False)
def start_training_runner(payload: TrainJobPayload) -> None:
    """Claim job rồi khởi chạy `python -m apps.ml.training_runner`; đã huỷ/đã claim thì bỏ qua (J06).

    Lệnh Redis bọc `redis_errors()`: Redis hỏng thành `AppError DEPENDENCY_UNAVAILABLE`, mà
    `define_task` thử lại (J02) thay vì rơi `INTERNAL` (lỗi tạm, không phải lỗi vĩnh viễn).
    """
    settings = TrainingRunnerSettings()
    client = training_redis()
    try:
        with redis_errors():
            cancelled = sync_result(client.exists(cancel_key(payload.job_id)), int)
            if cancelled:
                _log.info("training_launch_skipped", extra={"job_id": payload.job_id, "reason": "cancelled"})
                return
            token = new_token()
            claim = claim_key(payload.job_id)
            claimed = sync_result(client.set(claim, token, nx=True, px=settings.training_claim_ttl_ms), bool)
        if not claimed:
            _log.info("training_launch_skipped", extra={"job_id": payload.job_id, "reason": "claimed"})
            return
        _launch(payload, token, claim, client)
    finally:
        client.close()


def _launch(payload: TrainJobPayload, token: str, claim: str, client: SyncRedis) -> None:
    """Khởi chạy tiến trình con rồi ghi stdin (chữ ký chung); hỏng → xoá claim, báo `TRAINING_LAUNCH_FAILED`.

    `OSError` khi ghi stdin **sau** khi `Popen` đã chạy được thì tiến trình con đã tồn tại với
    stdin hỏng (JSON cụt) — `kill()` nó trước khi xoá claim, không để nó tự gửi `finished`
    `INTERNAL` một lần nữa đè lên `finished(failed, TRAINING_LAUNCH_FAILED)` của task này.
    """
    stdin = json.dumps({"claim_token": token, "payload": payload.model_dump(mode="json")}).encode("utf-8")
    proc: subprocess.Popen[bytes] | None = None
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "apps.ml.training_runner"], stdin=subprocess.PIPE, start_new_session=True
        )
        # `stdin=PIPE` luôn cho `proc.stdin`; `cast` thay nhánh `None` chết (không phủ được).
        pipe = cast("IO[bytes]", proc.stdin)
        pipe.write(stdin)
        pipe.close()
    except OSError:
        if proc is not None:
            proc.kill()
        with redis_errors():
            delete_if_owner(client, claim, token)
        raise PermanentError(TRAINING_LAUNCH_FAILED) from None
    threading.Thread(target=proc.wait, daemon=True).start()
