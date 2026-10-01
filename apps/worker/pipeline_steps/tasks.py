"""Khai task `pipeline.orchestrate.step_done` (B5-06c [2]); nghiệp vụ ở `step_done.py`.

Hàm task mỏng theo BE-00 §7 "Khuôn task": dựng sessionmaker, đồng hồ rồi gọi lõi. Lỗi tạm và
thông điệp độc do `define_task` lo; `on_failed` chạy lõi trên vòng sự kiện của tiến trình.
"""

from apps.worker.pipeline_steps.step_done import (
    STEP_DONE_TASK,
    fail_pipeline_step_done_core,
    run_pipeline_step_done,
)
from packages.core.clock import SystemClock
from packages.db.engine import worker_sessionmaker
from packages.messaging.tasks import define_task, runner
from packages.ml_contracts.payloads import StepResultPayload


async def _fail_on_loop(payload: StepResultPayload, code: str) -> None:
    """Thân của `on_failed`; `worker_sessionmaker()` đòi vòng sự kiện nên phải gọi trong đây."""
    await fail_pipeline_step_done_core(payload, code, sessionmaker=worker_sessionmaker(), clock=SystemClock())


def fail_pipeline_step_done(payload: StepResultPayload, code: str) -> None:
    """`on_failed` đồng bộ mà `define_task` gọi; chạy lõi async trên vòng sự kiện của tiến trình."""
    runner().run(_fail_on_loop(payload, code))


@define_task(name=STEP_DONE_TASK, payload=StepResultPayload, on_failed=fail_pipeline_step_done)
async def orchestrate_pipeline_step_done(payload: StepResultPayload) -> None:
    """Nhận kết quả một bước, đẩy bước theo thứ tự, xếp dựng/ghi ([6] "step_done")."""
    await run_pipeline_step_done(payload, sessionmaker=worker_sessionmaker(), clock=SystemClock())
