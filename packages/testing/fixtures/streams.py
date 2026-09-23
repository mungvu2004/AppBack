"""Fixture luồng SSE (B4-01): lái ASGI tay để kiểm route `apps/api/streams` thật.

`httpx.ASGITransport` (0.28.1) chờ app chạy **xong** mới trả response và chỉ gửi
`http.disconnect` sau khi response xong — không dùng được cho luồng vô hạn hay để giả
client rớt. `sse_open` tự dựng `scope` HTTP và chạy `app(scope, receive, send)` trong
một task riêng, lái bằng hai hàng đợi.

Phần lái ASGI không nhập gì từ `apps.api.streams` — nó chỉ nói ASGI thuần. Phần cuối file
(`stream_app`, `signed_stream_user`) là giàn dựng app thật cho test route của việc C: nó phải
biết `reset_stream_settings_cache` vì router đọc `STREAM_*` **một lần** lúc `lifespan`.
"""

import asyncio
import json
from collections.abc import AsyncIterator, Callable, Iterator, Mapping, Sequence
from contextlib import AbstractAsyncContextManager, AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from time import monotonic
from typing import Final
from urllib.parse import urlencode

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.applications import Starlette
from starlette.types import Message, Scope

from apps.api.auth.cookies import STREAM_COOKIE
from apps.api.core import extensions
from apps.api.core.app import create_app
from apps.api.streams.settings import reset_stream_settings_cache
from packages.core.clock import SystemClock
from packages.core.ids import new_id
from packages.core.instants import to_wire
from packages.core.settings import get_core_settings
from packages.db.models.auth import User
from packages.messaging.streams import EventBus, upload_stream, user_stream
from packages.testing.factories.auth import make_user
from packages.testing.fixtures.api import API_RESPONSE_OBSERVERS, BASE_URL, ObservedClient
from packages.testing.fixtures.auth import SignedIn, sign_in
from packages.testing.fixtures.clock import FakeClock
from packages.testing.golden.recorder import record_stream_event
from packages.testing.golden.sse import SseFrame, parse_sse

_OPEN_TIMEOUT_S: Final = 5.0
"""Trần chờ `http.response.start` và, với lỗi, thân đầy đủ (mục 6 của prompt)."""

_DISCONNECT_TIMEOUT_S: Final = 5.0
"""Trần chờ task app thoát sau khi `disconnect()` gửi `http.disconnect`."""

_EVENT_STREAM: Final = "text/event-stream"

_POLL_TICK_S: Final = 0.2
"""Lát chờ tối đa mỗi lượt `_pull`, để vòng lặp của người gọi tự kiểm hạn riêng đều đặn
(không thì `_pull` ăn hết cả `timeout_s` và thông điệp lỗi riêng của người gọi không bao giờ nổi lên)."""


def _is_event_stream(headers: httpx.Headers) -> bool:
    """Content-type có phải `text/event-stream` — quyết định đọc thân hay lái luồng."""
    return bool(headers.get("content-type", "").startswith(_EVENT_STREAM))


class _Receiver:
    """`receive` ASGI: trả `http.request` rỗng một lần, sau đó chặn tới khi `disconnect()`."""

    def __init__(self) -> None:
        """Chưa gửi `http.request`, chưa có ai gọi `disconnect()`."""
        self._sent_request = False
        self._disconnect_event: Final = asyncio.Event()

    async def __call__(self) -> Message:
        """Một `http.request` thân rỗng, rồi chặn tới `disconnect()` → `http.disconnect`."""
        if not self._sent_request:
            self._sent_request = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await self._disconnect_event.wait()
        return {"type": "http.disconnect"}

    def disconnect(self) -> None:
        """Đánh dấu client rớt — lần `receive()` kế tiếp trả `http.disconnect`."""
        self._disconnect_event.set()


def _build_scope(
    path: str,
    query: Mapping[str, str] | None,
    cookies: Mapping[str, str] | None,
    headers: Mapping[str, str] | None,
) -> Scope:
    """`scope` HTTP GET tối thiểu: `cookie` ghép từ `cookies`, `host: testserver`, scheme `https`."""
    header_list: list[tuple[bytes, bytes]] = [(b"host", b"testserver")]
    for name, value in (headers or {}).items():
        header_list.append((name.lower().encode("latin-1"), value.encode("latin-1")))
    if cookies:
        cookie_header = "; ".join(f"{name}={value}" for name, value in cookies.items())
        header_list.append((b"cookie", cookie_header.encode("latin-1")))
    return {
        "type": "http",
        # `spec_version` < 2.4: Starlette `StreamingResponse` huỷ qua vòng lặp lắng `receive()`
        # (task group), không phải qua `OSError` khi `send()` thất bại (giao thức 2.4) — `send`
        # của fixture chỉ đẩy vào hàng đợi, không bao giờ ném `OSError`, nên phải khai phiên bản cũ.
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": urlencode(query or {}, doseq=True).encode("ascii"),
        "root_path": "",
        "headers": header_list,
        "client": ("127.0.0.1", 0),
        "server": ("testserver", 443),
    }


