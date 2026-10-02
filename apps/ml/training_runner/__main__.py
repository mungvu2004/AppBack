"""Điểm vào tiến trình con huấn luyện: `python -m apps.ml.training_runner`, payload qua stdin.

Launcher (B6-03b [6] bước 3) ghi đúng một đối tượng JSON `{"claim_token", "payload"}` rồi đóng
stdin. `main()` là handler cuối của tiến trình: bất kỳ lỗi lạ nào cũng phải thành
`finished(failed, INTERNAL)` và mã thoát 1 — job treo "running" mãi là hỏng tệ hơn.
Log máy chủ chỉ mang `job_id`, không bao giờ thân payload (dữ liệu dự án).
"""

import importlib
import json
import logging
import sys
import time
from typing import Final

from apps.ml.runtime.settings import MlEnvSettings
from apps.ml.runtime.trainers import discover_trainers
from apps.ml.training_runner.errors import INTERNAL
from apps.ml.training_runner.keys import FINISHED_TASK
from apps.ml.training_runner.redis_sync import training_redis
from apps.ml.training_runner.runner import Trainers, run_training_job
from apps.ml.training_runner.settings import TrainingRunnerSettings
from packages.core.clock import SystemClock
from packages.core.errors import AppError
from packages.messaging.celery_app import send_task
from packages.ml_contracts.payloads import TrainingFinishedPayload, TrainJobPayload
from packages.storage.factory import create_storage
from packages.storage.settings import get_storage_settings

_log: Final = logging.getLogger(__name__)


def _trainers(settings: TrainingRunnerSettings) -> Trainers:
    """`discover_trainers`, hay trainer tiêm bằng `TRAINING_TRAINER_OVERRIDE` **chỉ khi** `APP_ENV=test`.

    Ngoài `test` biến bị bỏ qua và log `WARNING`: nạp module lạ trong tiến trình huấn luyện
    của staging/production là lối chạy mã tuỳ ý (B6-03b [5]).
    """
    override = settings.training_trainer_override
    if override is None:
        return discover_trainers
    if MlEnvSettings().app_env != "test":
        _log.warning("training_trainer_override_ignored")
        return discover_trainers
    module_name, _, attribute = override.partition(":")
    trainer = getattr(importlib.import_module(module_name), attribute)
    return lambda: {trainer.family: trainer}


def main() -> None:
    """Đọc stdin, dựng phụ thuộc thật, chạy lượt, thoát bằng mã của `run_training_job`."""
    job_id = ""
    try:
        request = json.loads(sys.stdin.read())
        payload = TrainJobPayload.model_validate(request["payload"])
        job_id = payload.job_id
        settings = TrainingRunnerSettings()
        code = run_training_job(
            payload,
            claim_token=str(request["claim_token"]),
            trainers=_trainers(settings),
            storage=create_storage(get_storage_settings(), None, SystemClock()),
            send=send_task,
            redis=training_redis(),
            clock=SystemClock(),
            monotonic=time.monotonic,
            settings=settings,
        )
    except Exception:  # noqa: BLE001 — handler cuối của tiến trình: lỗi lạ vẫn phải báo job hỏng (B6-03b [6] bước 9)
        _log.exception("training_runner_crashed", extra={"job_id": job_id})
        _report_internal(job_id)
        sys.exit(1)
    sys.exit(code)


def _report_internal(job_id: str) -> None:
    """Gửi `finished(failed, INTERNAL)` cho job đã biết id; broker hỏng → chỉ log, vẫn thoát 1."""
    if not job_id:
        return
    try:
        send_task(FINISHED_TASK, TrainingFinishedPayload(job_id=job_id, status="failed", error_code=INTERNAL))
    except AppError:
        _log.exception("training_finished_unsent", extra={"job_id": job_id})


if __name__ == "__main__":
    main()
