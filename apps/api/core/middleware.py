"""Bốn lớp middleware ASGI thuần của `apps/api` (BE-00 §8, §11, W6).

Từ ngoài vào trong:

1. `RequestIdMiddleware` — nhận `X-Request-Id` của FE (sai mẫu thì sinh mới) và
   **luôn** trả lại nó (W6); đây cũng là nơi gắn id vào ngữ cảnh log;
2. `AccessLogMiddleware` — ghi `routeTemplate`, status, thời lượng. **Không** ghi
   đường thật: `/api/files/<token>` mang chính quyền truy cập trong URL (K11);
3. `SecurityHeadersMiddleware` — bốn header của BE-00 §11; `Cache-Control` chỉ đặt
   khi route chưa tự đặt (endpoint tệp dùng `private, max-age=600`);
4. `BodyLimitMiddleware` — trần thân **theo route**, mọi method.

`FinalErrorMiddleware` nằm trong cùng, ngay ngoài `ExceptionMiddleware` của
Starlette: nó biến mọi ngoại lệ lọt lưới thành 500 `INTERNAL` **đi qua** ba lớp
trên, nên 500 vẫn có `X-Request-Id` và header bảo mật. Nếu để `ServerErrorMiddleware`
mặc định xử (nó nằm ngoài cùng, ngoài tầm với của ta) thì 500 sẽ thiếu cả hai.

Middleware ASGI thuần chứ không `BaseHTTPMiddleware`: lớp kia dựng một task riêng
cho mỗi request, làm `contextvars` và `StreamingResponse` cư xử khác.
"""

import logging
import re
import secrets
import time
from typing import Final

from starlette.datastructures import Headers, MutableHeaders
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from apps.api.core.errors import REQUEST_ID_HEADER, error_response, request_id, simple_error, translate_unknown
from apps.api.core.routing import body_limit_of, route_of
from packages.core.error_codes import PAYLOAD_TOO_LARGE
from packages.core.logging import request_id_var

_log: Final = logging.getLogger(__name__)

HTTP: Final = "http"
RESPONSE_START: Final = "http.response.start"
REQUEST: Final = "http.request"

REQUEST_ID_RE: Final = re.compile(r"[A-Za-z0-9-]{8,64}")
REQUEST_ID_BYTES: Final = 16

CACHE_CONTROL: Final = "cache-control"
SECURITY_HEADERS: Final = (
    ("x-content-type-options", "nosniff"),
    ("referrer-policy", "same-origin"),
    ("x-frame-options", "DENY"),
)
NO_STORE: Final = "no-store"

UNKNOWN_ROUTE: Final = "-"


def new_request_id() -> str:
    """Id mới hợp mẫu W6 (`^[A-Za-z0-9-]{8,64}$`)."""
    return secrets.token_hex(REQUEST_ID_BYTES)


def incoming_request_id(scope: Scope) -> str:
    """`X-Request-Id` của client nếu đúng mẫu, còn lại là id mới (W6)."""
    given = Headers(scope=scope).get(REQUEST_ID_HEADER)
    return given if given is not None and REQUEST_ID_RE.fullmatch(given) else new_request_id()


class RequestIdMiddleware:
    """W6: nhận, chuẩn hoá và luôn trả lại `X-Request-Id`; gắn nó vào mọi dòng log."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != HTTP:
            await self.app(scope, receive, send)
            return
        rid = incoming_request_id(scope)
        token = request_id_var.set(rid)

        async def send_with_id(message: Message) -> None:
            if message["type"] == RESPONSE_START:
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = rid
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            request_id_var.reset(token)


class AccessLogMiddleware:
    """Một dòng log mỗi request, không bao giờ kèm đường thật hay thân (K11, BE-00 §8)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != HTTP:
            await self.app(scope, receive, send)
            return
        started = time.perf_counter()
        status = 0

        async def send_recording(message: Message) -> None:
            nonlocal status
            if message["type"] == RESPONSE_START:
                status = int(message["status"])
            await send(message)

        try:
            await self.app(scope, receive, send_recording)
        finally:
            route = route_of(scope)
            _log.info(
                "http_access",
                extra={
                    "method": scope.get("method", ""),
                    "routeTemplate": UNKNOWN_ROUTE if route is None else route.path_format,
                    "status": status,
                    "durationMs": round((time.perf_counter() - started) * 1000, 1),
                },
            )


class SecurityHeadersMiddleware:
    """Header nền của BE-00 §11; `Cache-Control` không đè giá trị route đã đặt."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != HTTP:
            await self.app(scope, receive, send)
            return

        async def send_hardened(message: Message) -> None:
            if message["type"] == RESPONSE_START:
                headers = MutableHeaders(scope=message)
                for name, value in SECURITY_HEADERS:
                    headers[name] = value
                if CACHE_CONTROL not in headers:
                    headers[CACHE_CONTROL] = NO_STORE
            await send(message)

        await self.app(scope, receive, send_hardened)


class _BodyTooLarge(StarletteHTTPException):
    """413 ném từ `receive`.

    Kế thừa `HTTPException` có chủ đích: FastAPI bọc **mọi** ngoại lệ khác khi đọc
    thân thành 400 "error parsing the body", chỉ `HTTPException` mới được ném
    tiếp — và `install_error_handlers` đổi 413 thành `PAYLOAD_TOO_LARGE` (W7).
    """

    def __init__(self) -> None:
        super().__init__(status_code=413)


class BodyLimitMiddleware:
    """Trần thân theo route (BE-00 §11, C12): `Content-Length` vượt → 413 **trước** handler."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != HTTP:
            await self.app(scope, receive, send)
            return
        limit = body_limit_of(scope)
        declared = _content_length(scope)
        if declared is not None and declared > limit:
            await simple_error(PAYLOAD_TOO_LARGE, request_id())(scope, receive, send)
            return
        received = 0

        async def receive_counting() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == REQUEST:
                received += len(message.get("body", b""))
                if received > limit:
                    raise _BodyTooLarge
            return message

        await self.app(scope, receive_counting, send)


class FinalErrorMiddleware:
    """Chặng cuối: ngoại lệ lọt qua `ExceptionMiddleware` → 503 đã dịch, hoặc 500 có stack."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != HTTP:
            await self.app(scope, receive, send)
            return
        started = False

        async def send_marking(message: Message) -> None:
            nonlocal started
            if message["type"] == RESPONSE_START:
                started = True
            await send(message)

        try:
            await self.app(scope, receive, send_marking)
        except Exception as exc:  # chặng cuối của app: không còn ai bắt sau đây nữa
            if started:
                raise
            await error_response(translate_unknown(exc), request_id())(scope, receive, send)


def _content_length(scope: Scope) -> int | None:
    """`Content-Length` của request, hoặc `None` khi vắng hay không phải số."""
    raw = Headers(scope=scope).get("content-length")
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None
