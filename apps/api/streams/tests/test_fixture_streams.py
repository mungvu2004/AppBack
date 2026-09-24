"""Kiểm `packages/testing/fixtures/streams.py` trên một app ASGI SSE tối thiểu tự khai (B4-01).

Không nhập `apps.api.streams` (chưa tồn tại ở nhánh này) — app thử ở đây là Starlette
thuần, độc lập với bản hiện thực thật của route SSE.
"""

import asyncio
import contextlib
import json
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Final

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route
from starlette.types import Receive, Scope, Send

from packages.core.ids import is_id
from packages.messaging.streams import EventBus, upload_stream, user_stream
from packages.testing.factories.auth import make_user
from packages.testing.fixtures import streams as streams_fixture
from packages.testing.fixtures.api import API_RESPONSE_OBSERVERS
from packages.testing.fixtures.auth import SignIn
from packages.testing.fixtures.streams import (
    SseOpen,
    publish_notification,
    publish_progress,
    record_stream_frames,
    sample_notification,
    sample_progress,
    stream_cookie,
)
from packages.testing.golden import recorder
from packages.testing.golden.sse import SseFrame

# -- App ASGI SSE tối thiểu, khai ngay trong file --------------------------------------------------


def _frame(event_id: int, data: dict[str, object]) -> bytes:
    """Một khung SSE hợp lệ: `id:`/`data:`, không `event:` (K03)."""
    return f"id: {event_id}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n".encode()


class StreamApp(Starlette):
    """App thử: nhớ khi `receive()` trả `http.disconnect` (S05) qua `disconnect_seen`."""

    disconnect_seen: asyncio.Event


type Endpoint = Callable[[Request], Awaitable[Response]]

HANG_S: Final = 3600.0
"""Chờ "vô hạn" của app thử: đủ lâu để chỉ `http.disconnect` mới kết thúc được luồng."""

PING_EVERY_S: Final = 0.02


def _sse(chunks: AsyncIterator[bytes]) -> StreamingResponse:
    """Response SSE của app thử (media type đúng để fixture nhận ra luồng)."""
    return StreamingResponse(chunks, media_type="text/event-stream")


def _hang_endpoint(disconnect_seen: asyncio.Event) -> Endpoint:
    """`GET /stream/hang/{n}`: N khung rồi treo — chỉ client rớt mới kết thúc được (S02, S05)."""

    async def stream_hang(request: Request) -> Response:
        """Luồng vô hạn; generator bị huỷ thì đánh dấu `disconnect_seen`."""
        n = int(request.path_params["n"])

        async def chunks() -> AsyncIterator[bytes]:
            """N khung rồi chờ mãi."""
            try:
                for i in range(1, n + 1):
                    yield _frame(i, {"n": i})
                await asyncio.sleep(HANG_S)
            except asyncio.CancelledError:
                disconnect_seen.set()
                raise

        return _sse(chunks())

    return stream_hang


def _ping_endpoint(disconnect_seen: asyncio.Event) -> Endpoint:
    """`GET /stream/ping`: chỉ gửi `: ping` — khung không có `data` (S04)."""

    async def stream_ping(_request: Request) -> Response:
        """Ping đều đặn tới khi client rớt."""

        async def chunks() -> AsyncIterator[bytes]:
            """`: ping` mỗi `PING_EVERY_S`."""
            try:
                while True:
                    yield b": ping\n\n"
                    await asyncio.sleep(PING_EVERY_S)
            except asyncio.CancelledError:
                disconnect_seen.set()
                raise

        return _sse(chunks())

    return stream_ping


async def stream_close(request: Request) -> Response:
    """`GET /stream/close/{n}`: N khung rồi server tự đóng (S07 nhìn từ phía client)."""

    async def chunks() -> AsyncIterator[bytes]:
        """N khung rồi hết."""
        for i in range(1, int(request.path_params["n"]) + 1):
            yield _frame(i, {"n": i})

    return _sse(chunks())


