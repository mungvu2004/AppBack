"""`AuthServices` — tài nguyên của app mà xác thực cần (BE-00 §2.2).

`build_verifier(app)` chạy trong `create_app`, **trước** `lifespan`: lúc đó `app.state` mới
có `clock`, chưa có sessionmaker hay client Redis. Vì vậy lớp này chỉ giữ `app.state` và
đọc từng tài nguyên **lúc gọi**; dựng sớm là giữ tham chiếu `None` suốt đời app.
"""

import logging
from collections.abc import Awaitable
from typing import Final, cast

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.core.clock import Clock
from packages.messaging.redis import AsyncRedis, translate_redis_error

_log: Final = logging.getLogger(__name__)


class AuthServices:
    """Đồng hồ, sessionmaker và hai client Redis mà `lifespan` của B0-06 gắn lên `app.state`."""

    def __init__(self, app: FastAPI) -> None:
        """Giữ `app.state`; không đọc gì cả (xem docstring module)."""
        self._state = app.state

    @property
    def clock(self) -> Clock:
        """Đồng hồ của app — giả ở `APP_ENV=test` (K20)."""
        return cast("Clock", self._state.clock)

    @property
    def sessionmaker(self) -> async_sessionmaker[AsyncSession]:
        """Sessionmaker của pool request — `check_session` mở session ngắn riêng từ đây."""
        return cast("async_sessionmaker[AsyncSession]", self._state.sessionmaker)

    @property
    def cache(self) -> AsyncRedis:
        """`redis-cache`: cache `Principal`, hạn mức refresh (được đuổi khi đầy)."""
        return cast("AsyncRedis", self._state.cache_redis)

    @property
    def safe(self) -> AsyncRedis:
        """DB an toàn trên `redis-broker`: khoá đăng nhập (không bị đuổi, BE-00 §11)."""
        return cast("AsyncRedis", self._state.safe_redis)


async def soft_redis[ResultT](call: Awaitable[ResultT], event: str) -> ResultT | None:
    """Một lời gọi Redis **được phép hỏng** (cache `Principal`, hạn mức `on_error="open"`).

    Lỗi phụ thuộc (mất kết nối, hết giờ) → log `event` rồi trả `None`: người gọi đi tiếp
    như khi cache trượt. Lỗi lệnh (sai kiểu khoá, script hỏng) là lỗi của mã, nổi lên
    nguyên trạng (R-16).
    """
    try:
        return await call
    except Exception as exc:  # phân loại ngay dưới: lỗi không phải phụ thuộc được ném lại
        if translate_redis_error(exc) is None:
            raise
        _log.warning(event, extra={"error": type(exc).__name__})
        return None
