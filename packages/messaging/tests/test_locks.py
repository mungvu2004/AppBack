"""Khoá an toàn trên Redis thật: tranh chấp, hết hạn, token rào, tự gia hạn."""

import asyncio
from contextlib import suppress

import pytest

from packages.messaging.locks import FENCE_SUFFIX, LockBusy, LockLost, SafeLock
from packages.messaging.redis import AsyncRedis, safe_redis, safe_redis_sync
from packages.testing.fixtures.messaging import ephemeral_broker

NAME = "gpu:0"
KEY = f"lock:{NAME}"
TTL_MS = 300
RENEW_MS = 80
WAIT_S = 30.0
"""Trần của mọi lượt chờ một trạng thái: chỉ để test không treo, không phải biên thời gian."""


def lock(client: AsyncRedis, *, ttl_ms: int = TTL_MS) -> SafeLock:
    return SafeLock(client, NAME, ttl_ms)


@pytest.mark.parametrize(("name", "ttl_ms"), [("", TTL_MS), (NAME, 0), (NAME, -1)])
def test_lock_rejects_a_nameless_or_deadline_free_configuration(
    safe_client: AsyncRedis, name: str, ttl_ms: int
) -> None:
    with pytest.raises(ValueError, match=r"tên khoá|ttl_ms"):
        SafeLock(safe_client, name, ttl_ms)


async def test_only_one_side_wins_a_contested_lock(safe_client: AsyncRedis) -> None:
    first, second = lock(safe_client), lock(safe_client)

    tokens = await asyncio.gather(first.acquire(), second.acquire())

    assert sorted(token is None for token in tokens) == [False, True]
    assert await safe_client.ttl(KEY) >= 0


async def test_the_second_holder_gets_a_larger_fence_token(safe_client: AsyncRedis) -> None:
    """Token rào phải tăng đơn điệu: người ghi dùng nó để bỏ qua lượt ghi của chủ cũ."""
    lease = lock(safe_client, ttl_ms=100)
    first = await lease.acquire()
    await asyncio.sleep(0.15)
    second = await lease.acquire()

    assert first is not None
    assert second is not None
    assert second > first
    assert int(await safe_client.get(f"{KEY}{FENCE_SUFFIX}")) == second


async def test_an_expired_owner_cannot_renew_or_release_the_new_owner(safe_client: AsyncRedis) -> None:
    lease = lock(safe_client, ttl_ms=100)
    stale = await lease.acquire()
    await asyncio.sleep(0.15)
    fresh = await lease.acquire()
    assert stale is not None
    assert fresh is not None

    assert await lease.renew(stale) is False
    await lease.release(stale)
    assert await safe_client.exists(KEY) == 1

    assert await lease.renew(fresh) is True
    await lease.release(fresh)
    assert await safe_client.exists(KEY) == 0


async def test_renew_on_a_missing_lock_reports_failure(safe_client: AsyncRedis) -> None:
    assert await lock(safe_client).renew(1) is False


async def test_hold_keeps_the_lock_alive_past_three_ttls(safe_client: AsyncRedis) -> None:
    async with lock(safe_client).hold(RENEW_MS) as token:
        assert token >= 1
        await asyncio.sleep(TTL_MS * 3.5 / 1000)
        assert await safe_client.exists(KEY) == 1

    assert await safe_client.exists(KEY) == 0


async def test_hold_refuses_to_start_when_someone_else_holds_the_lock(safe_client: AsyncRedis) -> None:
    lease = lock(safe_client, ttl_ms=5000)
    assert await lease.acquire() is not None

    with pytest.raises(LockBusy, match=NAME):
        async with lease.hold(RENEW_MS):
            pytest.fail("không được vào thân khi khoá đang có chủ")


async def test_hold_interrupts_the_body_when_the_lock_is_taken_away(safe_client: AsyncRedis) -> None:
    """Mất khoá giữa chừng thì việc dài phải dừng, không chạy tiếp dưới khoá người khác."""
    reached: list[str] = []

    async def long_work() -> None:
        async with lock(safe_client).hold(RENEW_MS):
            await safe_client.delete(KEY)
            await asyncio.sleep(TTL_MS * 4 / 1000)
            reached.append("het thân")

    with pytest.raises(LockLost, match=NAME):
        await long_work()

    assert reached == []


async def test_hold_lets_a_body_error_through_unchanged(safe_client: AsyncRedis) -> None:
    with pytest.raises(ZeroDivisionError):
        async with lock(safe_client).hold(RENEW_MS):
            raise ZeroDivisionError

    assert await safe_client.exists(KEY) == 0


