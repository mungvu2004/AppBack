"""Giữ chỗ kết nối SSE trên `redis-cache` thật (B4-01 [6] "Giữ chỗ"; K23 cấm mock Redis)."""

from collections.abc import AsyncIterator
from typing import Final

import pytest_asyncio
from redis.asyncio import Redis

from apps.api.streams.connections import conn_key, refresh, release, reserve
from packages.messaging.redis import AsyncRedis

USER: Final = "usr_01ARZ3NDEKTSV4RRFFQ69G5FAV"
NOW_MS: Final = 1_767_225_600_000
"""2026-01-01T00:00:00Z tính bằng mili giây — cùng mốc với `fake_clock`."""

TTL_MS: Final = 30_000
LIMIT: Final = 6
DEAD_PORT: Final = 1
"""Cổng không ai nghe: dựng "redis-cache hỏng" bằng máy chủ thật vắng mặt, không mock (K23)."""


@pytest_asyncio.fixture(loop_scope="function")
async def dead_cache() -> AsyncIterator[AsyncRedis]:
    """Client trỏ vào một cổng chết, trần nối 0,2 s để test không chờ lâu."""
    client: AsyncRedis = Redis.from_url(
        f"redis://127.0.0.1:{DEAD_PORT}/0", decode_responses=True, socket_connect_timeout=0.2, socket_timeout=0.2
    )
    try:
        yield client
    finally:
        await client.aclose()


async def _reserve(cache: AsyncRedis, conn_id: str, *, now_ms: int = NOW_MS) -> bool:
    """Một lượt giữ chỗ với tham số mặc định của test."""
    return await reserve(cache, USER, conn_id, now_ms=now_ms, ttl_ms=TTL_MS, limit=LIMIT)


async def test_reserve_admits_up_to_the_limit(cache_client: AsyncRedis) -> None:
    """Sáu kết nối cùng người đều vào được (`STREAM_MAX_PER_USER` mặc định)."""
    for index in range(LIMIT):
        assert await _reserve(cache_client, f"c{index}") is True
    assert await cache_client.zcard(conn_key(USER)) == LIMIT


async def test_reserve_rejects_the_seventh_without_leaving_a_member(cache_client: AsyncRedis) -> None:
    """Cái thứ bảy bị từ chối **và** tự `ZREM`: không để lại chỗ ma cho lượt sau."""
    for index in range(LIMIT):
        assert await _reserve(cache_client, f"c{index}") is True
    assert await _reserve(cache_client, "c6") is False
    assert await cache_client.zcard(conn_key(USER)) == LIMIT
    assert await cache_client.zscore(conn_key(USER), "c6") is None


async def test_release_frees_a_slot(cache_client: AsyncRedis) -> None:
    """Đóng một luồng rồi mở lại được ngay (S05)."""
    for index in range(LIMIT):
        assert await _reserve(cache_client, f"c{index}") is True
    await release(cache_client, USER, "c0")
    assert await _reserve(cache_client, "c6") is True
    assert await cache_client.zcard(conn_key(USER)) == LIMIT


async def test_reserve_drops_expired_members(cache_client: AsyncRedis) -> None:
    """Mục của tiến trình đã chết (score quá hạn) bị dọn ở lượt giữ chỗ kế tiếp."""
    for index in range(LIMIT):
        assert await _reserve(cache_client, f"c{index}") is True
    later = NOW_MS + TTL_MS + 1
    assert await _reserve(cache_client, "c6", now_ms=later) is True
    assert await cache_client.zcard(conn_key(USER)) == 1


async def test_refresh_extends_the_deadline_and_the_key(cache_client: AsyncRedis) -> None:
    """Gia hạn dời cả score của mục lẫn TTL của khoá — luồng bận không tự rụng."""
    assert await _reserve(cache_client, "c0") is True
    await refresh(cache_client, USER, "c0", now_ms=NOW_MS + TTL_MS, ttl_ms=TTL_MS)
    assert await cache_client.zscore(conn_key(USER), "c0") == NOW_MS + 2 * TTL_MS
    assert 0 < await cache_client.ttl(conn_key(USER)) <= TTL_MS // 1000


async def test_reserve_fails_open_when_cache_is_down(dead_cache: AsyncRedis) -> None:
    """`redis-cache` chết → cho qua (mở): hạn mức là chống lạm dụng, không phải hàng rào quyền."""
    assert await _reserve(dead_cache, "c0") is True


async def test_refresh_and_release_survive_a_dead_cache(dead_cache: AsyncRedis) -> None:
    """Gia hạn và trả chỗ cũng nuốt lỗi phụ thuộc: `finally` của luồng không được ném."""
    await refresh(dead_cache, USER, "c0", now_ms=NOW_MS, ttl_ms=TTL_MS)
    await release(dead_cache, USER, "c0")
