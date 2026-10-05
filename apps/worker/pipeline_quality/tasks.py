"""Khai task `pipeline.quality.run` (B5-07 [2]); toàn bộ nghiệp vụ ở `service.py`.

Hàm task mỏng theo BE-00 §7 "Khuôn task" (như `pipeline_persist/tasks.py`): dựng tài nguyên tiến
trình (sessionmaker, kho, đồng hồ) rồi gọi lõi. Lỗi tạm, hết hạn thử lại và thông điệp độc do
`define_task` lo; `on_failed` chạy `fail_quality` trên vòng sự kiện dùng chung của tiến trình.
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Final

from apps.worker.pipeline_quality.service import fail_quality, run_quality
from packages.core.clock import SystemClock
from packages.db.engine import worker_sessionmaker
from packages.messaging.payloads.pipeline import RunStepPayload
from packages.messaging.redis import ProcessLocal
from packages.messaging.tasks import define_task, runner
from packages.storage.port import ObjectStorage

QUALITY_TASK: Final = "pipeline.quality.run"
"""Tên task; B5-06b gửi nó sau khi ghi lớp, B5-06c gửi lại khi quét bù (B5-07 [2])."""


def open_storage() -> ObjectStorage:
    """Kho thật dựng từ biến môi trường; `create_storage` nhập trễ (K22, như B5-06b)."""
    from packages.storage.factory import create_storage
    from packages.storage.settings import get_storage_settings

    return create_storage(get_storage_settings(), None, SystemClock())


_STORAGE: Final = ProcessLocal[ObjectStorage](open_storage)


@contextmanager
def override_quality_storage(factory: Callable[[], ObjectStorage]) -> Iterator[None]:
    """Chỉ cho test: task chạy trên kho do `factory` dựng trong khối `with`, trả kho thật khi thoát."""
    with _STORAGE.override(factory):
        yield


def reset_quality_storage() -> None:
    """Chỉ cho test: quên kho đã nhớ giữa các lượt (URL kho đổi giữa các lượt test)."""
    _STORAGE.reset()


async def _fail_on_loop(payload: RunStepPayload, code: str) -> None:
    """Thân của `on_failed`; `worker_sessionmaker()` đòi vòng sự kiện nên phải gọi trong đây."""
    await fail_quality(payload, code, sessionmaker=worker_sessionmaker(), clock=SystemClock())


def fail_quality_step(payload: RunStepPayload, code: str) -> None:
    """`on_failed` đồng bộ mà `define_task` gọi; chạy lõi async trên vòng sự kiện của tiến trình."""
    runner().run(_fail_on_loop(payload, code))


@define_task(name=QUALITY_TASK, payload=RunStepPayload, on_failed=fail_quality_step)
async def check_pipeline_quality(payload: RunStepPayload) -> None:
    """Kiểm toàn vẹn + đếm mục tin cậy thấp, ghi `quality.json`, đóng lượt (`qualityCheck`, [6])."""
    await run_quality(
        payload,
        sessionmaker=worker_sessionmaker(),
        storage=_STORAGE.get(),
        clock=SystemClock(),
    )
