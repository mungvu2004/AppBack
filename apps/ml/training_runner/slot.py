"""Khoá "một job mỗi lúc" (`training:slot`) và lease claim của job (B6-03b [2], [6]).

Tiến trình con huấn luyện không có vòng sự kiện: cả hai khối `with` đây dùng Redis
**đồng bộ** (`training_redis`). Lấy/gia hạn/`lost`/trả của `training_slot` là lõi chung
`held_lease` của `apps/ml/runtime/lease.py` (cùng lõi với `gpu_slot`, NO-308); ở đây chỉ còn
lớp vỏ `_SlotOps` trên khoá thô `training:slot` (token 32 hex, Lua so token). `claim_lease`
dùng lại `RenewThread` của lõi với nhịp riêng (giành lại claim khi khoá bị xoá).
"""

import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Final

import redis

from apps.ml.runtime.lease import RenewThread, check_timing, held_lease
from apps.ml.training_runner.errors import TRAINING_SLOT_LOST
from apps.ml.training_runner.keys import SLOT_KEY, claim_key, new_token
from apps.ml.training_runner.redis_sync import delete_if_owner, renew_if_owner, training_redis
from packages.messaging.redis import SyncRedis, sync_result
from packages.messaging.tasks import PermanentError

_log: Final = logging.getLogger(__name__)

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


class _SlotOps:
    """`LeaseOps[str]` trên khoá thô `SLOT_KEY`: `SET NX PX` + Lua so token, client đồng bộ của người gọi."""

    name: Final = SLOT_KEY

    def __init__(self, client: SyncRedis, ttl_ms: int) -> None:
        """Giữ client (người gọi đóng) và TTL của khoá."""
        self._client = client
        self._ttl_ms = ttl_ms

    def try_acquire(self) -> str | None:
        """Token mới khi lấy được, `None` khi đang bận; Redis lỗi nổi lên nguyên dạng (lỗi của lượt)."""
        token = new_token()
        return token if _try_acquire(self._client, SLOT_KEY, token, self._ttl_ms) else None

    def renew(self, token: str) -> bool | None:
        """Gia hạn nếu còn của `token`; `redis.RedisError` → `None` (lõi tính hạn fail-closed)."""
        try:
            return renew_if_owner(self._client, SLOT_KEY, token, self._ttl_ms)
        except redis.RedisError:
            return None

    def release_quietly(self, token: str) -> None:
        """Xoá khoá nếu còn của `token`; Redis lỗi chỉ ghi `WARNING`."""
        _delete_quietly(self._client, SLOT_KEY, token)


@contextmanager
def training_slot(*, wait_s: float, ttl_ms: int = 60_000, renew_every_ms: int = 20_000) -> Iterator[TrainingSlot]:
    """Giữ `SLOT_KEY` suốt khối `with` — một job huấn luyện mỗi lúc trên mọi thiết bị (BE-00 §7, §9).

    Hợp đồng như `gpu_slot`: `renew_every_ms x 2 >= ttl_ms` → `ValueError`; chờ khoá tới
    `wait_s` → `TransientError`. Gia hạn `False`, hay Redis hỏng liên tục quá
    `ttl_ms - renew_every_ms` (khoá có thể đã hết hạn và người khác giành mất) → bật `lost`
    (fail-closed). Thoát khối: dừng luồng gia hạn, `join` tối đa `JOIN_TIMEOUT_S`, xoá khoá
    nếu còn của mình, rồi đóng client tự dựng.
    """
    check_timing(ttl_ms=ttl_ms, renew_every_ms=renew_every_ms)
    client = training_redis()
    try:
        with held_lease(_SlotOps(client, ttl_ms), wait_s=wait_s, ttl_ms=ttl_ms, renew_every_ms=renew_every_ms) as lease:
            yield TrainingSlot(token=lease.token, lost=lease.lost)
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
    thử lượt sau (không bật `lost`); lỗi lạ khác làm luồng gia hạn chết và bật `lost`
    (fail-closed, `RenewThread` của lõi). Thoát: dừng luồng, `join`, `delete_if_owner` (không
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
    thread = RenewThread(interval_s=ttl_ms / 4000, step=step, lost=lost)
    if first is not False:
        thread.start()
    try:
        yield ClaimLease(token=token, lost=lost)
    finally:
        thread.stop()
        _delete_quietly(client, key, token)
