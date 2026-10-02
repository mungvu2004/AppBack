"""Khoá "một job mỗi lúc" (`training:slot`) và lease claim của job (B6-03b [2], [6]).

Tiến trình con huấn luyện không có vòng sự kiện: cả hai khối `with` đây dùng Redis
**đồng bộ** (`training_redis`) và một luồng daemon riêng để gia hạn định kỳ, khác
`gpu_slot` (`apps/ml/runtime/gpu.py`) chạy `asyncio.Runner` trong luồng của nó vì
`SafeLock` là async. Luồng gia hạn (`_RenewThread`) dùng chung cho cả hai khối: mỗi
nhịp gọi một hàm `step()` do nơi gọi khép kín, trả `True` còn giữ, `False` mất hẳn
(dừng gia hạn ngay), `None` lỗi nhất thời (thử lượt sau).
"""

import logging
import random
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Final

import redis

from apps.ml.training_runner.errors import TRAINING_SLOT_LOST
from apps.ml.training_runner.keys import SLOT_KEY, claim_key, new_token
from apps.ml.training_runner.redis_sync import delete_if_owner, renew_if_owner, training_redis
from apps.ml.training_runner.watchdog import JOIN_TIMEOUT_S
from packages.messaging.redis import SyncRedis, sync_result
from packages.messaging.tasks import PermanentError, TransientError

_log: Final = logging.getLogger(__name__)

ACQUIRE_EVERY_S: Final = 1.0
ACQUIRE_JITTER: Final = 0.2

__all__ = ["ClaimLease", "TrainingSlot", "claim_lease", "training_slot"]


@dataclass(frozen=True, slots=True)
class TrainingSlot:
    """Chỗ huấn luyện đang giữ: token của lượt và cờ mất khoá (bật bởi luồng gia hạn)."""

    token: str
    lost: threading.Event

    def check(self) -> None:
        """Gọi giữa các bước: khoá đã mất → `PermanentError(TRAINING_SLOT_LOST)`."""
        if self.lost.is_set():
            raise PermanentError(TRAINING_SLOT_LOST)


@dataclass(frozen=True, slots=True)
class ClaimLease:
    """Lease "job này thuộc token này" đang giữ; `lost` bật khi token khác đã chiếm claim."""

    token: str
    lost: threading.Event


class _RenewThread(threading.Thread):
    """Luồng daemon gọi `step()` mỗi `interval_s` tới khi được báo dừng hay `step()` trả `False`."""

    def __init__(self, *, interval_s: float, step: Callable[[], bool | None], lost: threading.Event) -> None:
        """Daemon: tiến trình tắt giữa chừng không bị luồng này chặn (TTL dọn khoá hộ)."""
        super().__init__(name="training-renew", daemon=True)
        self.stopping = threading.Event()
        self.lost = lost
        self._interval_s = interval_s
        self._step = step

    def run(self) -> None:
        """Gia hạn định kỳ; `step()` trả `False` thì bật `lost` và thôi hẳn (không gọi lại)."""
        while not self.stopping.wait(self._interval_s):
            if self._step() is False:
                self.lost.set()
                return


def _delete_quietly(client: SyncRedis, key: str, token: str) -> None:
    """`delete_if_owner` mà nuốt `redis.RedisError`: TTL dọn khoá hộ nếu lượt trả thất bại.

    Một nguồn (như `SafeLock.release_quietly`, NO-074): Redis hỏng lúc trả chỉ ghi
    `WARNING`, không che lỗi thật của thân khối `with` đang lan ra.
    """
    try:
        delete_if_owner(client, key, token)
    except redis.RedisError:
        _log.warning("training_lock_release_failed", extra={"key": key})


def _try_acquire(client: SyncRedis, key: str, token: str, ttl_ms: int) -> bool:
    """Một lượt `SET key token NX PX ttl_ms`; `True` nếu lấy được."""
    return sync_result(client.set(key, token, nx=True, px=ttl_ms), bool)


def _acquire(client: SyncRedis, key: str, token: str, ttl_ms: int, wait_s: float) -> None:
    """Thử `_try_acquire` tới `wait_s`, nhịp 1 s ± 20 %; hết giờ → `TransientError`.

    Redis lỗi lúc lấy nổi lên nguyên dạng (không bắt ở đây): runner coi là lỗi của lượt.
    """
    deadline = time.monotonic() + wait_s
    jitter = random.Random()  # noqa: S311 — lệch nhịp chờ giữa các job tranh cùng khoá, không phải mật mã
    while True:
        if _try_acquire(client, key, token, ttl_ms):
            return
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TransientError(f"khoá {key} đang bận quá {wait_s} giây")
        pause = ACQUIRE_EVERY_S * jitter.uniform(1 - ACQUIRE_JITTER, 1 + ACQUIRE_JITTER)
        time.sleep(min(remaining, pause))