async def stream_crash(_request: Request) -> Response:
    """`GET /stream/crash`: một khung rồi generator ném — fixture phải nổi lỗi, không nuốt."""

    async def chunks() -> AsyncIterator[bytes]:
        """Một khung rồi `RuntimeError`."""
        yield _frame(1, {"n": 1})
        raise RuntimeError("boom")

    return _sse(chunks())


async def error_401(_request: Request) -> Response:
    """`GET /error/401`: thân W7 chứ không phải luồng — fixture phải đọc hết thân."""
    return JSONResponse({"code": "UNAUTHENTICATED", "requestId": "rid-0000000001"}, status_code=401)


@asynccontextmanager
async def _fake_lifespan(app: Starlette) -> AsyncIterator[None]:
    """`app.state.sessionmaker` giả (B0-06 gắn cái thật) — chỉ để kiểm fixture tự vào lifespan."""
    app.state.sessionmaker = object()
    yield


def build_stream_app() -> StreamApp:
    """Năm đường: N khung rồi treo; N khung rồi tự đóng; chỉ `: ping`; lỗi 401 JSON; generator ném."""
    disconnect_seen = asyncio.Event()
    app = StreamApp(
        routes=[
            Route("/stream/hang/{n:int}", _hang_endpoint(disconnect_seen)),
            Route("/stream/close/{n:int}", stream_close),
            Route("/stream/ping", _ping_endpoint(disconnect_seen)),
            Route("/error/401", error_401),
            Route("/stream/crash", stream_crash),
        ],
        lifespan=_fake_lifespan,
    )
    app.disconnect_seen = disconnect_seen
    return app


class BrokenStartApp(Starlette):
    """App vi phạm ASGI: gửi `http.response.body` trước `http.response.start` rồi treo."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Message lạ trước `http.response.start` — kiểm fixture bắt được, không nuốt."""
        await send({"type": "http.response.body", "body": b"?", "more_body": True})
        await asyncio.sleep(3600)


@pytest.fixture
def stream_app() -> StreamApp:
    """Một app thử mới mỗi test (không chia sẻ `disconnect_seen` giữa các test)."""
    return build_stream_app()


# -- status/headers, next_frames, raw_until, disconnect, wait_closed, body lỗi ---------------------


async def test_status_and_headers_of_an_open_stream(sse_open: SseOpen, stream_app: StreamApp) -> None:
    """`status`/`headers` có ngay sau khi mở, trước khi đọc khung nào."""
    async with sse_open(stream_app, "/stream/close/1") as stream:
        assert stream.status == 200
        assert stream.headers["content-type"].startswith("text/event-stream")
        assert stream.body == b""


async def test_next_frames_orders_and_never_repeats(sse_open: SseOpen, stream_app: StreamApp) -> None:
    """5 khung: hai lượt `next_frames` liên tiếp không lặp, không mất, đúng thứ tự."""
    async with sse_open(stream_app, "/stream/hang/5") as stream:
        first = await stream.next_frames(2)
        assert [frame.id for frame in first] == ["1", "2"]
        second = await stream.next_frames(3)
        assert [frame.id for frame in second] == ["3", "4", "5"]
        assert [json.loads(frame.data) for frame in second] == [{"n": 3}, {"n": 4}, {"n": 5}]


async def test_next_frames_skips_comment_only_frames(sse_open: SseOpen, stream_app: StreamApp) -> None:
    """Heartbeat `: ping` xen giữa không được `next_frames` đếm là khung."""
    async with sse_open(stream_app, "/stream/ping") as stream:
        await stream.raw_until(lambda raw: raw.count(b": ping\n\n") >= 2)
        with pytest.raises(TimeoutError, match="quá hạn"):
            await stream.next_frames(1, timeout_s=0.1)


async def test_next_frames_times_out_with_received_bytes_in_message(sse_open: SseOpen, stream_app: StreamApp) -> None:
    """Quá hạn khi thiếu khung → `TimeoutError` kèm byte đã nhận."""
    async with sse_open(stream_app, "/stream/hang/1") as stream:
        with pytest.raises(TimeoutError, match="id: 1"):
            await stream.next_frames(2, timeout_s=0.2)


