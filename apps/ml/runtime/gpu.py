"""Khoá GPU `gpu:0` trên DB Redis an toàn: một tác vụ GPU mỗi lúc (BE-00 §9, M04).

`gpu_slot` là context **đồng bộ** cho mã huấn luyện (không có vòng sự kiện): một luồng
daemon chạy `asyncio.Runner` riêng, dựng client `safe_redis()` ngay trong vòng đó (client
async gắn với vòng tạo ra nó), lấy `SafeLock` rồi gia hạn định kỳ. Mất khoá — gia hạn
bị từ chối, hay Redis hỏng lâu hơn `ttl_ms - renew_every_ms` (khoá có thể đã hết hạn và
người khác đã lấy) — thì bật `lost`; người giữ gọi `check()` giữa các bước để dừng.
"""

import asyncio
import logging
import random
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Final

from apps.ml.runtime.errors import GPU_LOCK_LOST
from packages.core.error_codes import DEPENDENCY_UNAVAILABLE
from packages.core.errors import AppError
from packages.messaging.locks import SafeLock
from packages.messaging.redis import AsyncRedis, safe_redis
from packages.messaging.tasks import PermanentError, TransientError

_log: Final = logging.getLogger(__name__)

GPU_LOCK_NAME: Final = "gpu:0"
ACQUIRE_EVERY_S: Final = 1.0
ACQUIRE_JITTER: Final = 0.2
JOIN_TIMEOUT_S: Final = 5.0


@dataclass(frozen=True, slots=True)
class GpuSlot:
    """Chỗ GPU đang giữ: token rào của khoá và cờ mất khoá."""

    token: int
    lost: threading.Event

    def check(self) -> None:
        """Gọi giữa các bước: khoá đã mất → `PermanentError(GPU_LOCK_LOST)`."""
        if self.lost.is_set():
            raise PermanentError(GPU_LOCK_LOST)


def _dependency_error(exc: AppError) -> bool:
    """Lỗi Redis không phục vụ được (đã dịch bởi `redis_errors`); lỗi khác phải nổi lên."""
    return exc.code is DEPENDENCY_UNAVAILABLE


class _Keeper(threading.Thread):
    """Luồng giữ khoá: lấy (thử lại mỗi 1 s ± 20 %), gia hạn, trả khoá khi được báo dừng."""

    def __init__(self, *, wait_s: float, ttl_ms: int, renew_every_ms: int) -> None:
        """Luồng daemon: tiến trình tắt giữa chừng không bị luồng giữ khoá chặn lại (TTL dọn khoá)."""
        super().__init__(name="gpu-slot", daemon=True)
        self.ready = threading.Event()
        self.stopping = threading.Event()
        self.lost = threading.Event()
        self.token: int | None = None
        self.error: Exception | None = None
        self._wait_s = wait_s
        self._ttl_ms = ttl_ms
        self._renew_every_ms = renew_every_ms

    def run(self) -> None:
        """Toàn bộ đời khoá trên một vòng sự kiện riêng; `ready` bật ở mọi đường ra."""
        try:
            with asyncio.Runner() as runner:
                client = runner.run(_client())
                try:
                    self._hold(runner, SafeLock(client, GPU_LOCK_NAME, self._ttl_ms))
                finally:
                    runner.run(client.aclose())
        finally:
            self.ready.set()

    def _hold(self, runner: asyncio.Runner, lock: SafeLock) -> None:
        """Lấy khoá rồi giữ tới khi được báo dừng; thoát bất thường cũng tính là mất khoá (fail-closed)."""
        try:
            token = self._acquire(runner, lock)
            self.token = token
        except (TransientError, AppError) as exc:
            self.error = exc
            return
        finally:
            self.ready.set()
        try:
            self._renew_until_stopped(runner, lock, token)
        finally:
            if not self.stopping.is_set():
                self.lost.set()

    def _acquire(self, runner: asyncio.Runner, lock: SafeLock) -> int:
        """Thử lấy khoá tới `wait_s`; hết giờ → `TransientError` (task thử lại sau)."""
        deadline = time.monotonic() + self._wait_s
        jitter = random.Random()  # noqa: S311 — lệch nhịp chờ cho các worker không tranh cùng lúc
        while True:
            token = runner.run(lock.acquire())
            if token is not None:
                return token
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TransientError(f"GPU đang bận quá {self._wait_s} giây")
            pause = ACQUIRE_EVERY_S * jitter.uniform(1 - ACQUIRE_JITTER, 1 + ACQUIRE_JITTER)
            time.sleep(min(remaining, pause))

    def _renew_until_stopped(self, runner: asyncio.Runner, lock: SafeLock, token: int) -> None:
        """Gia hạn mỗi `renew_every_ms`; mất khoá thì bật `lost` và thôi gia hạn; dừng thì trả khoá.

        Trả bằng `SafeLock.release_quietly` (một nguồn, NO-074): Redis hỏng lúc trả chỉ ghi
        `WARNING`, không che lỗi của thân khối; khoá không trả được thì TTL dọn hộ.
        """
        grace_s = (self._ttl_ms - self._renew_every_ms) / 1000
        last_ok = time.monotonic()
        while not self.stopping.wait(self._renew_every_ms / 1000):
            try:
                renewed: bool | None = runner.run(lock.renew(token))
            except AppError as exc:
                if not _dependency_error(exc):
                    raise
                renewed = None
            if renewed:
                last_ok = time.monotonic()
            elif renewed is False or time.monotonic() - last_ok > grace_s:
                self.lost.set()
                _log.warning("gpu_lock_lost", extra={"lock": GPU_LOCK_NAME, "token": token})
                return
        runner.run(lock.release_quietly(token))


async def _client() -> AsyncRedis:
    """Client DB an toàn dựng **trong** vòng sự kiện của luồng giữ khoá."""
    return safe_redis()


@contextmanager
def gpu_slot(*, wait_s: float, ttl_ms: int = 60_000, renew_every_ms: int = 20_000) -> Iterator[GpuSlot]:
    """Giữ `gpu:0` suốt khối `with` (dùng khi thiết bị là `cuda`).

    Chờ tới `wait_s` → `TransientError`; Redis hỏng lúc lấy → `AppError` 503 (thử lại).
    `renew_every_ms x 2 ≥ ttl_ms` → `ValueError`: phải kịp gia hạn ít nhất hai lần mỗi TTL.
    Thoát khối: dừng luồng, trả khoá, `join` tối đa `JOIN_TIMEOUT_S`.
    """
    if renew_every_ms <= 0 or renew_every_ms * 2 >= ttl_ms:
        raise ValueError(f"cần 0 < renew_every_ms x 2 < ttl_ms, nhận {renew_every_ms} và {ttl_ms}")
    keeper = _Keeper(wait_s=wait_s, ttl_ms=ttl_ms, renew_every_ms=renew_every_ms)
    keeper.start()
    keeper.ready.wait()
    if keeper.token is None:
        keeper.join(JOIN_TIMEOUT_S)
        raise keeper.error or RuntimeError("luồng khoá GPU dừng trước khi lấy được khoá")
    try:
        yield GpuSlot(token=keeper.token, lost=keeper.lost)
    finally:
        keeper.stopping.set()
        keeper.join(JOIN_TIMEOUT_S)
