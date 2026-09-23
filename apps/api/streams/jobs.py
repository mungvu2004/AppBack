"""Lịch dọn stream upload mồ côi (BE-00 §7 "Dọn rác", dòng "stream upload"; B4-01 [6]).

`apps/worker` nhập module này để chạy beat, nên nó chỉ nhập `packages.core` và
`packages.messaging` — không `fastapi`, `starlette`, `jwt`, `argon2` (BE-00 §2.1, K36).

Đường thường là `finalize_upload_stream` (`lifecycle.py`) đặt TTL khi lượt tải vào
trạng thái cuối. Lịch này chỉ vớt phần rơi: tiến trình chết giữa chừng, lượt tải bị bỏ
dở, hay một lỗi làm callback sau commit không chạy — khoá còn `TTL = -1` mãi mãi. Mốc
"cũ" đọc từ **phần mili giây của id cuối**, không từ đồng hồ Redis: id do chính Redis
sinh nên nó là thời điểm sự kiện cuối, không phụ thuộc lệch giờ giữa các máy.

`SCAN` theo lô và gom mỗi lô vào **một** pipeline (R-20): một lượt quét 10 000 khoá đi
hai vòng Redis mỗi lô chứ không hai vòng mỗi khoá.
"""

import logging
from datetime import timedelta
from typing import Final, cast

from packages.core.clock import Clock, SystemClock
from packages.messaging import periodic, streams_redis
from packages.messaging.redis import AsyncRedis

_log: Final = logging.getLogger(__name__)

TASK_NAME: Final = "default.streams.expire_stale_uploads"
EVERY: Final = timedelta(hours=6)

UPLOAD_KEY_PATTERN: Final = "events:upload:*"
"""Mẫu khoá của `packages.messaging.streams.upload_stream` — lịch quét theo mẫu, không theo id."""

STALE_AFTER: Final = timedelta(days=7)
"""Không sự kiện nào trong 7 ngày: lượt tải đã chết, không ai còn nối lại luồng của nó."""

STALE_TTL_S: Final = 3600
"""Cho thêm một giờ thay vì xoá ngay — một luồng đang mở vẫn đọc nốt được."""

SCAN_BATCH: Final = 200
NO_TTL: Final = -1
"""`TTL` của Redis cho khoá **có thật mà không có hạn**; `-2` là khoá không tồn tại."""


def _event_ms(event_id: str) -> int:
    """Phần mili giây của một id Redis Stream `<mili giây>-<thứ tự>`."""
    return int(event_id.partition("-")[0])


async def _scan_batch(client: AsyncRedis, cursor: int, batch: int) -> tuple[int, list[str]]:
    """Một lô `SCAN` khoá stream upload; trả (cursor kế tiếp, khoá của lô)."""
    next_cursor, keys = cast("tuple[int, list[str]]", await client.scan(cursor, match=UPLOAD_KEY_PATTERN, count=batch))
    return int(next_cursor), [str(key) for key in keys]


async def _stale_keys(client: AsyncRedis, keys: list[str], cutoff_ms: int) -> list[str]:
    """Khoá không có hạn **và** id cuối cũ hơn `cutoff_ms`, hỏi cả lô trong một pipeline."""
    async with client.pipeline(transaction=False) as pipe:
        for key in keys:
            pipe.ttl(key)
            pipe.xrevrange(key, count=1)
        raw = cast("list[object]", await pipe.execute())
    stale: list[str] = []
    for index, key in enumerate(keys):
        ttl, entries = cast("int", raw[2 * index]), cast("list[tuple[str, object]]", raw[2 * index + 1])
        if int(ttl) == NO_TTL and entries and _event_ms(str(entries[0][0])) < cutoff_ms:
            stale.append(key)
    return stale


async def _expire_keys(client: AsyncRedis, keys: list[str]) -> None:
    """`EXPIRE` cả lô khoá cũ trong một pipeline."""
    async with client.pipeline(transaction=False) as pipe:
        for key in keys:
            pipe.expire(key, STALE_TTL_S)
        await pipe.execute()


async def run_expire_stale_uploads(client: AsyncRedis, clock: Clock, *, batch: int) -> int:
    """Đặt hạn cho mọi stream upload mồ côi; trả số khoá đã đặt hạn.

    Idempotent (J06): lượt sau thấy khoá đã có TTL nên bỏ qua, và `SCAN` có thể trả một
    khoá hai lần — đặt lại cùng hạn cũng không đổi kết quả.
    """
    cutoff_ms = int((clock.now() - STALE_AFTER).timestamp() * 1000)
    cursor, expired = 0, 0
    while True:
        cursor, keys = await _scan_batch(client, cursor, batch)
        stale = await _stale_keys(client, keys, cutoff_ms) if keys else []
        if stale:
            await _expire_keys(client, stale)
            expired += len(stale)
        if cursor == 0:
            break
    _log.info("stream_stale_uploads_expired", extra={"expired": expired})
    return expired


@periodic(TASK_NAME, every=EVERY)
async def expire_stale_uploads() -> None:
    """Hàm lịch: chỉ dựng client thật rồi gọi lõi (BE-00 §7 "khuôn lịch nền")."""
    client = streams_redis()
    try:
        await run_expire_stale_uploads(client, SystemClock(), batch=SCAN_BATCH)
    finally:
        await client.aclose()