async def test_raw_until_returns_all_received_bytes(sse_open: SseOpen, stream_app: StreamApp) -> None:
    """`raw_until` trả toàn bộ byte thô đã nhận, không chỉ phần khớp điều kiện."""
    async with sse_open(stream_app, "/stream/ping") as stream:
        raw = await stream.raw_until(lambda data: b": ping" in data)
        assert raw.startswith(b": ping\n\n")


async def test_raw_until_times_out_with_received_bytes_in_message(sse_open: SseOpen, stream_app: StreamApp) -> None:
    """Predicate không bao giờ đúng → `TimeoutError` kèm byte đã nhận (NO-155: nhánh riêng của `raw_until`)."""
    async with sse_open(stream_app, "/stream/hang/1") as stream:
        with pytest.raises(TimeoutError, match="id: 1"):
            await stream.raw_until(lambda _raw: False, timeout_s=0.2)


async def test_disconnect_reaches_the_app_and_ends_its_task(sse_open: SseOpen, stream_app: StreamApp) -> None:
    """`disconnect()` làm app nhận `http.disconnect` (generator huỷ) và task app kết thúc."""
    async with sse_open(stream_app, "/stream/hang/2") as stream:
        await stream.next_frames(2)
        assert not stream_app.disconnect_seen.is_set()
        await stream.disconnect()
        assert stream_app.disconnect_seen.is_set()


async def test_wait_closed_measures_time_until_server_closes(sse_open: SseOpen, stream_app: StreamApp) -> None:
    """Luồng tự đóng (server gửi `more_body=False`) → `closed=True`, `wait_closed` trả số giây đã chờ."""
    async with sse_open(stream_app, "/stream/close/2") as stream:
        assert not stream.closed
        elapsed = await stream.wait_closed(timeout_s=2.0)
        assert stream.closed
        assert elapsed >= 0.0


async def test_wait_closed_times_out_when_stream_never_closes(sse_open: SseOpen, stream_app: StreamApp) -> None:
    """Luồng treo vô hạn → `wait_closed` quá hạn ném `TimeoutError`."""
    async with sse_open(stream_app, "/stream/hang/1") as stream:
        with pytest.raises(TimeoutError, match="không tự đóng"):
            await stream.wait_closed(timeout_s=0.1)


async def test_body_of_an_error_response_is_not_a_stream(sse_open: SseOpen, stream_app: StreamApp) -> None:
    """Lỗi 401 JSON (W7): `content-type` không phải `text/event-stream`, `body` có thân đầy đủ."""
    async with sse_open(stream_app, "/error/401") as stream:
        assert stream.status == 401
        assert not stream.headers["content-type"].startswith("text/event-stream")
        assert json.loads(stream.body) == {"code": "UNAUTHENTICATED", "requestId": "rid-0000000001"}


async def test_fixture_enters_lifespan_when_app_has_not_run_it(sse_open: SseOpen, stream_app: StreamApp) -> None:
    """App chưa qua `lifespan` (không có `sessionmaker`) → fixture tự vào trước khi mở luồng."""
    assert not hasattr(stream_app.state, "sessionmaker")
    async with sse_open(stream_app, "/stream/close/1") as stream:
        assert stream.status == 200
    assert stream_app.state.sessionmaker is not None


async def test_fixture_reuses_an_already_running_lifespan(sse_open: SseOpen, stream_app: StreamApp) -> None:
    """App đã qua `lifespan` sẵn (vd `api_app`) → fixture không vào lần hai, kể cả mở nhiều luồng."""
    async with stream_app.router.lifespan_context(stream_app):
        marker = stream_app.state.sessionmaker
        async with sse_open(stream_app, "/stream/close/1") as stream:
            assert stream.status == 200
        async with sse_open(stream_app, "/stream/close/1") as stream:
            assert stream.status == 200
        assert stream_app.state.sessionmaker is marker


