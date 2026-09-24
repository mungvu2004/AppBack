"""Lõi một luồng SSE: mở, phát, giữ quyền, dọn (B4-01 [6]; BE-00 §7 "SSE", W15).

Ba điều quyết định toàn bộ hình dạng file này:

- **vị trí bắt đầu tính trước byte đầu.** Đọc đuôi stream rồi mới lấy ảnh chụp, nên sự
  kiện đến giữa hai bước vẫn được phát **sau** ảnh chụp: FE nhận lặp một `Progress` đơn
  điệu chứ không mất sự kiện (S08);
- **không có session DB của request.** `AppRoute` đã commit và đóng session trước khi
  thân `StreamingResponse` chạy, nên mọi truy vấn trong vòng đời luồng đi qua
  `check_session` và nhà cung cấp với `app.state.sessionmaker` — phiên ngắn, đóng ngay (K36);
- **dọn phải chống huỷ.** Starlette huỷ task group khi client rớt và AnyIO huỷ lại mọi
  `await` còn trong scope bị huỷ; không `CancelScope(shield=True)` thì `ZREM` không bao
  giờ chạy và chỗ giữ rò cho tới khi TTL khoá hết (S05);
- **generator chưa chắc được chạy.** Giữa lúc handler trả `StreamingResponse` và lúc byte
  đầu ra dây còn `AppRoute._finish`; nó ném là response bị bỏ và `finally` của generator
  không bao giờ tới. Vì vậy `open_stream` ghi tài nguyên đã giữ lên `request.state` và
  `StreamRoute` (`router.py`) trả chúng bằng `release_held` (NO-156).

Mỗi luồng giữ **một** kết nối của pool SSE riêng (`XREAD BLOCK` chiếm socket suốt lượt
chặn). Trần toàn cục lấy bằng một semaphore cùng cỡ pool: hết chỗ phải là 429 ngay,
chứ không phải chờ pool rồi treo request.
"""

import asyncio
import json
import logging
import random
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from time import monotonic
from typing import Final, cast

import anyio
from fastapi import FastAPI
from pydantic import ValidationError
from redis.asyncio import Redis
from redis.exceptions import RedisError
from starlette.requests import Request
from starlette.responses import StreamingResponse

from apps.api.auth.cookies import STREAM_COOKIE
from apps.api.auth.services import AuthServices
from apps.api.auth.sessions import check_session
from apps.api.auth.stream_tokens import StreamClaims, verify_stream_token
from apps.api.core.auth import Principal
from apps.api.streams import connections
from apps.api.streams.providers import SnapshotProvider, StreamKind, StreamProvider
from apps.api.streams.settings import RECHECK_JITTER, StreamSettings, get_stream_settings
from packages.core.clock import Clock
from packages.core.error_codes import DEPENDENCY_UNAVAILABLE, RATE_LIMITED, UNAUTHENTICATED
from packages.core.errors import AppError
from packages.core.ids import new_id
from packages.core.logging import bind_log_context
from packages.messaging.redis import AsyncRedis
from packages.messaging.streams import FIRST_ID, Event, EventBus, event_id_key, is_event_id

_log: Final = logging.getLogger(__name__)
_jitter: Final = random.SystemRandom()

SSE_MEDIA_TYPE: Final = "text/event-stream; charset=utf-8"
SSE_HEADERS: Final = {"Cache-Control": "no-store", "X-Accel-Buffering": "no"}
PING: Final = ": ping\n\n"
"""Heartbeat W15 — một dòng chú thích, không phải sự kiện; FE bỏ qua, nginx thì không."""

RETRY_AFTER_S: Final = 5
CLEANUP_TIMEOUT_S: Final = 1.0

HELD_ATTR: Final = "stream_held"
"""Tên thuộc tính trên `request.state` giữ `StreamContext` cho tới khi response chắc chắn ra dây."""

CLIENT_GONE: Final = "client_gone"
REVOKED: Final = "revoked"
REDIS_ERROR: Final = "redis_error"
DEPENDENCY_ERROR: Final = "dependency_error"
SNAPSHOT_INVALID: Final = "snapshot_invalid"
SETUP_FAILED: Final = "setup_failed"


