"""`GET /api/health` và `GET /api/ready` (B0-06 [2]).

Hai route cố ý khác nhau:

- `health_live` **không chạm phụ thuộc nào**. Nó trả lời "tiến trình còn sống";
  nếu nó cũng kiểm Postgres thì mỗi lần DB chập chờn là orchestrator giết luôn
  tiến trình đang khoẻ;
- `health_ready` kiểm đủ Postgres, hai Redis (kèm `maxmemory-policy` của broker —
  `allkeys-lru` ở đó là **mất việc**) và kho object. Kết quả được cache 2 giây và
  có rate limit theo IP: endpoint này công khai, nên nó cũng là một cách để người
  lạ bắt máy chủ mở kết nối.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final, Literal

from fastapi import Depends
from sqlalchemy import text
from starlette.requests import Request

from apps.api.core.ratelimit import key_ip, rate_limit
from apps.api.core.routing import public_router
from apps.api.core.wire import WireModel
from packages.core.error_codes import DEPENDENCY_UNAVAILABLE
from packages.messaging.redis import assert_broker_policy

_log: Final = logging.getLogger(__name__)

READY_CACHE: Final = timedelta(seconds=2)
PROBE_TIMEOUT_S: Final = 2.0
"""Trần **tổng** của một lượt kiểm: trần từng lời gọi (DB 10 s, Redis 2+5 s) cộng dồn
thì một probe có thể treo hơn 10 s, lâu hơn hẳn `timeoutSeconds` của probe orchestrator."""
READY_RETRY_AFTER_S: Final = 5
READY_LIMIT: Final = 60
READY_WINDOW_S: Final = 60
PROBE_KEY: Final = "health/ready-probe"
"""Khoá không tồn tại: `stat` vẫn phải đi tới kho và trả lời được, đó mới là phép thử."""

STATE_ATTR: Final = "ready_cache"

router = public_router(tags=["health"])
ROUTERS: Final = (router,)


class HealthStatus(WireModel):
    """Thân của cả hai route: đúng một khoá `status`."""

    status: Literal["ok"]


@dataclass(frozen=True, slots=True)
class ReadyCache:
    """Kết quả một lượt kiểm và thời điểm nó hết hiệu lực."""

    until: datetime
    healthy: bool


@router.get("/health", response_model=HealthStatus, status_code=200)
async def health_live() -> HealthStatus:
    """Sống hay chưa — không mở kết nối nào."""
    return HealthStatus(status="ok")


@router.get(
    "/ready",
    response_model=HealthStatus,
    status_code=200,
    dependencies=[
        Depends(
            rate_limit(
                "health_ready",
                limit=READY_LIMIT,
                window_s=READY_WINDOW_S,
                key=key_ip,
                store="cache",
                on_error="open",
            )
        )
    ],
)
async def health_ready(request: Request) -> HealthStatus:
    """Sẵn sàng nhận tải chưa; hỏng một phụ thuộc → 503 `DEPENDENCY_UNAVAILABLE`."""
    if not await _cached_probe(request):
        raise DEPENDENCY_UNAVAILABLE.error(retry_after=READY_RETRY_AFTER_S)
    return HealthStatus(status="ok")


async def _cached_probe(request: Request) -> bool:
    """Kết quả kiểm, dùng lại trong `READY_CACHE` — probe của k8s gọi mỗi giây."""
    now = request.app.state.clock.now()
    cached = getattr(request.app.state, STATE_ATTR, None)
    if isinstance(cached, ReadyCache) and cached.until > now:
        return cached.healthy
    healthy = await probe(request)
    setattr(request.app.state, STATE_ATTR, ReadyCache(until=now + READY_CACHE, healthy=healthy))
    return healthy


async def probe(request: Request) -> bool:
    """Một lượt kiểm thật. Mọi hỏng hóc đều quy về "chưa sẵn sàng", có log để truy."""
    state = request.app.state
    try:
        async with asyncio.timeout(PROBE_TIMEOUT_S):
            async with state.sessionmaker() as session:
                await session.execute(text("SELECT 1"))
            await state.cache_redis.ping()
            await state.safe_redis.ping()
            # Client đồng bộ: `assert_broker_policy` chạy được cả trong tín hiệu Celery,
            # nên ở đây phải đẩy sang luồng khác để không chặn vòng sự kiện (R-23).
            await asyncio.to_thread(assert_broker_policy, state.broker_sync)
            await state.storage.stat(PROBE_KEY)
    except Exception as exc:  # noqa: BLE001 — probe: mọi lỗi đều là "chưa sẵn sàng", không có ngoại lệ nào đáng nổi lên
        _log.warning("ready_probe_failed", extra={"error": repr(exc)})
        return False
    return True
