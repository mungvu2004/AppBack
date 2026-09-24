"""Lõi luồng SSE: tài nguyên đã giữ luôn về, và id stream tách bằng hàm dùng chung (B4-01).

Hai nợ khác nhau, cùng một file sản phẩm:

- NO-156 — `AppRoute._finish` (idempotency → commit → chờ callback sau commit) chạy **sau**
  khi handler đã trả `StreamingResponse`. Nó ném là response bị bỏ, `stream_body` không bao
  giờ chạy, và ba thứ `open_stream` đã giữ (chỗ ZSET, chỗ toàn cục, kết nối pool SSE) rò
  cho tới khi TTL dọn hộ;
- NO-157 — `_id_key` từng được chép lại ở đây, trùng bản của `packages.messaging.streams` (R-07).
"""

from typing import Final

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core import routing
from apps.api.streams import sse
from apps.api.streams.connections import conn_key
from apps.api.streams.tests.fakes import progress_provider
from apps.api.streams.tests.test_streams_open_progress import FAST, progress_path
from packages.messaging.redis import AsyncRedis
from packages.messaging.streams import event_id_key
from packages.testing.fixtures.streams import SseOpen, StreamAppFactory, signed_stream_user

SLOTS: Final = 2
"""Trần chỗ toàn cục nhỏ hơn số lượt: rò một chỗ hay một kết nối pool thì lượt thứ ba đã hỏng."""

ROUNDS: Final = 5


def test_sse_reuses_the_shared_event_id_key() -> None:
    """NO-157: không còn bản chép `_id_key` trong `sse.py`; nó nhập hàm công khai của B0-05."""
    assert not hasattr(sse, "_id_key")
    # Đọc qua `vars()`: `mypy --strict` cấm đọc một tên **nhập lại** như thuộc tính module.
    assert vars(sse)["event_id_key"] is event_id_key


async def test_a_failure_after_the_handler_returns_every_held_resource(
    stream_app: StreamAppFactory,
    sse_open: SseOpen,
    db_session: AsyncSession,
    cache_client: AsyncRedis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """NO-156: bước sau handler ném → chỗ ZSET, chỗ toàn cục và kết nối pool SSE đều về.

    Năm lượt liên tiếp với `STREAM_MAX_GLOBAL=2` bắt cả ba đường rò cùng lúc: chỗ toàn cục
    rò thì lượt thứ ba là 429, kết nối pool rò thì nó là 503 (pool cạn), còn chỗ ZSET rò thì
    `zcard` cuối cùng khác 0.

    `_finish` chỉ được thay **sau** khi `signed_stream_user` đăng nhập xong: chính lượt
    đăng nhập cũng đi qua `AppRoute`.
    """
    app = stream_app(providers=[progress_provider()], stream_max_global=str(SLOTS), **FAST)
    async with signed_stream_user(app, db_session) as owner:

        async def boom(*_args: object, **_kwargs: object) -> None:
            """Bước sau handler hỏng — như `commit()` gặp Postgres mất kết nối."""
            raise RuntimeError("bước sau handler hỏng")

        monkeypatch.setattr(routing, "_finish", boom)

        for round_number in range(ROUNDS):
            async with sse_open(app, progress_path(), cookies=owner.cookies) as stream:
                assert stream.status == 500, f"lượt {round_number}: {stream.status} {stream.body!r}"
            assert not app.state.stream_slots.locked(), f"lượt {round_number} không trả chỗ toàn cục"

        assert await cache_client.zcard(conn_key(owner.user.id)) == 0