def frame(event_id: str, data: Mapping[str, object]) -> str:
    """Một khung SSE W15: `id:` rồi `data:` một dòng, **không bao giờ** `event:` (K03).

    Ghi lại chính dữ liệu đã qua `model_validate` chứ không serialize lại từ model: đi
    qua model là thêm trường mặc định và đổi alias, làm dây lệch khỏi schema FE.
    """
    body = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    return f"id: {event_id}\ndata: {body}\n\n"


def _slot_ttl_ms(settings: StreamSettings) -> int:
    """TTL của mục và khoá ZSET: 2 lần heartbeat, đủ để một luồng im lặng vẫn giữ chỗ."""
    return int(settings.stream_heartbeat_s * 2000)


def _now_ms(clock: Clock) -> int:
    """Mốc mili giây của đồng hồ app — score của ZSET giữ chỗ."""
    return int(clock.now().timestamp() * 1000)


def _error_marks(exc: ValidationError) -> list[dict[str, object]]:
    """Chỉ `loc` và `type` của từng lỗi: K11 cấm đưa `data` của sự kiện vào log."""
    return [{"loc": item["loc"], "type": item["type"]} for item in exc.errors(include_input=False, include_url=False)]


@dataclass(frozen=True, slots=True)
class StreamRequest:
    """Kết quả các bước kiểm của router, trước khi trung tâm SSE giữ chỗ (B4-01 [6])."""

    kind: StreamKind
    stream: str
    params: Mapping[str, str]
    principal: Principal
    claims: StreamClaims
    services: AuthServices
    last_event_id: str | None


@dataclass(frozen=True, slots=True)
class StreamContext:
    """Tài nguyên đã giữ của một luồng đang mở; `_close` trả lại đúng từng thứ."""

    app: FastAPI
    spec: StreamRequest
    provider: StreamProvider
    settings: StreamSettings
    client: Redis
    bus: EventBus
    conn_id: str
    ttl_ms: int

    @property
    def cache(self) -> AsyncRedis:
        """`redis-cache` của app — nơi ZSET giữ chỗ sống."""
        return cast("AsyncRedis", self.app.state.cache_redis)

    @property
    def clock(self) -> Clock:
        """Đồng hồ của app (giả ở `APP_ENV=test`)."""
        return cast("Clock", self.app.state.clock)


@dataclass(frozen=True, slots=True)
class StartPosition:
    """Vị trí bắt đầu đã chốt; `ok=False` = ảnh chụp hỏng, đóng luồng mà không gửi gì."""

    cursor: str
    opening: str | None = None
    ok: bool = True


@dataclass(slots=True)
class _LoopState:
    """Con trỏ và ba mốc thời gian của vòng phát; `reason` là lý do đóng cuối cùng."""

    cursor: str
    last_sent: float
    next_recheck: float
    next_refresh: float
    reason: str = CLIENT_GONE


async def authenticate_stream(request: Request) -> tuple[AuthServices, Principal, StreamClaims]:
    """Cookie luồng → `Principal` (B4-01 [6] bước 2); thiếu, hỏng hay phiên chết → 401."""
    services = AuthServices(request.app)
    token = request.cookies.get(STREAM_COOKIE)
    if not token:
        raise UNAUTHENTICATED.error()
    claims = verify_stream_token(services, token)
    principal = await check_session(services, user_id=claims.user_id, sid=claims.sid, ver=claims.ver)
    return services, principal, claims


async def _take_slot(slots: asyncio.Semaphore) -> bool:
    """Lấy một chỗ toàn cục **không chờ**: hết chỗ phải thành 429 ngay, không treo request.

    `acquire()` trả về mà không nhường vòng sự kiện khi còn chỗ, nên giữa `locked()` và
    `acquire()` không ai chen được (asyncio chạy một luồng).
    """
    if slots.locked():
        return False
    await slots.acquire()
    return True


async def _open_slot(request: Request, spec: StreamRequest, provider: StreamProvider, conn_id: str) -> StreamContext:
    """Giữ chỗ toàn cục **và** một kết nối của pool SSE; hết chỗ → 429 `RATE_LIMITED`."""
    app = request.app
    settings = get_stream_settings()
    if not await _take_slot(app.state.stream_slots):
        raise RATE_LIMITED.error(retry_after=RETRY_AFTER_S)
    client: Redis = Redis(connection_pool=app.state.stream_pool, single_connection_client=True)
    try:
        await client.initialize()
    except BaseException:
        app.state.stream_slots.release()
        raise
    return StreamContext(
        app=app,
        spec=spec,
        provider=provider,
        settings=settings,
        client=client,
        bus=EventBus(client),
        conn_id=conn_id,
        ttl_ms=_slot_ttl_ms(settings),
    )


