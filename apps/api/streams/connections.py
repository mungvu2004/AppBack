"""Giữ chỗ kết nối SSE theo người dùng (B4-01 [5], [6] "Giữ chỗ").

ZSET `streams:conn:{user_id}` ở `redis-cache`: member là id kết nối, score là **hạn**
(mili giây). Dùng ZSET chứ không phải bộ đếm vì một tiến trình API bị giết không kịp
`ZREM` — mục của nó tự rụng ở lượt `ZREMRANGEBYSCORE` kế tiếp, còn bộ đếm thì kẹt cao
mãi mãi. Khoá mang TTL 2 lần heartbeat để người dùng im lặng không để lại rác.

`redis-cache` được phép bị đuổi khoá và được phép chết (BE-00 §11), nên mọi lời gọi ở
đây **fail-open**: hạn mức kết nối là chống lạm dụng, không phải hàng rào an toàn — mất
Redis cache không được biến thành "không ai mở được luồng". Quyền thật nằm ở
`check_session` + `StreamAccessPolicy`.
"""

import math
from typing import Final

from apps.api.auth.services import soft_redis
from packages.messaging.redis import AsyncRedis

KEY_PREFIX: Final = "streams:conn:"
CACHE_UNAVAILABLE: Final = "stream_conn_cache_unavailable"
"""Tên sự kiện log khi `redis-cache` hỏng — không kèm token, cookie hay id kết nối (K11)."""


def conn_key(user_id: str) -> str:
    """Khoá ZSET giữ chỗ của một người dùng."""
    return f"{KEY_PREFIX}{user_id}"


async def reserve(cache: AsyncRedis, user_id: str, conn_id: str, *, now_ms: int, ttl_ms: int, limit: int) -> bool:
    """Giữ một chỗ; `False` = đã chạm `STREAM_MAX_PER_USER` (người gọi trả 429).

    Một vòng Redis cho cả bốn lệnh: dọn mục hết hạn → thêm mình → đếm → gia hạn khoá.
    Đếm **sau** khi thêm mình nên trần so với `limit` chứ không `limit - 1`; vượt thì tự
    `ZREM` để lượt thử của người khác không thấy chỗ ma.
    """
    key = conn_key(user_id)
    ttl_s = max(1, math.ceil(ttl_ms / 1000))
    async with cache.pipeline(transaction=True) as pipe:
        pipe.zremrangebyscore(key, 0, now_ms)
        pipe.zadd(key, {conn_id: now_ms + ttl_ms})
        pipe.zcard(key)
        pipe.expire(key, ttl_s)
        result = await soft_redis(pipe.execute(), CACHE_UNAVAILABLE)
    if result is None:
        return True  # cache hỏng → cho qua (mở), đã log ở `soft_redis`
    if int(result[2]) <= limit:
        return True
    await release(cache, user_id, conn_id)
    return False


async def refresh(cache: AsyncRedis, user_id: str, conn_id: str, *, now_ms: int, ttl_ms: int) -> None:
    """Dời hạn của chỗ đang giữ và của cả khoá — luồng bận không bao giờ tự rụng."""
    key = conn_key(user_id)
    async with cache.pipeline(transaction=True) as pipe:
        pipe.zadd(key, {conn_id: now_ms + ttl_ms})
        pipe.expire(key, max(1, math.ceil(ttl_ms / 1000)))
        await soft_redis(pipe.execute(), CACHE_UNAVAILABLE)


async def release(cache: AsyncRedis, user_id: str, conn_id: str) -> None:
    """Trả chỗ. Chạy trong `finally` của luồng, kể cả khi client rớt (S05)."""
    await soft_redis(cache.zrem(conn_key(user_id), conn_id), CACHE_UNAVAILABLE)
