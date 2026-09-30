"""Khai task `pipeline.orchestrate.start` (B5-06a [2]); toàn bộ nghiệp vụ ở `start.py`.

Hàm task mỏng theo BE-00 §7 "Khuôn task": dựng tài nguyên tiến trình (sessionmaker, kho,
đồng hồ) rồi gọi lõi. Lỗi tạm, hết hạn thử lại và thông điệp độc do `define_task` lo, nên
ở đây không có `try`; `on_failed` chạy lõi `fail_pipeline_start_core` trên vòng sự kiện
dùng chung của tiến trình worker (`runner()`), không `asyncio.run` riêng mỗi lượt.
"""

from typing import Final

from apps.api.drawings.runs import START_TASK
from apps.worker.pipeline_orchestrate.start import fail_pipeline_start_core, run_pipeline_start
from packages.core.clock import SystemClock
from packages.db.engine import worker_sessionmaker
from packages.messaging.payloads.drawings import PipelineStartPayload
from packages.messaging.redis import ProcessLocal
from packages.messaging.tasks import define_task, runner
from packages.storage.port import ObjectStorage


def _storage() -> ObjectStorage:
    """Kho thật dựng từ biến môi trường; `create_storage` nhập trễ (K22, như B5-05)."""
    from packages.storage.factory import create_storage
    from packages.storage.settings import get_storage_settings

    return create_storage(get_storage_settings(), None, SystemClock())


_STORAGE: Final = ProcessLocal[ObjectStorage](_storage)


def reset_orchestrate_storage() -> None:
    """Chỉ cho test: quên kho đã nhớ giữa các lượt (URL kho đổi giữa các lượt test)."""
    _STORAGE.reset()


async def _fail_on_loop(payload: PipelineStartPayload, code: str) -> None:
    """Thân của `on_failed`; `worker_sessionmaker()` đòi vòng sự kiện nên phải gọi trong đây."""
    await fail_pipeline_start_core(payload, code, sessionmaker=worker_sessionmaker(), clock=SystemClock())


def fail_pipeline_start(payload: PipelineStartPayload, code: str) -> None:
    """`on_failed` đồng bộ mà `define_task` gọi; chạy lõi async trên vòng sự kiện của tiến trình."""
    runner().run(_fail_on_loop(payload, code))


@define_task(name=START_TASK, payload=PipelineStartPayload, on_failed=fail_pipeline_start)
async def orchestrate_pipeline_start(payload: PipelineStartPayload) -> None:
    """Ghim model, tiền xử lý trang, xếp ba bước ML cho một lượt chạy ([6] "start")."""
    await run_pipeline_start(
        payload,
        sessionmaker=worker_sessionmaker(),
        storage=_STORAGE.get(),
        clock=SystemClock(),
    )