async def _reserve_or_429(request: Request, spec: StreamRequest, conn_id: str, settings: StreamSettings) -> None:
    """Giữ chỗ của người dùng ở ZSET; chạm `STREAM_MAX_PER_USER` → 429 `RATE_LIMITED`."""
    clock: Clock = request.app.state.clock
    reserved = await connections.reserve(
        request.app.state.cache_redis,
        spec.principal.user_id,
        conn_id,
        now_ms=_now_ms(clock),
        ttl_ms=_slot_ttl_ms(settings),
        limit=settings.stream_max_per_user,
    )
    if not reserved:
        raise RATE_LIMITED.error(retry_after=RETRY_AFTER_S)


async def _with_released_slot(
    request: Request, spec: StreamRequest, provider: StreamProvider, conn_id: str
) -> StreamContext:
    """`_open_slot`, nhưng trả lại chỗ của người dùng khi bước toàn cục hỏng."""
    try:
        return await _open_slot(request, spec, provider, conn_id)
    except BaseException:
        await connections.release(request.app.state.cache_redis, spec.principal.user_id, conn_id)
        raise


async def open_stream(request: Request, spec: StreamRequest) -> StreamingResponse:
    """Đường mở luồng sau khi router đã kiểm `Origin`, cookie và mẫu id (B4-01 [6]).

    Thứ tự còn lại: quyền → giữ chỗ của người dùng → giữ chỗ toàn cục → vị trí bắt đầu →
    `StreamingResponse`. Hỏng ở bước nào thì trả lại đúng những gì đã giữ tới đó, vì sau
    khi response ra thì chủ sở hữu là `finally` của generator.
    """
    app = request.app
    provider = cast("Mapping[StreamKind, StreamProvider]", app.state.stream_registry)[spec.kind]
    if provider.policy is not None:
        await provider.policy.authorize(spec.principal, spec.params, app.state.sessionmaker)
    settings = get_stream_settings()
    # `packages.core.ids` chỉ phơi `new_id(<tiền tố>)`, không có bản ULID trần, nên member của
    # ZSET mang tiền tố `tok_`; nó chỉ cần duy nhất trong một khoá, không ai tra ngược nó.
    conn_id = new_id("tok", app.state.clock)
    await _reserve_or_429(request, spec, conn_id, settings)
    ctx = await _with_released_slot(request, spec, provider, conn_id)
    try:
        start = await resolve_start(ctx, spec.last_event_id)
    except BaseException:
        await _close(ctx, SETUP_FAILED)
        raise
    # Từ đây tới byte đầu tiên, chủ sở hữu vẫn chưa phải generator: `AppRoute._finish`
    # (idempotency → commit → chờ callback) còn chạy **sau** handler, và nó ném là response
    # bị bỏ, `stream_body` không bao giờ chạy. `StreamRoute` của router gọi `release_held`
    # trên chính `request` này để trả cả ba thứ (NO-156).
    setattr(request.state, HELD_ATTR, ctx)
    return StreamingResponse(stream_body(ctx, start), media_type=SSE_MEDIA_TYPE, headers=SSE_HEADERS)


async def release_held(request: Request) -> None:
    """Trả tài nguyên của một luồng mà response của nó không bao giờ ra dây (NO-156).

    Idempotent và an toàn khi không có gì để trả: `StreamRoute` gọi nó trên **mọi** ngoại lệ
    của route luồng, kể cả những lượt hỏng trước khi `open_stream` giữ được gì. Không đụng
    với `stream_body`: hai đường loại trừ nhau — generator chỉ chạy khi response đã ra dây,
    còn hàm này chỉ chạy khi nó không bao giờ ra.
    """
    ctx = getattr(request.state, HELD_ATTR, None)
    if not isinstance(ctx, StreamContext):
        return
    setattr(request.state, HELD_ATTR, None)
    await _close(ctx, SETUP_FAILED)


