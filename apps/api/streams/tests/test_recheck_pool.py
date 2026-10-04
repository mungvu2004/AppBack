"""Recheck của luồng SSE đọc Postgres bằng phiên ngắn rồi trả kết nối về pool (K36, NO-342).

`test_no_db_hold.py` đứng đồng hồ nên không recheck nào chạy; test này kích **đúng một** recheck
bằng đồng hồ `monotonic` tiêm được của `sse` và xoá ảnh chụp phiên trong cache, để `check_session`
phải đi đường `_load_snapshot` (Postgres) — rồi khẳng định kết nối đã về pool.

Tín hiệu "recheck xong" là lượt `authorize` của nhà cung cấp: `_still_allowed` gọi nó **sau**
`check_session` (`apps/api/streams/sse.py`), tức sau khi phiên ngắn đã thoát `async with`.
Đồng hồ đứng sau bước nhảy nên recheck kế không bao giờ tới hạn — lúc đo không còn truy vấn nào.
"""

import asyncio
from collections.abc import Mapping
from time import monotonic

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.auth.sessions import principal_key
from apps.api.core.auth import Principal
from apps.api.streams import sse
from apps.api.streams.tests.fakes import FakePolicy, progress_provider
from apps.api.streams.tests.test_streams_open_progress import FAST, WAIT_S, progress_path
from packages.testing.fixtures.streams import SseOpen, StreamAppFactory, signed_stream_user


class SteppedClock:
    """`monotonic` của `sse` đứng yên tới khi test `advance` — recheck tới hạn theo ý test."""

    def __init__(self) -> None:
        """Bắt đầu ở giờ thật hiện tại."""
        self.now = monotonic()

    def __call__(self) -> float:
        """Giờ hiện tại của đồng hồ."""
        return self.now

    def advance(self, seconds: float) -> None:
        """Nhảy tới trước `seconds` giây."""
        self.now += seconds


class SignallingPolicy(FakePolicy):
    """`FakePolicy` cho qua, bật `rechecked` ở lượt `authorize` đầu tiên sau khi test `arm()`."""

    def __init__(self) -> None:
        """Chưa canh: lượt `authorize` lúc mở luồng không tính."""
        super().__init__()
        self.rechecked = asyncio.Event()
        self._armed = False

    def arm(self) -> None:
        """Từ giờ, lượt `authorize` kế là của recheck."""
        self._armed = True

    async def authorize(
        self,
        principal: Principal,
        params: Mapping[str, str],
        sessionmaker: async_sessionmaker[AsyncSession],
    ) -> None:
        """Đếm và cho qua như `FakePolicy`, rồi báo recheck đã xong nếu đang canh."""
        await super().authorize(principal, params, sessionmaker)
        if self._armed:
            self.rechecked.set()


async def test_recheck__returns_session_to_pool(
    stream_app: StreamAppFactory,
    sse_open: SseOpen,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Recheck trượt cache mượn kết nối (`checkout` ≥ 1) và trả lại ngay: `checkedout() == 0` khi recheck xong."""
    clock = SteppedClock()
    monkeypatch.setattr(sse, "monotonic", clock)
    policy = SignallingPolicy()
    app = stream_app(providers=[progress_provider(policy)], **FAST)
    async with (
        signed_stream_user(app, db_session) as owner,
        sse_open(app, progress_path(), cookies=owner.cookies) as stream,
    ):
        await stream.next_frames(1, WAIT_S)
        pool = app.state.engine.pool
        checkouts: list[object] = []

        def on_checkout(*_args: object) -> None:
            """Ghi một lượt mượn kết nối của pool."""
            checkouts.append(None)

        event.listen(pool, "checkout", on_checkout)
        await app.state.cache_redis.delete(principal_key(owner.signed.sid))
        assert pool.checkedout() == 0

        policy.arm()
        clock.advance(60)
        await asyncio.wait_for(policy.rechecked.wait(), WAIT_S)

        assert checkouts, "cache trượt nên recheck phải đọc Postgres"
        assert pool.checkedout() == 0