async def test_open_uses_cookies_and_headers_in_the_scope(sse_open: SseOpen, stream_app: StreamApp) -> None:
    """`cookies`/`headers` truyền vào `open()` tới được app qua scope ASGI."""

    async def echo_cookie(request: Request) -> Response:
        """Trả lại hai header mà test quan tâm, dưới dạng thân lỗi 401 (không phải luồng)."""
        return JSONResponse(
            {"cookie": request.headers.get("cookie"), "x_test": request.headers.get("x-test")}, status_code=401
        )

    stream_app.routes.append(Route("/echo", echo_cookie))
    async with sse_open(stream_app, "/echo", cookies={"appback_stream": "tok-1"}, headers={"X-Test": "abc"}) as stream:
        body = json.loads(stream.body)
    assert body == {"cookie": "appback_stream=tok-1", "x_test": "abc"}


async def test_app_errors_after_start_surface_through_wait_closed(sse_open: SseOpen, stream_app: StreamApp) -> None:
    """App hỏng giữa luồng (sau khi đã gửi khung) → lỗi nổi lên qua bất kỳ lệnh chờ nào sau đó."""

    async def run() -> None:
        """Mở luồng hỏng rồi chờ — lỗi của app phải nổi lên từ lệnh chờ."""
        async with sse_open(stream_app, "/stream/crash") as stream:
            await stream.next_frames(1)
            await stream.wait_closed(timeout_s=1.0)

    with pytest.raises(RuntimeError, match="boom"):
        await run()


async def test_cancellation_while_waiting_cleans_up_and_propagates(sse_open: SseOpen, stream_app: StreamApp) -> None:
    """Bị huỷ khi đang chờ khung (vd `wait_for` hết hạn từ ngoài) → dọn `get_task`, lỗi nổi lên."""
    async with sse_open(stream_app, "/stream/hang/1") as stream:
        await stream.next_frames(1)
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(stream.next_frames(5, timeout_s=10), timeout=0.05)


async def test_disconnect_times_out_when_the_app_never_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Task app không thoát kịp trần → `disconnect()` ném `TimeoutError`, không chờ vô hạn.

    Kiểm ở mức thấp (không qua ASGI/Starlette): một task chặn vô hạn trên `asyncio.Event`
    không bao giờ được set — kiểm soát được chính xác lúc nào nó thoát (`cancel()` của
    `disconnect()` chính là thứ khiến nó thoát), không phụ thuộc cách Starlette lan huỷ.
    """
    monkeypatch.setattr(streams_fixture, "_DISCONNECT_TIMEOUT_S", 0.05)
    never = asyncio.Event()

    async def block_forever() -> None:
        """Task app không bao giờ tự thoát: chỉ `cancel()` mới kết thúc được nó."""
        await never.wait()

    app_task: asyncio.Task[None] = asyncio.ensure_future(block_forever())
    stream = streams_fixture.SseStream(app_task, streams_fixture._Receiver(), asyncio.Queue())
    with pytest.raises(TimeoutError):
        await stream.disconnect()
    with contextlib.suppress(asyncio.CancelledError):
        await app_task


async def test_await_start_rejects_a_message_before_http_response_start(sse_open: SseOpen) -> None:
    """App gửi message lạ trước `http.response.start` → `RuntimeError`, task còn treo bị huỷ."""
    broken = BrokenStartApp()
    with pytest.raises(RuntimeError, match="message lạ"):
        async with sse_open(broken, "/bat-ky"):
            pass


class _SilentApp(Starlette):
    """Không gửi message ASGI nào — `_await_start` phải quá hạn chờ `http.response.start` (NO-155)."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Treo vô hạn, không gửi gì; chỉ trần `_OPEN_TIMEOUT_S` (đã hạ ở test) mới cắt được."""
        await asyncio.sleep(3600)