class SseStream:
    """Một luồng SSE đang mở, lái bằng ASGI thô (không qua `httpx.ASGITransport`)."""

    status: int
    headers: httpx.Headers
    body: bytes
    closed: bool

    def __init__(self, app_task: "asyncio.Task[None]", receiver: _Receiver, queue: "asyncio.Queue[Message]") -> None:
        """Trạng thái ban đầu — `status`/`headers`/`body` được điền bởi `_await_start`."""
        self._app_task = app_task
        self._receiver = receiver
        self._queue = queue
        self.status = 0
        self.headers = httpx.Headers()
        self.body = b""
        self.closed = False
        self._disconnected = False
        self._raw = b""
        self._delivered = 0

    async def _pull(self, timeout_s: float) -> Message | None:
        """Message ASGI kế tiếp trong `timeout_s`, `None` nếu hết hạn; ném lỗi nếu app đã hỏng/thoát."""
        get_task: asyncio.Task[Message] = asyncio.ensure_future(self._queue.get())
        try:
            done, _pending = await asyncio.wait(
                {get_task, self._app_task}, timeout=timeout_s, return_when=asyncio.FIRST_COMPLETED
            )
        except asyncio.CancelledError:
            get_task.cancel()
            raise
        if get_task in done:
            return get_task.result()
        get_task.cancel()
        if self._app_task in done:
            exc = self._app_task.exception()
            if exc is not None:
                raise exc
            raise RuntimeError("app ASGI kết thúc mà không gửi thêm message SSE")
        return None

    async def _drain_one(self, timeout_s: float) -> None:
        """Kéo một message `http.response.body` nếu có trong `timeout_s`; gộp vào `_raw`, đánh dấu `closed`."""
        message = await self._pull(min(timeout_s, _POLL_TICK_S))
        if message is not None and message.get("type") == "http.response.body":
            self._raw += bytes(message.get("body") or b"")
            if not message.get("more_body", False):
                self.closed = True

    async def _await_start(self, timeout_s: float) -> None:
        """Chờ `http.response.start`; nếu không phải luồng thì đọc hết thân vào `body`."""
        deadline = monotonic() + timeout_s
        message: Message | None = None
        while message is None:
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise TimeoutError(f"quá hạn {timeout_s}s chờ http.response.start")
            message = await self._pull(min(remaining, _POLL_TICK_S))
        if message.get("type") != "http.response.start":
            raise RuntimeError(f"ASGI app gửi message lạ trước http.response.start: {message!r}")
        self.status = int(message["status"])
        self.headers = httpx.Headers(
            [(k.decode("latin-1"), v.decode("latin-1")) for k, v in message.get("headers", [])]
        )
        if _is_event_stream(self.headers):
            return
        while not self.closed:
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise TimeoutError(f"quá hạn {timeout_s}s đọc thân lỗi; đã nhận: {self._raw!r}")
            await self._drain_one(remaining)
        self.body = self._raw

    async def next_frames(self, n: int, timeout_s: float = 2.0) -> list[SseFrame]:
        """`n` khung có `data` kế tiếp (bỏ khung chỉ chú thích), không lặp giữa các lần gọi."""
        deadline = monotonic() + timeout_s
        while True:
            data_frames = [frame for frame in parse_sse(self._raw) if frame.data]
            pending = data_frames[self._delivered :]
            if len(pending) >= n:
                self._delivered += n
                return pending[:n]
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise TimeoutError(f"quá hạn {timeout_s}s chờ {n} khung SSE; đã nhận: {self._raw!r}")
            await self._drain_one(remaining)

    async def raw_until(self, predicate: Callable[[bytes], bool], timeout_s: float = 2.0) -> bytes:
        """Toàn bộ byte đã nhận, chờ tới khi `predicate` đúng."""
        deadline = monotonic() + timeout_s
        while not predicate(self._raw):
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise TimeoutError(f"quá hạn {timeout_s}s chờ điều kiện; đã nhận: {self._raw!r}")
            await self._drain_one(remaining)
        return self._raw

    async def disconnect(self) -> None:
        """Gửi `http.disconnect` (nếu chưa) rồi chờ task app thoát, có trần thời gian."""
        self._disconnected = True
        self._receiver.disconnect()
        try:
            await asyncio.wait_for(asyncio.shield(self._app_task), timeout=_DISCONNECT_TIMEOUT_S)
        except TimeoutError:
            self._app_task.cancel()
            raise

    async def wait_closed(self, timeout_s: float) -> float:
        """Chờ server tự đóng (`closed`), trả số giây đã chờ (S07)."""
        start = monotonic()
        deadline = start + timeout_s
        while not self.closed:
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise TimeoutError(f"luồng không tự đóng trong {timeout_s}s")
            await self._drain_one(remaining)
        return monotonic() - start