async def test_hold_forwards_a_cancellation_that_is_not_a_lost_lock(safe_client: AsyncRedis) -> None:
    async def holding() -> None:
        async with lock(safe_client, ttl_ms=5000).hold(RENEW_MS):
            await asyncio.sleep(10)

    task = asyncio.create_task(holding())
    await asyncio.sleep(0.1)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.parametrize("renew_every_ms", [0, -1, TTL_MS, TTL_MS + 1])
async def test_hold_rejects_a_renewal_period_that_cannot_beat_the_ttl(
    safe_client: AsyncRedis, renew_every_ms: int
) -> None:
    with pytest.raises(ValueError, match="renew_every_ms"):
        async with lock(safe_client).hold(renew_every_ms):
            pytest.fail("không được vào thân với chu kỳ gia hạn sai")


async def test_hold_requires_a_running_task(safe_client: AsyncRedis, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(asyncio, "current_task", lambda: None)

    with pytest.raises(RuntimeError, match="task asyncio"):
        async with lock(safe_client).hold(RENEW_MS):
            pytest.fail("không được vào thân khi không có task để huỷ")


async def test_hold_reports_a_lost_lock_even_when_the_body_swallows_the_cancellation(
    safe_client: AsyncRedis,
) -> None:
    """Thân nuốt `CancelledError` mà vòng gia hạn gửi thì vẫn chạy tiếp; lúc thoát `hold` phải báo
    `LockLost` thay vì thoát êm như thể việc đã xong dưới khoá (NO-025)."""

    async def stubborn() -> None:
        async with lock(safe_client).hold(RENEW_MS):
            await safe_client.delete(KEY)
            with suppress(asyncio.CancelledError):
                await asyncio.wait_for(asyncio.Event().wait(), WAIT_S)

    with pytest.raises(LockLost, match=NAME):
        await stubborn()
    # Lượt huỷ của vòng gia hạn đã được trả lại: `asyncio.timeout` bên ngoài không đọc nhầm.
    current = asyncio.current_task()
    assert current is not None
    assert current.cancelling() == 0


async def test_hold_lets_a_body_error_raised_after_losing_the_lock_through(safe_client: AsyncRedis) -> None:
    """Thân đổi lượt huỷ thành lỗi của chính nó: lỗi đó nổi lên nguyên trạng, lượt huỷ được trả lại."""

    async def converting() -> None:
        async with lock(safe_client).hold(RENEW_MS):
            await safe_client.delete(KEY)
            try:
                await asyncio.wait_for(asyncio.Event().wait(), WAIT_S)
            except asyncio.CancelledError:
                raise RuntimeError("dọn dở") from None

    with pytest.raises(RuntimeError, match="dọn dở"):
        await converting()
    current = asyncio.current_task()
    assert current is not None
    assert current.cancelling() == 0


async def test_hold_reports_a_lock_lost_under_a_blocking_body(safe_client: AsyncRedis) -> None:
    """Khối đồng bộ dài không nhường vòng sự kiện, nên vòng gia hạn không chen vào được; khoá mất
    (hết hạn, bị lấy) trong lúc đó thì `hold` báo `LockLost` lúc thoát (NO-025)."""
    blocking = safe_redis_sync()
    try:
        with pytest.raises(LockLost, match=NAME):
            async with lock(safe_client).hold(RENEW_MS):
                blocking.delete(KEY)  # lời gọi đồng bộ: thân không có một điểm `await` nào
    finally:
        blocking.close()


async def test_hold_treats_a_broken_redis_as_a_lost_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail-closed: gia hạn không xong vì Redis hỏng cũng là mất khoá.

    Để lỗi thoát khỏi vòng gia hạn thì task gia hạn chết im lặng và thân vẫn chạy tiếp
    dưới một khoá sắp hết hạn — đúng thứ token rào sinh ra để chống."""
    reached: list[str] = []

    with ephemeral_broker(monkeypatch) as admin:
        client = safe_redis()
        try:

            async def long_work() -> None:
                async with SafeLock(client, NAME, TTL_MS).hold(RENEW_MS):
                    # Giết hẳn máy chủ: `maxmemory` không chặn `PEXPIRE` (lệnh không cấp phát),
                    # nên chỉ mất kết nối mới dựng được cảnh "gia hạn không xong".
                    admin.shutdown(nosave=True)
                    await asyncio.sleep(TTL_MS * 4 / 1000)
                    reached.append("het thân")

            with pytest.raises(LockLost, match=NAME):
                await long_work()
        finally:
            await client.aclose()

    assert reached == []
