"""Client Redis **đồng bộ** của runner và hai lệnh Lua so token (claim, `training:slot`).

Lệch khỏi prompt [6]: không dựng client riêng — `safe_redis_sync` (B0-05) đã là client đồng
bộ tới DB an toàn dựng từ `MessagingSettings`, cùng DB mà B6-03a đặt `cancel_key`. Tiến trình
con không có vòng sự kiện nên không dùng `SafeLock` (async).
"""

from typing import Final

from packages.messaging.redis import SyncRedis, safe_redis_sync, sync_result

__all__ = ["delete_if_owner", "renew_if_owner", "training_redis"]

_RENEW: Final = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('PEXPIRE', KEYS[1], ARGV[2])
end
return 0
"""

_DELETE: Final = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('DEL', KEYS[1])
end
return 0
"""


def training_redis() -> SyncRedis:
    """Client đồng bộ tới DB an toàn (claim, huỷ, `training:slot`); người gọi tự `close()`."""
    return safe_redis_sync()


def renew_if_owner(client: SyncRedis, key: str, token: str, ttl_ms: int) -> bool:
    """Gia hạn `key` thêm `ttl_ms` **chỉ khi** nó còn mang `token`; khoá vắng hay của người khác → `False`."""
    return sync_result(client.eval(_RENEW, 1, key, token, ttl_ms), int) == 1


def delete_if_owner(client: SyncRedis, key: str, token: str) -> bool:
    """Xoá `key` **chỉ khi** nó còn mang `token` (không bao giờ xoá claim/khoá của người khác)."""
    return sync_result(client.eval(_DELETE, 1, key, token), int) == 1