def _notify_observers(
    request: pytest.FixtureRequest, path: str, query: Mapping[str, str] | None, stream: SseStream
) -> None:
    """Đưa response dựng lại (theo `status`/`headers`, thân của luồng 200 là rỗng) cho mọi observer."""
    url = httpx.URL(BASE_URL + path, params=dict(query or {}))
    http_request = httpx.Request("GET", url)
    content = b"" if _is_event_stream(stream.headers) else stream.body
    response = httpx.Response(stream.status, headers=stream.headers, content=content, request=http_request)
    for observer in request.node.config.stash.get(API_RESPONSE_OBSERVERS, []):
        observer(request.node, response)


@asynccontextmanager
async def _open_stream(
    request: pytest.FixtureRequest,
    app: Starlette,
    path: str,
    query: Mapping[str, str] | None,
    cookies: Mapping[str, str] | None,
    headers: Mapping[str, str] | None,
) -> AsyncIterator[SseStream]:
    """Dựng `scope`, chạy `app` trong task riêng, chờ status rồi trao `SseStream`; dọn khi thoát."""
    scope = _build_scope(path, query, cookies, headers)
    receiver = _Receiver()
    queue: asyncio.Queue[Message] = asyncio.Queue()

    async def send(message: Message) -> None:
        await queue.put(message)

    app_task: asyncio.Task[None] = asyncio.ensure_future(app(scope, receiver, send))
    stream = SseStream(app_task, receiver, queue)
    started = False
    try:
        await stream._await_start(_OPEN_TIMEOUT_S)
        started = True
    finally:
        if not started and not app_task.done():
            app_task.cancel()
    _notify_observers(request, path, query, stream)
    try:
        yield stream
    finally:
        if not stream._disconnected:
            await stream.disconnect()


type SseOpen = Callable[..., AbstractAsyncContextManager[SseStream]]


@pytest_asyncio.fixture(loop_scope="function")
async def sse_open(request: pytest.FixtureRequest) -> AsyncIterator[SseOpen]:
    """`open(app, path, *, query=None, cookies=None, headers=None)`: mở một luồng SSE thật qua ASGI.

    Vào `lifespan` của `app` tự động (một lần cho mỗi app trong test) nếu nó chưa qua —
    dò bằng `hasattr(app.state, "sessionmaker")` (B0-06 gắn nó trong `lifespan`); thoát ở
    teardown fixture, cùng vòng sự kiện với test (R-06: không viết lại `make_api_client`,
    chỉ tái dùng `app.router.lifespan_context`).
    """
    async with AsyncExitStack() as stack:
        entered: set[int] = set()

        @asynccontextmanager
        async def do_open(
            app: Starlette,
            path: str,
            *,
            query: Mapping[str, str] | None = None,
            cookies: Mapping[str, str] | None = None,
            headers: Mapping[str, str] | None = None,
        ) -> AsyncIterator[SseStream]:
            """Một luồng mở; vào `lifespan` của `app` trước, nếu cần."""
            if id(app) not in entered:
                if not hasattr(app.state, "sessionmaker"):
                    await stack.enter_async_context(app.router.lifespan_context(app))
                entered.add(id(app))
            async with _open_stream(request, app, path, query, cookies, headers) as stream:
                yield stream

        yield do_open


def stream_cookie(signed: SignedIn) -> dict[str, str]:
    """`{"appback_stream": <token>}` của một người đã `sign_in` (login + refresh xoay cookie luồng)."""
    return {STREAM_COOKIE: signed.client.cookies[STREAM_COOKIE]}


def sample_progress(upload_id: str, **overrides: object) -> dict[str, object]:
    """Dữ liệu `Progress` hợp lệ theo `ProgressSchema` (FE), `id` mặc định là `upload_id`."""
    data: dict[str, object] = {
        "id": upload_id,
        "progressPercent": 50,
        "status": "running",
        "step": "processing",
    }
    data.update(overrides)
    return data


def sample_notification(**overrides: object) -> dict[str, object]:
    """Dữ liệu `Notification` hợp lệ theo `NotificationSchema` (FE), id sinh mới mỗi lần gọi."""
    clock = SystemClock()
    data: dict[str, object] = {
        "createdAt": to_wire(clock.now()),
        "id": new_id("ntf", clock),
        "isRead": False,
        "kind": "aiCompleted",
        "message": "AI đã xử lý xong bản vẽ tầng trệt",
        "objectLabel": "Tường ngoài",
        "place": "walls",
        "projectId": new_id("prj", clock),
        "projectName": "Dự án mẫu",
    }
    data.update(overrides)
    return data


