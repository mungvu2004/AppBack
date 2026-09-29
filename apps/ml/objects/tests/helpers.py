"""Dựng dữ liệu thử cho `apps.ml.objects`: payload bước, kho hỏng tạm.

Chép khuôn từ `apps/ml/text/tests/helpers.py` và `apps/ml/walls/tests/helpers.py` chứ
**không** nhập chéo (BE-00 §2). Model ONNX tí hon (`storage_ref`, `load_session`) là của
việc A, `apps/ml/objects/tests/onnx_models.py` — không dựng bộ thứ hai ở đây.
"""

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

from packages.core.clock import SystemClock
from packages.core.errors import AppError
from packages.core.ids import IdPrefix, new_id
from packages.ml_contracts.payloads import InferStepPayload, ModelRef
from packages.storage.local import LocalDiskStorage
from packages.storage.port import CHUNK_SIZE, ObjectStorage

STEP = "openingAndFurnitureDetection"


def some_id(prefix: IdPrefix) -> str:
    """Id mới đúng tiền tố (`run`, `mdl`, `upl`, …)."""
    return new_id(prefix, SystemClock())


def infer_payload(*, width: int, height: int, model_ref: ModelRef | None = None, step: str = STEP) -> InferStepPayload:
    """Payload bước suy luận hợp lệ; model mặc định là dạng cổ điển của chính `step`."""
    prefix = f"projects/{some_id('prj')}/floors/L-ABCDEFGHIJ/uploads/{some_id('upl')}/"
    run = some_id("run")
    ref = model_ref or ModelRef(version_id=None, family=step, weights_key=None, pinned_name=None, checksum_sha256="")
    return InferStepPayload(
        run_id=run,
        step=step,
        page_key=f"{prefix}pages/0.png",
        width_px=width,
        height_px=height,
        artifact_prefix=f"{prefix}runs/{run}/{step}/",
        model=ref,
    )


def put_sync(storage: ObjectStorage, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    """Ghi một object từ test đồng bộ (worker thật chạy ngoài vòng sự kiện của test)."""
    asyncio.run(storage.put(key, data, content_type=content_type, max_bytes=len(data) + 1))


def read_sync(storage: ObjectStorage, key: str) -> bytes | None:
    """Nội dung object, hay `None` khi chưa có."""

    async def read() -> bytes | None:
        """Đọc toàn bộ nội dung nếu object tồn tại, không thì `None`."""
        if await storage.stat(key) is None:
            return None
        return b"".join([chunk async for chunk in storage.open_read(key)])

    return asyncio.run(read())


class FlakyReads(LocalDiskStorage):
    """Kho đĩa thật hỏng `failures` lượt đọc đầu rồi đọc được (kho chập chờn, J02).

    `failures` âm nghĩa là hỏng mãi. Đếm theo tiến trình vì worker thử của B0-05 chạy
    trong chính tiến trình pytest.
    """

    def __init__(self, root: Path, error: AppError, *, failures: int) -> None:
        """`error` là lỗi tạm kho ném ra ở mỗi lượt đọc còn trong hạn `failures`."""
        super().__init__(root, SystemClock(), "https://x.test")
        self.error = error
        self.failures = failures
        self.attempts = 0

    async def open_read(self, key: str, *, chunk_size: int = CHUNK_SIZE) -> AsyncIterator[bytes]:
        """Lượt đọc thứ `n`: ném khi `n ≤ failures`, không thì đọc như kho thật."""
        self.attempts += 1
        if self.failures < 0 or self.attempts <= self.failures:
            raise self.error
        async for chunk in super().open_read(key, chunk_size=chunk_size):
            yield chunk