class _SlowErrorApp(Starlette):
    """Gửi `http.response.start` lỗi (không phải luồng) rồi treo — thân không bao giờ đọc xong."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """`content-type` không phải `text/event-stream` nên `_await_start` chuyển sang đọc thân."""
        await send({"type": "http.response.start", "status": 500, "headers": [(b"content-type", b"application/json")]})
        await asyncio.sleep(3600)


async def test_await_start_times_out_waiting_for_http_response_start(
    sse_open: SseOpen, monkeypatch: pytest.MonkeyPatch
) -> None:
    """App không gửi gì → quá hạn `_OPEN_TIMEOUT_S` chờ `http.response.start` (NO-155, nhánh 1/2 của `_await_start`).

    Hạ `_OPEN_TIMEOUT_S` xuống 0,1 s (khuôn `test_disconnect_times_out_when_the_app_never_exits`)
    để test nhanh và tất định, không đoán bằng `sleep` dài.
    """
    monkeypatch.setattr(streams_fixture, "_OPEN_TIMEOUT_S", 0.1)
    with pytest.raises(TimeoutError, match=re.escape("http.response.start")):
        async with sse_open(_SilentApp(), "/bat-ky"):
            pass


async def test_await_start_times_out_reading_an_error_body(sse_open: SseOpen, monkeypatch: pytest.MonkeyPatch) -> None:
    """Thân lỗi (không phải luồng) không bao giờ đọc xong → quá hạn (NO-155, nhánh 2/2 của `_await_start`)."""
    monkeypatch.setattr(streams_fixture, "_OPEN_TIMEOUT_S", 0.1)
    with pytest.raises(TimeoutError, match="đọc thân lỗi"):
        async with sse_open(_SlowErrorApp(), "/bat-ky"):
            pass


# -- Observer (vết case, H1) ------------------------------------------------------------------------


async def test_observer_is_called_once_with_status_and_matching_request_url(
    sse_open: SseOpen, stream_app: StreamApp, request: pytest.FixtureRequest
) -> None:
    """Mọi observer đăng ký ở `API_RESPONSE_OBSERVERS` nhận đúng một response, đúng `request.url`."""
    calls: list[tuple[pytest.Item, httpx.Response]] = []

    def probe(item: pytest.Item, response: httpx.Response) -> None:
        calls.append((item, response))

    observers = request.node.config.stash[API_RESPONSE_OBSERVERS]
    observers.append(probe)
    try:
        async with sse_open(stream_app, "/stream/close/1", query={"lastEventId": "0-0"}) as stream:
            await stream.next_frames(1)
    finally:
        observers.remove(probe)
    assert len(calls) == 1
    item, response = calls[0]
    assert item is request.node
    assert response.status_code == 200
    assert str(response.request.url) == "https://testserver/stream/close/1?lastEventId=0-0"
    assert response.content == b""


async def test_observer_gets_the_body_for_an_error_response(
    sse_open: SseOpen, stream_app: StreamApp, request: pytest.FixtureRequest
) -> None:
    """Lỗi trước khi mở luồng: observer nhận response có thân W7."""
    calls: list[httpx.Response] = []
    observers = request.node.config.stash[API_RESPONSE_OBSERVERS]
    observers.append(lambda _item, response: calls.append(response))
    try:
        async with sse_open(stream_app, "/error/401"):
            pass
    finally:
        observers.pop()
    assert calls[0].json() == {"code": "UNAUTHENTICATED", "requestId": "rid-0000000001"}


# -- publish_progress/publish_notification, sample_*, stream_cookie --------------------------------


async def test_publish_progress_uses_sample_progress_by_default(event_bus: EventBus) -> None:
    """`publish_progress` không truyền `data` → ghi `sample_progress(upload_id)`, đọc lại đúng."""
    upload_id = "upl_01ARZ3NDEKTSV4RRFFQ69G5FAV"
    event_id = await publish_progress(event_bus, upload_id)
    events = await event_bus.read_after(upload_stream(upload_id), "0-0")
    assert [event.id for event in events] == [event_id]
    assert events[0].data == sample_progress(upload_id)


async def test_publish_progress_accepts_custom_data(event_bus: EventBus) -> None:
    """`data` tường minh thắng mặc định."""
    upload_id = "upl_01ARZ3NDEKTSV4RRFFQ69G5FAW"
    custom = {"id": upload_id, "progressPercent": 10, "status": "pending", "step": "queued"}
    await publish_progress(event_bus, upload_id, custom)
    events = await event_bus.read_after(upload_stream(upload_id), "0-0")
    assert events[0].data == custom


async def test_publish_notification_uses_sample_notification_by_default(event_bus: EventBus) -> None:
    """`publish_notification` ghi `sample_notification()` mặc định vào stream của người dùng."""
    user_id = "usr_01ARZ3NDEKTSV4RRFFQ69G5FAX"
    await publish_notification(event_bus, user_id)
    events = await event_bus.read_after(user_stream(user_id), "0-0")
    assert events[0].data["kind"] == "aiCompleted"
    assert events[0].data["isRead"] is False


def test_sample_progress_has_every_field_the_fe_schema_requires() -> None:
    """`sample_progress` đủ `id`, `progressPercent` [0,100], `status`, `step`; `overrides` thay được."""
    data = sample_progress("upl_01ARZ3NDEKTSV4RRFFQ69G5FAY")
    assert data["id"] == "upl_01ARZ3NDEKTSV4RRFFQ69G5FAY"
    percent = data["progressPercent"]
    assert isinstance(percent, int)
    assert 0 <= percent <= 100
    assert data["status"] in {"pending", "running", "completed", "failed"}
    assert data["step"]
    overridden = sample_progress(
        "upl_01ARZ3NDEKTSV4RRFFQ69G5FAY", status="completed", endedAt="2026-01-01T00:00:00.000Z"
    )
    assert overridden["status"] == "completed"
    assert overridden["endedAt"] == "2026-01-01T00:00:00.000Z"


def test_sample_notification_has_every_field_the_fe_schema_requires() -> None:
    """`sample_notification` đủ trường bắt buộc, id đúng mẫu `<tiền tố>_<ULID>`; `overrides` thay được."""
    data = sample_notification()
    assert is_id("ntf", str(data["id"]))
    assert is_id("prj", str(data["projectId"]))
    for field in ("createdAt", "isRead", "kind", "message", "objectLabel", "place", "projectName"):
        assert field in data
    overridden = sample_notification(kind="commentMention", place="rooms")
    assert overridden["kind"] == "commentMention"
    assert overridden["place"] == "rooms"


def test_sample_notification_ids_are_fresh_each_call() -> None:
    """Hai lượt gọi không trùng id — mỗi mẫu là một thông báo riêng."""
    assert sample_notification()["id"] != sample_notification()["id"]


async def test_stream_cookie_matches_the_real_signed_in_cookie(signed_in: SignIn, db_session: AsyncSession) -> None:
    """`stream_cookie` đọc đúng cookie `appback_stream` của một người đã `sign_in` thật."""
    user = await make_user(db_session)
    signed = await signed_in(user)
    cookies = stream_cookie(signed)
    assert cookies == {"appback_stream": signed.client.cookies["appback_stream"]}
    assert cookies["appback_stream"]


# -- record_stream_frames -----------------------------------------------------------------------


def test_record_stream_frames_writes_one_sample_per_frame(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Bật `CONTRACT_SAMPLES_DIR` → mỗi khung thành `<op>/<case>-event-<n>.json`."""
    monkeypatch.setenv(recorder.SAMPLES_ENV, str(tmp_path))
    frames = [
        SseFrame(id="1-0", data=json.dumps({"n": 1}), event=None, comments=()),
        SseFrame(id="2-0", data=json.dumps({"n": 2}), event=None, comments=()),
    ]
    record_stream_frames("streams_open_progress", "S03", frames)
    written = sorted(p.name for p in (tmp_path / "streams_open_progress").iterdir())
    assert written == ["S03-event-1.json", "S03-event-2.json"]
    body = json.loads((tmp_path / "streams_open_progress" / "S03-event-1.json").read_text(encoding="utf-8"))
    assert body == {"operationId": "streams_open_progress", "case": "S03", "event": {"n": 1}}


def test_record_stream_frames_does_nothing_outside_the_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`CONTRACT_SAMPLES_DIR` vắng → không ghi gì (chạy pytest tay không làm bẩn cây)."""
    monkeypatch.delenv(recorder.SAMPLES_ENV, raising=False)
    frames = [SseFrame(id="1-0", data=json.dumps({"n": 1}), event=None, comments=())]
    record_stream_frames("streams_open_progress", "S03", frames)
    assert not (tmp_path / "streams_open_progress").exists()
