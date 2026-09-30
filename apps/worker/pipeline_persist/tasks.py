"""Khai task `pipeline.persist.run` (B5-06b [2]); toàn bộ nghiệp vụ ở `service.py`.

Hàm task mỏng theo BE-00 §7 "Khuôn task": dựng tài nguyên tiến trình (sessionmaker, kho,
đồng hồ) rồi gọi lõi. Lỗi tạm, hết hạn thử lại và thông điệp độc do `define_task` lo, nên ở
đây không có `try`; `on_failed` chạy `fail_step` trên vòng sự kiện dùng chung của tiến trình
worker (`runner()`), không `asyncio.run` riêng mỗi lượt.
"""

from typing import Final

from apps.worker.pipeline_persist.service import fail_step, run_persist
from packages.core.clock import SystemClock
from packages.db.engine import worker_sessionmaker
from packages.messaging.payloads.pipeline import RunStepPayload
from packages.messaging.redis import ProcessLocal
from packages.messaging.tasks import define_task, runner
from packages.storage.port import ObjectStorage

PERSIST_TASK: Final = "pipeline.persist.run"
"""Tên task; B5-06c gửi nó khi `persisted_revision` của lượt còn NULL (B5-06b [2])."""


def _storage() -> ObjectStorage:
    """Kho thật dựng từ biến môi trường; `create_storage` nhập trễ (K22, như B5-05, B5-06a)."""
    from packages.storage.factory import create_storage
    from packages.storage.settings import get_storage_settings

    return create_storage(get_storage_settings(), None, SystemClock())


_STORAGE: Final = ProcessLocal[ObjectStorage](_storage)


def reset_persist_storage() -> None:
    """Chỉ cho test: quên kho đã nhớ giữa các lượt (URL kho đổi giữa các lượt test)."""
    _STORAGE.reset()


async def _fail_on_loop(payload: RunStepPayload, code: str) -> None:
    """Thân của `on_failed`; `worker_sessionmaker()` đòi vòng sự kiện nên phải gọi trong đây."""
    await fail_step(payload, code, sessionmaker=worker_sessionmaker(), clock=SystemClock())


def fail_persist_step(payload: RunStepPayload, code: str) -> None:
    """`on_failed` đồng bộ mà `define_task` gọi; chạy lõi async trên vòng sự kiện của tiến trình."""
    runner().run(_fail_on_loop(payload, code))


@define_task(name=PERSIST_TASK, payload=RunStepPayload, on_failed=fail_persist_step)
async def persist_pipeline_result(payload: RunStepPayload) -> None:
    """Ghi lớp AI đã dựng vào tài liệu tầng, báo `aiCompleted`, xếp bước chất lượng ([6])."""
    await run_persist(
        payload,
        sessionmaker=worker_sessionmaker(),
        storage=_STORAGE.get(),
        clock=SystemClock(),
    )
