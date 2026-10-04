"""Khoá GPU `gpu:0` trên DB Redis an toàn: một tác vụ GPU mỗi lúc (BE-00 §9, M04).

`gpu_slot` là context **đồng bộ** cho mã huấn luyện (không có vòng sự kiện): lấy, gia hạn,
cờ `lost` và trả khoá là lõi chung `held_lease` (`apps/ml/runtime/lease.py`, cùng lõi với
`training_slot`, NO-308). Lớp vỏ ở đây chỉ chuyển ba phép của lõi sang `SafeLock` (async,
token rào, khoá `lock:gpu:0`): client async gắn với vòng tạo ra nó, nên mọi lời gọi đi qua
**một** vòng sự kiện chạy trong luồng daemon riêng (`SafeLockOps`).
"""

import asyncio
import threading
from collections.abc import Coroutine, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Final

from apps.ml.runtime.errors import GPU_LOCK_LOST
from apps.ml.runtime.lease import JOIN_TIMEOUT_S, check_timing, held_lease
from packages.core.error_codes import DEPENDENCY_UNAVAILABLE
from packages.core.errors import AppError
from packages.messaging.locks import SafeLock
from packages.messaging.redis import AsyncRedis, safe_redis
from packages.messaging.tasks import PermanentError

GPU_LOCK_NAME: Final = "gpu:0"


@dataclass(frozen=True, slots=True)
class GpuSlot:
    """Chỗ GPU đang giữ: token rào của khoá và cờ mất khoá."""

    token: int
    lost: threading.Event

    def check(self) -> None:
        """Gọi giữa các bước: khoá đã mất → `PermanentError(GPU_LOCK_LOST)`."""
        if self.lost.is_set():
            raise PermanentError(GPU_LOCK_LOST)


async def _client() -> AsyncRedis:
    """Client DB an toàn dựng **trong** vòng sự kiện của `SafeLockOps`."""
    return safe_redis()


class SafeLockOps:
    """`LeaseOps[int]` trên `SafeLock`: một vòng sự kiện riêng trong luồng daemon, đóng bằng `close()`."""

    def __init__(self, name: str, ttl_ms: int) -> None:
        """Mở vòng sự kiện và client; client lỗi → dọn vòng rồi nổi lên."""
        self.name = name
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, name="gpu-slot-loop", daemon=True)
        self._thread.start()
        try:
            self._client = self._call(_client())
        except BaseException:
            self._stop_loop()
            raise
        self._lock = SafeLock(self._client, name, ttl_ms)

    def _call[R](self, coro: Coroutine[Any, Any, R]) -> R:
        """Chạy `coro` trên vòng của lớp này và chờ kết quả (gọi được từ mọi luồng)."""
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result()

    def try_acquire(self) -> int | None:
        """Token rào khi lấy được, `None` khi đang bận; Redis hỏng → `AppError` 503 (task thử lại)."""
        return self._call(self._lock.acquire())

    def renew(self, token: int) -> bool | None:
        """Gia hạn; Redis không phục vụ được (`DEPENDENCY_UNAVAILABLE`) → `None`, lỗi khác nổi lên."""
        try:
            return self._call(self._lock.renew(token))
        except AppError as exc:
            if exc.code is not DEPENDENCY_UNAVAILABLE:
                raise
            return None

    def release_quietly(self, token: int) -> None:
        """Trả khoá qua `SafeLock.release_quietly` (một nguồn, NO-074): Redis hỏng chỉ ghi `WARNING`."""
        self._call(self._lock.release_quietly(token))

    def close(self) -> None:
        """Đóng client rồi dừng vòng sự kiện và luồng của nó."""
        try:
            self._call(self._client.aclose())
        finally:
            self._stop_loop()

    def _stop_loop(self) -> None:
        """Dừng `run_forever`, `join` tối đa `JOIN_TIMEOUT_S`, đóng vòng.

        Lời gọi Redis có trần kết nối/đọc của client nên vòng dừng trong hạn `join`; vòng kẹt quá
        hạn thì `close()` ném `RuntimeError` — chấp nhận, không thêm nhánh không phủ được.
        """
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(JOIN_TIMEOUT_S)
        self._loop.close()


@contextmanager
def gpu_slot(*, wait_s: float, ttl_ms: int = 60_000, renew_every_ms: int = 20_000) -> Iterator[GpuSlot]:
    """Giữ `gpu:0` suốt khối `with` (dùng khi thiết bị là `cuda`).

    Chờ tới `wait_s` → `TransientError`; Redis hỏng lúc lấy → `AppError` 503 (thử lại).
    `renew_every_ms x 2 ≥ ttl_ms` → `ValueError` trước khi chạm Redis.
    """
    check_timing(ttl_ms=ttl_ms, renew_every_ms=renew_every_ms)
    ops = SafeLockOps(GPU_LOCK_NAME, ttl_ms)
    try:
        with held_lease(ops, wait_s=wait_s, ttl_ms=ttl_ms, renew_every_ms=renew_every_ms) as lease:
            yield GpuSlot(token=lease.token, lost=lease.lost)
    finally:
        ops.close()