async def publish_progress(bus: EventBus, upload_id: str, data: Mapping[str, object] | None = None) -> str:
    """`XADD` một sự kiện tiến độ (mặc định `sample_progress`) vào stream của `upload_id`, trả id."""
    return await bus.publish(upload_stream(upload_id), data if data is not None else sample_progress(upload_id))


async def publish_notification(bus: EventBus, user_id: str, data: Mapping[str, object] | None = None) -> str:
    """`XADD` một sự kiện thông báo (mặc định `sample_notification`) vào stream của `user_id`, trả id."""
    return await bus.publish(user_stream(user_id), data if data is not None else sample_notification())


def record_stream_frames(op: str, case: str, frames: Sequence[SseFrame]) -> None:
    """`record_stream_event(op, case, json.loads(frame.data))` cho từng khung **đã nhận** (H5)."""
    for frame in frames:
        record_stream_event(op, case, json.loads(frame.data))


# ---------------------------------------------------------------------------
# Giàn dựng app thật cho test route SSE (việc C của B4-01)
# ---------------------------------------------------------------------------

FAKE_PROVIDERS_MODULE: Final = "apps.api.fake.stream_providers"
"""Nhãn module của `extensions.override` — chỉ hiện trong thông báo lỗi, không ai nhập nó."""

PROVIDERS_SUBMODULE: Final = "stream_providers"

type StreamAppFactory = Callable[..., FastAPI]


@pytest.fixture
def stream_app(auth_env: None, fake_clock: FakeClock, monkeypatch: pytest.MonkeyPatch) -> Iterator[StreamAppFactory]:
    """`build(providers=(), **stream_env)` → app thật, nhà cung cấp giả đã cắm, **trước** `lifespan`.

    Hai thứ bắt buộc xảy ra trước `lifespan`: biến môi trường `STREAM_*` (router đọc
    `get_stream_settings()` một lần lúc khởi động để dựng pool và bộ đếm chỗ toàn cục) và
    `extensions.override` (sổ nhà cung cấp cũng dựng trong `lifespan`). Vì vậy test gọi
    factory này **rồi** mới `signed_stream_user(app, …)` hay `sse_open(app, …)`.
    """

    def build(providers: Sequence[object] = (), **stream_env: str) -> FastAPI:
        """Một app mới; `stream_env` nhận khoá `STREAM_*` viết thường (`stream_heartbeat_s="0.1"`)."""
        for name, value in stream_env.items():
            monkeypatch.setenv(name.upper(), value)
        reset_stream_settings_cache()
        app = create_app(get_core_settings(), clock=fake_clock)
        if providers:
            extensions.override(app, PROVIDERS_SUBMODULE, [(FAKE_PROVIDERS_MODULE, tuple(providers))])
        return app

    yield build
    reset_stream_settings_cache()


@dataclass(frozen=True, slots=True)
class StreamUser:
    """Người dùng đã đăng nhập thật trên một app luồng, cùng client REST của lượt đó."""

    user: User
    signed: SignedIn

    @property
    def cookies(self) -> dict[str, str]:
        """Cookie luồng của người này — tham số `cookies=` của `sse_open`."""
        return stream_cookie(self.signed)

    @property
    def client(self) -> httpx.AsyncClient:
        """Client REST giữ cookie refresh (S09 gọi lại `/api/auth/refresh` trên nó)."""
        return self.signed.client


@asynccontextmanager
async def signed_stream_user(
    app: FastAPI, db: AsyncSession, *, role: str = "engineer", status: str = "active"
) -> AsyncIterator[StreamUser]:
    """Client ASGI của `app` và một người dùng mới đã `sign_in` thật.

    Đây là lối **duy nhất** lấy cookie luồng trong test: nó do chính lượt
    `POST /api/auth/refresh` cấp, nên không test nào tự ký token luồng (S09 kiểm đúng đường đó).

    `lifespan` chỉ vào **một lần cho mỗi app** (dò bằng `app.state.sessionmaker`, như
    `sse_open`): test nào cần nhiều người dùng trên cùng một app — trần chỗ toàn cục, "không
    giữ kết nối Postgres" — lồng nhiều lượt gọi, và lượt thứ hai trở đi chỉ thêm client.
    Vào `lifespan` hai lần sẽ thay `app.state` giữa chừng (engine, pool SSE, bộ đếm chỗ),
    làm chính thứ đang đo biến mất.
    """
    async with AsyncExitStack() as stack:
        if not hasattr(app.state, "sessionmaker"):
            await stack.enter_async_context(app.router.lifespan_context(app))
        client = await stack.enter_async_context(
            ObservedClient(transport=httpx.ASGITransport(app=app), base_url=BASE_URL)
        )
        user = await make_user(db, role=role, status=status)
        yield StreamUser(user=user, signed=await sign_in(client, user))
