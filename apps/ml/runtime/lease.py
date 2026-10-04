"""Lõi giữ chỗ theo tên khoá trên Redis, **đồng bộ**, dùng chung cho `gpu_slot` và `training_slot` (NO-308).

Một thuật toán, hai lớp vỏ: lấy khoá (thử lại mỗi 1 s ± 20 % tới `wait_s`), một luồng daemon
gia hạn mỗi `renew_every_ms`, cờ `lost` bật khi gia hạn bị từ chối hay Redis hỏng lâu hơn
`ttl_ms - renew_every_ms` (khoá có thể đã hết hạn và người khác đã lấy — fail-closed), thoát
khối thì dừng luồng rồi trả khoá nếu còn của mình. Phép lấy/gia hạn/trả thuộc lớp vỏ
(`LeaseOps`): `gpu_slot` đi qua `SafeLock` (token rào, `lock:gpu:0`), `training_slot` qua khoá
thô `training:slot` — tên khoá Redis của mỗi bên giữ nguyên.
"""

import logging
import random
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Final, Protocol

from packages.messaging.tasks import TransientError

_log: Final = logging.getLogger(__name__)

ACQUIRE_EVERY_S: Final = 1.0
ACQUIRE_JITTER: Final = 0.2
JOIN_TIMEOUT_S: Final = 5.0
"""Trần `join` mọi luồng nền của `apps/ml` lúc dọn (gia hạn, canh, nhịp tim) — một nguồn (NO-314)."""

__all__ = [
    "ACQUIRE_EVERY_S",
    "ACQUIRE_JITTER",
    "JOIN_TIMEOUT_S",
    "Lease",
    "LeaseOps",
    "RenewThread",
    "check_timing",
    "held_lease",
]


class LeaseOps[T](Protocol):
    """Ba phép Redis của một khoá có tên; `T` là token của lượt (rào `int`, hay chuỗi hex)."""

    @property
    def name(self) -> str:
        """Tên khoá cho log và thông báo lỗi."""
        ...

    def try_acquire(self) -> T | None:
        """Một lượt `SET NX PX`: token khi lấy được, `None` khi người khác đang giữ; Redis hỏng thì ném."""
        ...

    def renew(self, token: T) -> bool | None:
        """Gia hạn nếu khoá còn của `token`: `True`/`False`; `None` khi Redis tạm hỏng (thử lượt sau)."""
        ...

    def release_quietly(self, token: T) -> None:
        """Trả khoá nếu còn của `token`; Redis hỏng chỉ ghi `WARNING` (TTL dọn hộ), không che lỗi thân khối."""
        ...


@dataclass(frozen=True, slots=True)
class Lease[T]:
    """Lượt đang giữ: token và cờ mất khoá (bật bởi luồng gia hạn)."""

    token: T
    lost: threading.Event


class RenewThread(threading.Thread):
    """Luồng daemon gọi `step()` mỗi `interval_s` tới khi được báo dừng hay `step()` trả `False`.

    `step()` trả `True` còn giữ, `False` mất hẳn (bật `lost`, thôi gia hạn), `None` lỗi nhất thời.
    Luồng chết vì lỗi lạ khi chưa được báo dừng cũng bật `lost` (fail-closed).
    """

    def __init__(self, *, interval_s: float, step: Callable[[], bool | None], lost: threading.Event) -> None:
        """Daemon: tiến trình tắt giữa chừng không bị luồng này chặn (TTL dọn khoá hộ)."""
        super().__init__(name="lease-renew", daemon=True)
        self.stopping = threading.Event()
        self.lost = lost
        self._interval_s = interval_s
        self._step = step

    def run(self) -> None:
        """Gia hạn định kỳ; `False` hay ngoại lệ (khi chưa dừng) → bật `lost` và thôi hẳn."""
        try:
            while not self.stopping.wait(self._interval_s):
                if self._step() is False:
                    self.lost.set()
                    return
        finally:
            if not self.stopping.is_set():
                self.lost.set()

    def stop(self) -> None:
        """Báo dừng rồi `join` tối đa `JOIN_TIMEOUT_S` (gọi trong `finally`)."""
        self.stopping.set()
        if self.is_alive():
            self.join(JOIN_TIMEOUT_S)


def check_timing(*, ttl_ms: int, renew_every_ms: int) -> None:
    """`ValueError` khi `renew_every_ms ≤ 0` hay `renew_every_ms x 2 ≥ ttl_ms` (phải kịp gia hạn hai lần mỗi TTL)."""
    if renew_every_ms <= 0 or renew_every_ms * 2 >= ttl_ms:
        raise ValueError(f"cần 0 < renew_every_ms x 2 < ttl_ms, nhận {renew_every_ms} và {ttl_ms}")


def _acquire[T](ops: LeaseOps[T], wait_s: float) -> T:
    """Thử `ops.try_acquire` tới `wait_s`, nhịp 1 s ± 20 %; hết giờ → `TransientError` (task thử lại sau)."""
    deadline = time.monotonic() + wait_s
    jitter = random.Random()  # noqa: S311 — lệch nhịp chờ cho các tiến trình tranh cùng khoá, không phải mật mã
    while True:
        token = ops.try_acquire()
        if token is not None:
            return token
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TransientError(f"khoá {ops.name} đang bận quá {wait_s} giây")
        pause = ACQUIRE_EVERY_S * jitter.uniform(1 - ACQUIRE_JITTER, 1 + ACQUIRE_JITTER)
        time.sleep(min(remaining, pause))


@contextmanager
def held_lease[T](ops: LeaseOps[T], *, wait_s: float, ttl_ms: int, renew_every_ms: int) -> Iterator[Lease[T]]:
    """Giữ khoá của `ops` suốt khối `with`, tự gia hạn; `lost` bật khi mất khoá.

    Thời gian sai → `ValueError` (`check_timing`). Chờ khoá tới `wait_s` → `TransientError`;
    Redis hỏng lúc lấy nổi lên nguyên dạng.
    """
    check_timing(ttl_ms=ttl_ms, renew_every_ms=renew_every_ms)
    token = _acquire(ops, wait_s)
    lost = threading.Event()
    grace_s = (ttl_ms - renew_every_ms) / 1000
    last_ok = time.monotonic()

    def step() -> bool | None:
        """Một nhịp gia hạn: `False` khi bị từ chối, hay Redis hỏng liên tục quá `grace_s`."""
        nonlocal last_ok
        renewed = ops.renew(token)
        if renewed:
            last_ok = time.monotonic()
            return True
        if renewed is False or time.monotonic() - last_ok > grace_s:
            reason = "redis_down" if renewed is None else "renew_rejected"
            _log.warning("lease_lost", extra={"lock": ops.name, "reason": reason})
            return False
        return None

    thread = RenewThread(interval_s=renew_every_ms / 1000, step=step, lost=lost)
    thread.start()
    try:
        yield Lease(token=token, lost=lost)
    finally:
        thread.stop()
        ops.release_quietly(token)
