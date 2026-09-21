"""Giới hạn tốc độ cửa sổ cố định trên Redis (BE-00 §11, C11).

Một `INCR` + `EXPIRE` chạy nguyên khối trong Lua: hai lệnh rời nhau có thể để lại
khoá **không TTL** khi tiến trình chết giữa chừng, tức khoá người dùng vĩnh viễn.

Hai kho tách nhau có chủ đích (BE-00 §1): bộ đếm đăng nhập đặt ở `safe`
(`redis-broker`, `noeviction`) vì `redis-cache` chạy `allkeys-lru` và sẽ **đuổi**
đúng khoá đang chặn kẻ dò mật khẩu khi bộ nhớ đầy.

`limit` và `window_s` cố định lúc khai route, không đọc từ request: C11 dựng bằng
chính hạn mức thật (gửi `limit` lượt rồi thêm một lượt).
"""

import ipaddress
import logging
from collections.abc import Awaitable, Callable
from typing import Any, Final, Literal, cast

from redis.commands.core import AsyncScript
from starlette.requests import Request

from apps.api.core.auth import Principal
from packages.core.error_codes import RATE_LIMITED
from packages.messaging.redis import AsyncRedis, translate_redis_error

_log: Final = logging.getLogger(__name__)

MAX_RETRY_AFTER_S: Final = 10
"""W9: FE tự thử lại trong 15 s, nên `Retry-After` của hạn mức luôn bị kẹp ≤ 10 s."""

IPV6_PREFIX: Final = 64
"""Một khách hàng IPv6 thường được cấp cả /64, nên đếm theo /64 chứ không theo địa chỉ."""

UNKNOWN_IP: Final = "unknown"
STATE_ATTR: Final = "rate_limit_scripts"

type Store = Literal["cache", "safe"]
type OnError = Literal["open", "closed"]
type KeyFn = Callable[[Request], Awaitable[str]]

# KEYS[1] = khoá bộ đếm · ARGV[1] = độ dài cửa sổ (giây).
# Trả (số lượt trong cửa sổ, TTL còn lại) — TTL đọc trong cùng lượt để không phải
# thêm một vòng mạng chỉ để dựng `Retry-After`.
_FIXED_WINDOW: Final = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return {count, redis.call('TTL', KEYS[1])}
"""


def install(app: Any, *, cache: AsyncRedis, safe: AsyncRedis) -> None:
    """Nạp script cho hai kho và gắn vào `app.state` (gọi trong `lifespan`)."""
    scripts = {"cache": cache.register_script(_FIXED_WINDOW), "safe": safe.register_script(_FIXED_WINDOW)}
    setattr(app.state, STATE_ATTR, scripts)


def _script(request: Request, store: Store) -> AsyncScript:
    """Script đã nạp cho kho `store`; quên `install` trong `lifespan` là lỗi lập trình."""
    scripts = getattr(request.app.state, STATE_ATTR, None)
    if not isinstance(scripts, dict) or store not in scripts:
        raise RuntimeError(f"kho rate limit {store!r} chưa được nạp trong lifespan")
    return cast("AsyncScript", scripts[store])


def ip_bucket(host: str) -> str:
    """IPv4 giữ nguyên; IPv6 gom về /64. Chuỗi không phải IP giữ nguyên."""
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return host
    if address.version == 4:
        return str(address)
    network = ipaddress.ip_network(f"{address}/{IPV6_PREFIX}", strict=False)
    return f"{network.network_address}/{IPV6_PREFIX}"


async def key_ip(request: Request) -> str:
    """Khoá theo IP người gọi (IP thật lấy từ `--forwarded-allow-ips`, BE-00 §11)."""
    client = request.client
    return ip_bucket(client.host) if client is not None else UNKNOWN_IP


async def key_user(request: Request) -> str:
    """Khoá theo người dùng đã xác thực; route công khai không dùng được hàm này."""
    principal = getattr(request.state, "principal", None)
    return principal.user_id if isinstance(principal, Principal) else UNKNOWN_IP


def retry_after(ttl_s: int) -> int:
    """`Retry-After` của hạn mức: `max(1, min(ttl, 10))` (BE-00 §11, W9)."""
    return max(1, min(ttl_s, MAX_RETRY_AFTER_S))


def rate_limit(
    name: str,
    *,
    limit: int,
    window_s: int,
    key: KeyFn,
    store: Store,
    on_error: OnError,
) -> Callable[[Request], Awaitable[None]]:
    """Dependency chặn khi vượt `limit` lượt trong `window_s` giây.

    `key` chạy **trước** khi Pydantic kiểm thân, nên nó không được ném: thân hỏng
    vẫn phải tính vào hạn mức, nếu không kẻ dò chỉ cần gửi thân rác để thoát đếm.
    """
    if limit < 1 or window_s < 1:
        raise ValueError(f"limit và window_s phải ≥ 1, nhận {limit}, {window_s}")

    async def dependency(request: Request) -> None:
        """Đếm một lượt; vượt hạn mức → 429, Redis hỏng → theo `on_error`."""
        bucket = await key(request)
        try:
            count, ttl = await _call(request, store, f"rl:{name}:{bucket}", window_s)
        except Exception as exc:  # phân loại ngay dưới: lỗi lệnh được ném lại nguyên trạng
            app_error = translate_redis_error(exc)
            if app_error is None:
                raise
            if on_error == "closed":
                raise app_error from exc
            _log.warning("rate_limit_open", extra={"limit_name": name, "error": repr(exc)})
            return
        # TTL âm = khoá không còn hạn (vừa hết giữa INCR và TTL): coi như không khoá.
        if count > limit and ttl >= 0:
            raise RATE_LIMITED.error(retry_after=retry_after(ttl))

    return dependency


async def _call(request: Request, store: Store, redis_key: str, window_s: int) -> tuple[int, int]:
    """Một lượt đếm; tách ra để thân `dependency` chỉ còn phần phân loại lỗi."""
    raw = await _script(request, store)(keys=[redis_key], args=[window_s])
    count, ttl = raw
    return int(count), int(ttl)
