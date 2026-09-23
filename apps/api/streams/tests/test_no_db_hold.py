"""Luồng SSE không giữ kết nối Postgres của request (K36, B4-01 [8]).

`AppRoute` commit và đóng `db_session` **trước** khi thân `StreamingResponse` chạy, và
mọi truy vấn trong vòng đời luồng (`check_session`, nhà cung cấp) mở phiên ngắn riêng từ
`app.state.sessionmaker`. Nếu một ngày nào đó generator giữ lại session của request thì
hai mươi luồng mở là hai mươi kết nối bị giam — pool `DB_POOL_SIZE` cạn và **mọi** route
REST khác 503. Test này đo đúng điều đó bằng `engine.pool.checkedout()`.
"""

from contextlib import AsyncExitStack
from typing import Final

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.streams.tests.fakes import progress_provider
from apps.api.streams.tests.test_streams_open_progress import FAST, WAIT_S, progress_path
from packages.testing.fixtures.auth import ORIGIN, REFRESH_PATH
from packages.testing.fixtures.streams import SseOpen, StreamAppFactory, signed_stream_user

USERS: Final = 5
STREAMS_PER_USER: Final = 4
"""5 x 4 = 20 luồng, dưới trần 6 của mỗi người nên không lượt nào bị 429."""


async def test_open_streams_do_not_hold_postgres_connections(
    stream_app: StreamAppFactory,
    sse_open: SseOpen,
    db_session: AsyncSession,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """20 luồng của 5 người đang mở → `pool.checkedout() == 0` và request REST khác vẫn chạy."""
    app = stream_app(providers=[progress_provider()], **FAST)
    async with AsyncExitStack() as stack:
        owners = [await stack.enter_async_context(signed_stream_user(app, db_session)) for _ in range(USERS)]
        for owner in owners:
            for _ in range(STREAMS_PER_USER):
                stream = await stack.enter_async_context(sse_open(app, progress_path(), cookies=owner.cookies))
                assert stream.status == 200
                await stream.next_frames(1, WAIT_S)
        checked_out = app.state.engine.pool.checkedout()
        with capsys.disabled():
            print(f"\n[K36] {USERS * STREAMS_PER_USER} luồng đang mở → pool.checkedout()={checked_out}")
        assert checked_out == 0
        # Đường REST thật vẫn phục vụ được trong lúc 20 luồng đang chờ `XREAD BLOCK`.
        refreshed = await owners[0].client.post(REFRESH_PATH, headers=ORIGIN)
        assert refreshed.status_code == 200, refreshed.text
        assert app.state.engine.pool.checkedout() == 0