async def resolve_start(ctx: StreamContext, last_event_id: str | None) -> StartPosition:
    """Vị trí bắt đầu, tính **trước** byte đầu (B4-01 [6] "Vị trí bắt đầu").

    `lastEventId` chỉ được dùng khi nó đúng mẫu, chưa bị `MAXLEN` cắt **và** không lớn
    hơn đuôi stream — một id bịa lớn hơn đuôi sẽ làm luồng im lặng vĩnh viễn nếu tin theo.
    """
    tail = await ctx.bus.tail_id(ctx.spec.stream) or FIRST_ID
    if (
        last_event_id is not None
        and is_event_id(last_event_id)
        and event_id_key(last_event_id) <= event_id_key(tail)
        and not await ctx.bus.is_trimmed(ctx.spec.stream, last_event_id)
    ):
        return StartPosition(cursor=last_event_id)
    source = ctx.provider.snapshot
    if source is None:
        return StartPosition(cursor=tail)  # luồng thông báo: không ảnh chụp, không phát lại (K32)
    return await _snapshot_start(ctx, source, tail)


async def _snapshot_start(ctx: StreamContext, source: SnapshotProvider, tail: str) -> StartPosition:
    """Khung ảnh chụp mang `id` = đuôi stream (S08); ảnh chụp sai `event_model` → đóng luồng.

    Nhận `source` làm tham số chứ không đọc lại `ctx.provider.snapshot`: người gọi đã biết
    nó khác `None`, nên hàm không phải mang một nhánh không bao giờ chạy để mypy yên lòng.
    """
    data = await source.snapshot(ctx.spec.principal, ctx.spec.params, ctx.app.state.sessionmaker)
    try:
        ctx.provider.event_model.model_validate(data)
    except ValidationError as exc:
        _log.warning("stream_snapshot_invalid", extra={"stream": ctx.spec.stream, "errors": _error_marks(exc)})
        return StartPosition(cursor=tail, ok=False)
    return StartPosition(cursor=tail, opening=frame(tail, data))


def _event_chunk(ctx: StreamContext, event: Event) -> str | None:
    """Khung của một sự kiện, hay `None` khi nó sai `event_model` (bỏ sự kiện, giữ luồng)."""
    try:
        ctx.provider.event_model.model_validate(event.data)
    except ValidationError as exc:
        _log.warning(
            "stream_event_invalid",
            extra={"stream": ctx.spec.stream, "eventId": event.id, "errors": _error_marks(exc)},
        )
        return None
    return frame(event.id, event.data)


def _recheck_delay(recheck_s: float) -> float:
    """Chu kỳ recheck lệch ngẫu nhiên ±20 %: hàng nghìn luồng không cùng hỏi DB một nhịp."""
    return recheck_s * _jitter.uniform(1 - RECHECK_JITTER, 1 + RECHECK_JITTER)


async def _still_allowed(ctx: StreamContext, state: _LoopState) -> bool:
    """Tới kỳ thì kiểm lại phiên và quyền; mất quyền → đóng luồng, không gửi gì (S07).

    `check_session` ném cả khi Postgres hay Redis hỏng: đóng luồng ở đó cũng đúng, vì FE
    tự nối lại và lượt sau sẽ gặp hệ thống đã hồi phục.
    """
    now = monotonic()
    if now < state.next_recheck:
        return True
    state.next_recheck = now + _recheck_delay(ctx.settings.stream_recheck_s)
    spec = ctx.spec
    try:
        principal = await check_session(
            spec.services, user_id=spec.claims.user_id, sid=spec.claims.sid, ver=spec.claims.ver
        )
        if ctx.provider.policy is not None:
            await ctx.provider.policy.authorize(principal, spec.params, ctx.app.state.sessionmaker)
    except AppError as exc:
        # Postgres hay redis-cache hỏng cũng ném `AppError` qua `_load_snapshot`; gọi nó là
        # `revoked` thì một sự cố hạ tầng hiện lên log y hệt một lượt thu hồi quyền (OBS-04).
        state.reason = DEPENDENCY_ERROR if exc.code is DEPENDENCY_UNAVAILABLE else REVOKED
        return False
    return True


async def _read(ctx: StreamContext, state: _LoopState) -> list[Event] | None:
    """Một lượt `XREAD BLOCK`; `None` = Redis streams hỏng (đóng luồng, FE nối lại)."""
    try:
        return await ctx.bus.read_after(
            ctx.spec.stream,
            state.cursor,
            block_ms=ctx.settings.stream_read_block_ms,
            count=ctx.settings.stream_read_count,
        )
    except (AppError, RedisError):
        _log.warning("stream_redis_error", extra={"stream": ctx.spec.stream})
        state.reason = REDIS_ERROR
        return None


