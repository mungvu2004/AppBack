"""Khoá đăng nhập theo (email, IP) và hạn mức mềm theo email (BE-00 §11, C27).

Mọi khoá nằm ở **DB an toàn** (`redis-broker`, `noeviction`): trên `redis-cache` chúng bị
đuổi đúng lúc bộ nhớ đầy — lúc kẻ dò đang bơm request. Khoá chứa `email_key` (HMAC), không
bao giờ email thô (K11). Với `k = email_key(email)`:

- `auth:login:fail:{k}:{ip}` — mọi lượt thử tính từ lần đúng gần nhất, tăng **trước khi
  băm**, sống `LOGIN_FAILURE_WINDOW_S` (900 s) từ lượt đầu. Vượt `LOGIN_FAILURE_LIMIT` →
  đặt `lock` và 429; **mỗi lượt sau đó** lại khoá, cho tới khi bộ đếm hết hạn (BE-00 §11:
  "bộ đếm sai sống 900 s, mỗi lượt sau lần sai thứ 5 lại khoá");
- `auth:login:lock:{k}:{ip}` — còn là 429, sống `LOGIN_LOCK_S`;
- `auth:login:emailfail:{k}` — chỉ đếm lần **sai**; chạm `LOGIN_EMAIL_FAILURE_LIMIT` thì
  chỉ IP có `auth:login:known:{k}:{ip}` (từng đăng nhập đúng, sống 30 ngày) được thử.

Chống dò: email lạ và email có thật đi cùng một kịch bản Lua và cùng số lượt Redis —
`admit` không hề biết email có tồn tại không. Lỗi Redis → 503 (`on_error="closed"`).
"""

import logging
from datetime import timedelta
from typing import Final

from apps.api.auth.settings import AuthSettings
from apps.api.core.ratelimit import retry_after
from packages.core.error_codes import RATE_LIMITED
from packages.messaging.redis import AsyncRedis, redis_errors

_log: Final = logging.getLogger(__name__)

KNOWN_TTL: Final = timedelta(days=30)
PASSED: Final = 0
LOCKED: Final = 1
EMAIL_LIMITED: Final = 2
JUST_LOCKED: Final = 3
LOCK_REASONS: Final = {EMAIL_LIMITED: "email_soft_limit", JUST_LOCKED: "email_ip_locked"}

# KEYS: lock, fail, emailfail, known · ARGV: cửa sổ fail, trần fail, giây khoá, trần emailfail.
# Trả {mã, ttl}: 0 = cho thử, 1 = đang khoá, 2 = email chạm hạn mức mềm, 3 = vừa đặt khoá.
# Nguyên khối trong Lua: kiểm `lock` và `INCR` rời nhau thì một loạt request song song đúng
# lúc khoá hết hạn cùng lọt qua trước khi lượt đầu kịp đặt lại khoá.
_ADMIT: Final = """
if redis.call('EXISTS', KEYS[1]) == 1 then return {1, redis.call('TTL', KEYS[1])} end
local fails = redis.call('INCR', KEYS[2])
if fails == 1 then redis.call('EXPIRE', KEYS[2], ARGV[1]) end
if fails > tonumber(ARGV[2]) then
  redis.call('SET', KEYS[1], '1', 'EX', ARGV[3])
  return {3, tonumber(ARGV[3])}
end
local email_fails = tonumber(redis.call('GET', KEYS[3]) or '0')
local known = redis.call('EXISTS', KEYS[4])
if email_fails >= tonumber(ARGV[4]) and known == 0 then return {2, redis.call('TTL', KEYS[3])} end
return {0, 0}
"""


def _fail_key(k: str, ip: str) -> str:
    """Bộ đếm lượt thử của (email, IP)."""
    return f"auth:login:fail:{k}:{ip}"


def _lock_key(k: str, ip: str) -> str:
    """Khoá 429 của (email, IP)."""
    return f"auth:login:lock:{k}:{ip}"


def _email_fail_key(k: str) -> str:
    """Bộ đếm lần sai theo email, mọi IP."""
    return f"auth:login:emailfail:{k}"


def _known_key(k: str, ip: str) -> str:
    """Dấu "IP này từng đăng nhập đúng bằng email này"."""
    return f"auth:login:known:{k}:{ip}"


async def bump(client: AsyncRedis, key: str, ttl_s: int) -> tuple[int, int]:
    """`INCR` + TTL ở lượt đầu, nguyên khối (`MULTI`); trả (giá trị mới, TTL còn lại).

    `EXPIRE … NX` chỉ đặt TTL khi khoá chưa có: cửa sổ cố định tính từ lượt đầu, và bộ đếm
    không bao giờ sống mãi dù tiến trình chết giữa hai lệnh. TTL đọc cùng lượt để dựng
    `Retry-After` không tốn thêm vòng mạng.
    """
    async with client.pipeline(transaction=True) as pipe:
        pipe.incr(key)
        pipe.expire(key, ttl_s, nx=True)
        pipe.ttl(key)
        count, _, ttl = await pipe.execute()
    return int(count), int(ttl)


async def peek(client: AsyncRedis, key: str) -> tuple[int, int]:
    """(giá trị, TTL) của một bộ đếm trong một vòng mạng; vắng khoá → (0, -2)."""
    async with client.pipeline(transaction=False) as pipe:
        pipe.get(key)
        pipe.ttl(key)
        raw, ttl = await pipe.execute()
    return int(raw or 0), int(ttl)


async def admit(client: AsyncRedis, settings: AuthSettings, k: str, ip: str) -> None:
    """Bước 3-4 của đăng nhập, **trước khi băm**: khoá còn, vừa vượt trần, hay email bị chặn → 429."""
    script = client.register_script(_ADMIT)
    keys = [_lock_key(k, ip), _fail_key(k, ip), _email_fail_key(k), _known_key(k, ip)]
    args = [
        settings.login_failure_window_s,
        settings.login_failure_limit,
        settings.login_lock_s,
        settings.login_email_failure_limit,
    ]
    with redis_errors():
        verdict, ttl = await script(keys=keys, args=args)
    if int(verdict) == PASSED:
        return
    if int(verdict) != LOCKED:
        # Dấu hiệu dò mật khẩu cho vận hành: một dòng khi khoá vừa được đặt và mỗi lượt vượt hạn mức
        # mềm theo email (đã bị hạn mức theo IP chặn trần); lượt đập vào khoá đang có thì không log.
        # Chỉ `email_key` (HMAC), không bao giờ email thô (K11).
        _log.warning("login_throttled", extra={"emailKey": k, "reason": LOCK_REASONS[int(verdict)]})
    raise RATE_LIMITED.error(retry_after=retry_after(int(ttl)))


async def record_failure(client: AsyncRedis, settings: AuthSettings, k: str) -> None:
    """Sai mật khẩu (kể cả email lạ, người `pending`): tăng bộ đếm mềm theo email."""
    with redis_errors():
        await bump(client, _email_fail_key(k), settings.login_email_failure_window_s)


async def record_success(client: AsyncRedis, k: str, ip: str) -> None:
    """Đăng nhập đúng: xoá bộ đếm lượt thử, ghi IP này là "đã từng đúng" 30 ngày."""
    with redis_errors():
        async with client.pipeline(transaction=True) as pipe:
            pipe.delete(_fail_key(k, ip))
            pipe.set(_known_key(k, ip), "1", ex=KNOWN_TTL)
            await pipe.execute()
