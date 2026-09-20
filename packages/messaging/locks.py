"""Khoá phân tán có token rào, trên DB Redis trạng thái an toàn (BE-00 §7, §9).

Khoá chỉ có TTL là chưa đủ: chủ cũ bị treo quá TTL vẫn tin mình đang giữ khoá và
vẫn ghi. Vì vậy mỗi lượt lấy khoá nhận một **token rào** tăng đơn điệu (`INCR`);
người ghi xuống tài nguyên chung so token và bỏ qua lượt ghi của token cũ hơn.

`renew` và `release` so giá trị bằng Lua rồi mới `PEXPIRE`/`DEL`, nên chủ cũ hết
hạn không bao giờ gia hạn hay xoá khoá của chủ mới.
"""

import asyncio
import logging
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from typing import Final

from packages.messaging.redis import AsyncRedis, redis_errors

_log: Final = logging.getLogger(__name__)

# Bộ đếm rào là khoá Redis duy nhất **không** TTL (BE-00 §5 của prompt B0-05): nó
# chỉ tăng, mất nó là mất tính đơn điệu của token.
FENCE_SUFFIX: Final = ":fence"
_SECRET_BYTES: Final = 16

# So **đuôi** `:<token>` để `renew`/`release` chỉ cần token, không cần nhớ phần ngẫu nhiên.
_RENEW: Final = """
local v = redis.call('GET', KEYS[1])
if v and string.sub(v, -string.len(ARGV[1])) == ARGV[1] then
  return redis.call('PEXPIRE', KEYS[1], ARGV[2])
end
return 0
"""
_RELEASE: Final = """
local v = redis.call('GET', KEYS[1])
if v and string.sub(v, -string.len(ARGV[1])) == ARGV[1] then
  return redis.call('DEL', KEYS[1])
end
return 0
"""


class LockBusy(Exception):  # noqa: N818 — tên do prompt B0-05 [2] đặt; B1-01/B5-01 sẽ nhập đúng tên này
    """`hold()` không lấy được khoá vì người khác đang giữ."""


class LockLost(Exception):  # noqa: N818 — như trên
    """Khoá đã thuộc về người khác trong lúc thân `hold()` còn chạy."""


class SafeLock:
    """Một khoá có tên, trên một client Redis của DB trạng thái an toàn."""

    def __init__(self, client: AsyncRedis, name: str, ttl_ms: int) -> None:
        if not name:
            raise ValueError("tên khoá không được rỗng")
        if ttl_ms <= 0:
            raise ValueError(f"ttl_ms phải > 0, nhận {ttl_ms}")
        self._client = client
        self._key = f"lock:{name}"
        self._fence_key = f"lock:{name}{FENCE_SUFFIX}"
        self._ttl_ms = ttl_ms
        self._renew_script = client.register_script(_RENEW)
        self._release_script = client.register_script(_RELEASE)

    @property
    def name(self) -> str:
        """Tên khoá như người gọi đặt (không kèm tiền tố `lock:`)."""
        return self._key.removeprefix("lock:")

    async def acquire(self) -> int | None:
        """Trả token rào khi lấy được khoá, `None` khi người khác đang giữ.

        Token được cấp **trước** khi `SET NX`, nên một lượt tranh thua vẫn tiêu một
        số: token chỉ bảo đảm đơn điệu, không bảo đảm liên tục.
        """
        with redis_errors():
            token = int(await self._client.incr(self._fence_key))
            # Phần ngẫu nhiên giữ khoá an toàn cả khi bộ đếm rào bị xoá (FLUSHDB) và
            # cấp lại một token đã dùng.
            value = f"{secrets.token_hex(_SECRET_BYTES)}:{token}"
            acquired = await self._client.set(self._key, value, nx=True, px=self._ttl_ms)
        return token if acquired else None

    async def renew(self, token: int) -> bool:
        """Đẩy hạn khoá thêm một TTL; `False` khi khoá đã mất hoặc đã đổi chủ."""
        with redis_errors():
            return bool(await self._renew_script(keys=[self._key], args=[f":{token}", self._ttl_ms]))

    async def release(self, token: int) -> None:
        """Trả khoá nếu còn là của `token`; khoá của chủ mới không bị đụng tới."""
        with redis_errors():
            await self._release_script(keys=[self._key], args=[f":{token}"])

    @asynccontextmanager
    async def hold(self, renew_every_ms: int) -> AsyncIterator[int]:
        """Giữ khoá suốt thân `async with`, tự gia hạn; mất khoá → `LockLost`.

        Task gia hạn huỷ task đang chạy thân (đúng cách `asyncio.timeout` làm) ngay
        lần kiểm thấy mất khoá, nên việc dài không chạy tiếp dưới khoá của người
        khác. Không lấy được khoá ngay từ đầu → `LockBusy`.
        """
        if not 0 < renew_every_ms < self._ttl_ms:
            raise ValueError(f"renew_every_ms phải trong (0, {self._ttl_ms}), nhận {renew_every_ms}")
        holder = asyncio.current_task()
        if holder is None:
            raise RuntimeError("hold() phải chạy trong một task asyncio")
        token = await self.acquire()
        if token is None:
            raise LockBusy(self.name)
        state = _Renewal(self, token, renew_every_ms, holder)
        keeper = asyncio.create_task(state.run())
        try:
            yield token
        except asyncio.CancelledError:
            if not state.lost:
                raise
            holder.uncancel()
            raise LockLost(self.name) from None
        finally:
            keeper.cancel()
            with suppress(asyncio.CancelledError):
                await keeper
            if not state.lost:
                await self.release(token)


class _Renewal:
    """Vòng gia hạn của một lượt `hold`; giữ cờ `lost` để `hold` phân biệt lý do huỷ."""

    def __init__(self, lock: SafeLock, token: int, every_ms: int, holder: asyncio.Task[object]) -> None:
        self._lock = lock
        self._token = token
        self._every_s = every_ms / 1000
        self._holder = holder
        self.lost = False

    async def run(self) -> None:
        """Gia hạn định kỳ; lần đầu gia hạn không thành thì huỷ task đang giữ khoá rồi dừng."""
        while True:
            await asyncio.sleep(self._every_s)
            if not await self._renewed():
                self.lost = True
                self._holder.cancel()
                return

    async def _renewed(self) -> bool:
        """Gia hạn **fail-closed**: mọi lỗi cũng tính là mất khoá.

        Để ngoại lệ thoát khỏi `run()` thì task gia hạn chết im lặng, `lost` vẫn `False`,
        và thân `hold()` chạy tiếp dưới một khoá sắp hết hạn — đúng thứ token rào sinh ra
        để chống. `CancelledError` là `BaseException` nên không bị bắt ở đây: lúc `hold`
        dọn dẹp, huỷ vẫn là huỷ.
        """
        try:
            return await self._lock.renew(self._token)
        except Exception as exc:  # noqa: BLE001 — Redis hỏng cũng là mất khoá; ghi log rồi nhường
            _log.warning("lock_renew_failed", extra={"lock": self._lock.name, "error": repr(exc)})
            return False