async def _keep_slot(ctx: StreamContext, state: _LoopState) -> None:
    """Gia hạn chỗ mỗi `STREAM_HEARTBEAT_S / 2` **theo đồng hồ tường**, không theo nhịp ping.

    Luồng bận không bao giờ ping, nên buộc nhịp gia hạn vào ping là để mục ZSET của chính
    những người dùng tích cực nhất rụng trước.
    """
    now = monotonic()
    if now < state.next_refresh:
        return
    state.next_refresh = now + ctx.settings.stream_heartbeat_s / 2
    await connections.refresh(
        ctx.cache, ctx.spec.principal.user_id, ctx.conn_id, now_ms=_now_ms(ctx.clock), ttl_ms=ctx.ttl_ms
    )


async def _pump(ctx: StreamContext, state: _LoopState) -> AsyncIterator[str]:
    """Vòng phát: kiểm quyền → đọc → phát → gia hạn chỗ → heartbeat, tới khi có lý do đóng."""
    heartbeat_s = ctx.settings.stream_heartbeat_s
    while True:
        if not await _still_allowed(ctx, state):
            return
        events = await _read(ctx, state)
        if events is None:
            return
        for event in events:
            state.cursor = event.id
            chunk = _event_chunk(ctx, event)
            if chunk is not None:
                state.last_sent = monotonic()
                yield chunk
        await _keep_slot(ctx, state)
        if monotonic() - state.last_sent >= heartbeat_s:
            state.last_sent = monotonic()
            yield PING


async def stream_body(ctx: StreamContext, start: StartPosition) -> AsyncIterator[str]:
    """Thân của `StreamingResponse`: khung mở (nếu có) rồi vòng phát, dọn trong `finally`."""
    now = monotonic()
    state = _LoopState(
        cursor=start.cursor,
        last_sent=now,
        next_recheck=now + _recheck_delay(ctx.settings.stream_recheck_s),
        next_refresh=now + ctx.settings.stream_heartbeat_s / 2,
    )
    try:
        if start.opening is not None:
            yield start.opening
        if not start.ok:
            state.reason = SNAPSHOT_INVALID
            return
        async for chunk in _pump(ctx, state):
            yield chunk
    finally:
        await _close(ctx, state.reason)


async def _close(ctx: StreamContext, reason: str) -> None:
    """Trả chỗ ZSET, trả kết nối về pool SSE, ghi `stream_closed` (S05).

    Chắn huỷ (`shield=True`) vì client rớt là đường **thường**, không phải ngoại lệ.

    Thứ tự bên trong quan trọng: chỉ `ZREM` — lời gọi **mạng** tới `redis-cache` — mới nằm
    dưới trần 1 giây; trả kết nối về pool đứng ngoài trần. `Redis.aclose(close_connection_pool=False)`
    chỉ đẩy kết nối lại vào danh sách rỗi của pool, không đi mạng, nên nó không treo được;
    đổi lại, một `redis-cache` chậm không bao giờ cướp mất chỗ của pool SSE. Gói cả hai vào
    một `move_on_after` như bản trước thì lượt hết giờ ở `ZREM` sẽ bỏ luôn bước trả kết nối
    trong khi chỗ semaphore vẫn được trả — pool cạn dần mà bộ đếm chỗ vẫn báo còn trống.

    Chỗ của semaphore trả trong `finally`: `aclose()` **có thể** ném (pool đang đóng lúc app
    dừng), và một chỗ rò ở đây rò vĩnh viễn trong cả đời tiến trình (RES-02). Bộ đếm là
    `BoundedSemaphore`, nên một lượt trả dư sẽ ném `ValueError` ngay thay vì âm thầm nới trần.
    """
    with anyio.CancelScope(shield=True):
        try:
            with anyio.move_on_after(CLEANUP_TIMEOUT_S):
                await connections.release(ctx.cache, ctx.spec.principal.user_id, ctx.conn_id)
            await ctx.client.aclose(close_connection_pool=False)
        finally:
            ctx.app.state.stream_slots.release()
            _log_closed(ctx.spec.stream, reason)


def _log_closed(stream: str, reason: str) -> None:
    """Ghi `stream_closed` kèm lý do qua `bind_log_context`, rồi gỡ ngữ cảnh khỏi task."""
    token = bind_log_context(stream=stream, reason=reason)
    try:
        _log.info("stream_closed")
    finally:
        token.var.reset(token)