@contextmanager
def training_slot(*, wait_s: float, ttl_ms: int = 60_000, renew_every_ms: int = 20_000) -> Iterator[TrainingSlot]:
    """Giữ `SLOT_KEY` suốt khối `with` — một job huấn luyện mỗi lúc trên mọi thiết bị (BE-00 §7, §9).

    Hợp đồng như `gpu_slot`: `renew_every_ms x 2 >= ttl_ms` → `ValueError`; chờ khoá tới
    `wait_s` → `TransientError`. Gia hạn `False`, hay Redis hỏng liên tục quá
    `ttl_ms - renew_every_ms` (khoá có thể đã hết hạn và người khác giành mất) → bật `lost`
    (fail-closed). Thoát khối: dừng luồng gia hạn, `join` tối đa `JOIN_TIMEOUT_S`, xoá khoá
    nếu còn của mình, rồi đóng client tự dựng.
    """
    if renew_every_ms <= 0 or renew_every_ms * 2 >= ttl_ms:
        raise ValueError(f"cần 0 < renew_every_ms x 2 < ttl_ms, nhận {renew_every_ms} và {ttl_ms}")
    client = training_redis()
    try:
        token = new_token()
        _acquire(client, SLOT_KEY, token, ttl_ms, wait_s)
        lost = threading.Event()
        grace_s = (ttl_ms - renew_every_ms) / 1000
        last_ok = time.monotonic()

        def step() -> bool | None:
            """Một nhịp gia hạn `SLOT_KEY`: `False` khi mất hẳn (fail-closed quá `grace_s`)."""
            nonlocal last_ok
            try:
                renewed = renew_if_owner(client, SLOT_KEY, token, ttl_ms)
            except redis.RedisError:
                if time.monotonic() - last_ok > grace_s:
                    _log.warning("training_slot_lost", extra={"reason": "redis_down"})
                    return False
                return None
            if renewed:
                last_ok = time.monotonic()
                return True
            _log.warning("training_slot_lost", extra={"reason": "renew_rejected"})
            return False

        thread = _RenewThread(interval_s=renew_every_ms / 1000, step=step, lost=lost)
        thread.start()
        try:
            yield TrainingSlot(token=token, lost=lost)
        finally:
            thread.stopping.set()
            thread.join(JOIN_TIMEOUT_S)
            _delete_quietly(client, SLOT_KEY, token)
    finally:
        client.close()


def _claim_step(client: SyncRedis, key: str, token: str, ttl_ms: int, job_id: str) -> bool | None:
    """Gia hạn `key` nếu còn của `token`; mất thì giành lại bằng `SET NX`; `WARNING` khi mất hẳn."""
    try:
        if renew_if_owner(client, key, token, ttl_ms):
            return True
        if _try_acquire(client, key, token, ttl_ms):
            return True
    except redis.RedisError:
        _log.warning("training_claim_redis_error", extra={"job_id": job_id})
        return None
    _log.warning("training_claim_lost", extra={"job_id": job_id})
    return False


@contextmanager
def claim_lease(client: SyncRedis, job_id: str, token: str, *, ttl_ms: int) -> Iterator[ClaimLease]:
    """Giữ `claim_key(job_id)` suốt khối `with` ("job này thuộc token này", BE-00 §9).

    Giành claim ngay lúc vào khối (đồng bộ) rồi gia hạn mỗi `ttl_ms / 4`; khoá bị xoá giữa
    chừng → giành lại bằng `SET NX` cùng token (`lost` không bật); token khác đã chiếm →
    bật `lost`, log `WARNING` `training_claim_lost`, thôi gia hạn. Redis lỗi → `WARNING`,
    thử lượt sau (không bật `lost`). Thoát: dừng luồng, `join`, `delete_if_owner` (không
    bao giờ xoá claim của token khác) — client **không** đóng, thuộc về người gọi.
    """
    key = claim_key(job_id)
    lost = threading.Event()

    def step() -> bool | None:
        """Một nhịp gia hạn/giành lại `claim_key(job_id)`; uỷ `_claim_step` (dùng lại cho test vá)."""
        return _claim_step(client, key, token, ttl_ms, job_id)

    first = step()
    if first is False:
        lost.set()
    thread = _RenewThread(interval_s=ttl_ms / 4000, step=step, lost=lost)
    if first is not False:
        thread.start()
    try:
        yield ClaimLease(token=token, lost=lost)
    finally:
        thread.stopping.set()
        if thread.is_alive():
            thread.join(JOIN_TIMEOUT_S)
        _delete_quietly(client, key, token)
