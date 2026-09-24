"""Lịch `default.streams.expire_stale_uploads` (B4-01 [6] "Dọn rác", J01, J06)."""

from datetime import timedelta
from typing import Final

from apps.api.streams.jobs import (
    EVERY,
    STALE_AFTER,
    STALE_TTL_S,
    TASK_NAME,
    expire_stale_uploads,
    run_expire_stale_uploads,
)
from packages.core.ids import new_id
from packages.messaging.redis import AsyncRedis, streams_redis_sync, sync_result
from packages.messaging.schedules import schedule_entries
from packages.messaging.streams import FIELD, upload_stream
from packages.testing.fixtures.clock import FakeClock

STALE_ID: Final = "upl_01ARZ3NDEKTSV4RRFFQ69G5FAV"
FRESH_ID: Final = "upl_01BX5ZZKBKACTAV9WEVGEMMVRZ"
CLOSED_ID: Final = "upl_01CQ4Y6MZKACTAV9WEVGEMMVS0"
KEPT_TTL_S: Final = 500
BATCH: Final = 3
"""Lô nhỏ hơn số khoá của test, để vòng `SCAN` chạy nhiều lượt thật."""
FILLER_COUNT: Final = 40
"""NO-158: seed nhiều khoá **hơn hẳn** `BATCH` — 3 khoá đúng bằng `BATCH` không ép được `SCAN`
quay lại (`apps/api/streams/jobs.py:91->85`) một cách tất định, phụ thuộc may rủi bảng băm
Redis (và khoá còn sót của DB streams dùng chung). Khoá đệm là stream **mới, không hạn** nên
không đổi số đếm `== 1` của test — chỉ ép cursor `SCAN` khác 0 giữa các lượt."""


def _ms(clock: FakeClock, ago: timedelta) -> int:
    """Mốc mili giây của `clock.now() - ago` — phần mili giây của một id Redis Stream."""
    return int((clock.now() - ago).timestamp() * 1000)


async def _seed(client: AsyncRedis, fake_clock: FakeClock) -> None:
    """Ba stream có ý nghĩa (cũ không hạn, mới không hạn, cũ đã có hạn) + đệm ép `SCAN` quay lại."""
    stale_ms = _ms(fake_clock, STALE_AFTER + timedelta(days=1))
    await client.xadd(upload_stream(STALE_ID), {FIELD: "{}"}, id=f"{stale_ms}-0")
    await client.xadd(upload_stream(FRESH_ID), {FIELD: "{}"}, id=f"{_ms(fake_clock, timedelta())}-0")
    await client.xadd(upload_stream(CLOSED_ID), {FIELD: "{}"}, id=f"{stale_ms}-0")
    await client.expire(upload_stream(CLOSED_ID), KEPT_TTL_S)
    fresh_ms = _ms(fake_clock, timedelta())
    for _ in range(FILLER_COUNT):
        await client.xadd(upload_stream(new_id("upl", fake_clock)), {FIELD: "{}"}, id=f"{fresh_ms}-0")


async def test_expire_stale_uploads__J01(streams_client: AsyncRedis, fake_clock: FakeClock) -> None:
    """Đường thường: chỉ stream cũ **và** không hạn bị đặt `EXPIRE`; hai stream kia giữ nguyên."""
    await _seed(streams_client, fake_clock)
    assert await run_expire_stale_uploads(streams_client, fake_clock, batch=BATCH) == 1
    assert 0 < await streams_client.ttl(upload_stream(STALE_ID)) <= STALE_TTL_S
    assert await streams_client.ttl(upload_stream(FRESH_ID)) == -1
    assert STALE_TTL_S > await streams_client.ttl(upload_stream(CLOSED_ID)) > 0


async def test_expire_stale_uploads__J06(streams_client: AsyncRedis, fake_clock: FakeClock) -> None:
    """Chạy hai lượt cho kết quả như một lượt: khoá đã có hạn không bị đếm lại."""
    await _seed(streams_client, fake_clock)
    assert await run_expire_stale_uploads(streams_client, fake_clock, batch=BATCH) == 1
    assert await run_expire_stale_uploads(streams_client, fake_clock, batch=BATCH) == 0
    assert 0 < await streams_client.ttl(upload_stream(STALE_ID)) <= STALE_TTL_S


async def test_run_expire_stale_uploads_on_empty_db(streams_client: AsyncRedis, fake_clock: FakeClock) -> None:
    """Không có stream nào: một lượt `SCAN` rồi thôi, không ném."""
    assert await run_expire_stale_uploads(streams_client, fake_clock, batch=BATCH) == 0


def test_schedule_is_registered() -> None:
    """Lịch nằm trong sổ của `packages.messaging` để beat của worker đọc được."""
    entries = {entry.name: entry for entry in schedule_entries()}
    assert entries[TASK_NAME].every == EVERY
    assert entries[TASK_NAME].function == "expire_stale_uploads"


def test_expire_stale_uploads_smoke(messaging_env: None) -> None:
    """Test khói: gọi chính hàm lịch với giờ thật và client Redis nó tự dựng (BE-00 §7)."""
    client = streams_redis_sync()
    key = upload_stream(STALE_ID)
    try:
        client.xadd(key, {FIELD: "{}"}, id="1000000000000-0")  # 2001-09-09, cũ hơn mọi ngưỡng
        expire_stale_uploads()
        assert 0 < sync_result(client.ttl(key), int) <= STALE_TTL_S
    finally:
        # Không `flushdb`: DB streams là fixture phiên dùng chung — xoá đúng khoá test tạo ra
        # thì bộ test vẫn đúng khi một ngày nào đó bật chạy song song (TEST-05).
        client.delete(key)
        client.close()
