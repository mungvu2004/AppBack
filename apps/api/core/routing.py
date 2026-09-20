"""`AppRoute` — thứ tự bất biến của một request (BE-00 §5, §7, W10, W21).

Mọi route của mọi module đi qua đúng một đường:

1. **xác thực trước khi đọc thân.** FastAPI đọc thân *trước* dependency, nên nếu
   để việc kiểm token cho một dependency thì một request 64 MiB không token vẫn
   được đọc hết rồi mới 401 (W10: 401 phải tới trước 400);
2. mở session của request, gắn ngữ cảnh log;
3. handler gốc của FastAPI: đọc thân → dependency của router/route (quyền, rate
   limit) → **guard của khung** (W21, 428, nhận việc idempotency) → lỗi Pydantic
   422 → endpoint. Guard được gắn **sau** `super().__init__()` để nằm cuối danh
   sách: FastAPI *chèn đầu* mọi dependency khai qua `dependencies=`;
4. hoàn tất idempotency **trong cùng giao dịch** → commit → chờ callback sau
   commit → đóng session → mới trả response.

Chỉ **ngoại lệ** mới rollback. Response 4xx mà handler *trả về* (không ném) vẫn là
một lượt chạy thành công: nó đã ghi gì thì giữ nguyên (BE-00 §7).
"""

import json
from collections.abc import Awaitable, Callable, Coroutine, Sequence
from dataclasses import dataclass
from typing import Any, ClassVar, Final, Literal

from fastapi import APIRouter, FastAPI
from fastapi.dependencies.utils import get_dependant
from fastapi.routing import APIRoute, request_response
from pydantic.alias_generators import to_camel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Match
from starlette.types import Scope

from apps.api.core import idempotency
from apps.api.core.auth import Principal, TokenVerifier
from packages.core.clock import Clock
from packages.core.error_codes import PATH_BODY_MISMATCH, PRECONDITION_REQUIRED, UNAUTHENTICATED
from packages.core.logging import bind_log_context
from packages.db.hooks import after_commit_idle

API_PREFIX: Final = "/api"
"""Mọi route của mọi module nằm dưới `/api` (W19)."""

DEFAULT_BODY_LIMIT: Final = 1024 * 1024
"""JSON 1 MiB (BE-00 §11). Route cần rộng hơn (#35 = 8 MiB) buộc phải `idempotency="off"`."""

BASE_VERSION_KEY: Final = "baseVersion"
AUTHORIZATION_HEADER: Final = "authorization"
BEARER: Final = "bearer"
OPTIONS_ATTR: Final = "__app_route_options__"

type Idempotency = Literal["auto", "off"]


@dataclass(frozen=True, slots=True)
class RouteOptions:
    """Khai báo của một route mà khung cần biết trước khi chạy request."""

    versioned: bool = False
    body_limit: int = DEFAULT_BODY_LIMIT
    idempotency: Idempotency = "auto"


DEFAULT_OPTIONS: Final = RouteOptions()


def route_options(
    *,
    versioned: bool = False,
    body_limit: int = DEFAULT_BODY_LIMIT,
    idempotency: Idempotency = "auto",
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Gắn tuỳ chọn lên hàm endpoint; sai luật thì hỏng **lúc nạp module**, không lúc chạy."""
    if body_limit < 1:
        raise ValueError(f"body_limit phải ≥ 1 byte, nhận {body_limit}")
    if body_limit > DEFAULT_BODY_LIMIT and idempotency != "off":
        raise ValueError(
            f"body_limit {body_limit} > {DEFAULT_BODY_LIMIT} buộc idempotency='off' "
            "(thân lớn hơn 1 MiB không lưu lại được, BE-00 §7)"
        )
    options = RouteOptions(versioned=versioned, body_limit=body_limit, idempotency=idempotency)

    def decorate(endpoint: Callable[..., Any]) -> Callable[..., Any]:
        setattr(endpoint, OPTIONS_ATTR, options)
        return endpoint

    return decorate


def options_of(endpoint: Callable[..., Any]) -> RouteOptions:
    """Tuỳ chọn của một endpoint; không khai gì thì dùng mặc định của hiến chương."""
    options = getattr(endpoint, OPTIONS_ATTR, DEFAULT_OPTIONS)
    return options if isinstance(options, RouteOptions) else DEFAULT_OPTIONS


async def _json_body(request: Request) -> object:
    """Thân đã giải JSON (FastAPI đã đọc và nhớ), hay `None` khi không có/không phải JSON."""
    raw = await request.body()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None  # JSON hỏng đã thành 400 `MALFORMED_JSON` ở chỗ khác


async def _principal_of(request: Request) -> Principal:
    """Đọc `Authorization: Bearer` rồi gọi verifier. Thiếu header → 401 ngay, chưa chạm thân."""
    scheme, _, token = request.headers.get(AUTHORIZATION_HEADER, "").partition(" ")
    if scheme.lower() != BEARER or not token:
        raise UNAUTHENTICATED.error()
    verifier: TokenVerifier = request.app.state.token_verifier
    return await verifier.verify(token, request)


def _path_body_guard(route: "AppRoute") -> Callable[[Request], Awaitable[None]]:
    """W21: khoá thân camelCase trùng tham số đường mà khác giá trị → 422 `PATH_BODY_MISMATCH`."""

    async def guard(request: Request) -> None:
        body = await _json_body(request)
        if not isinstance(body, dict):
            return
        for name, value in request.path_params.items():
            camel = to_camel(name)
            if camel in body and body[camel] != value:
                raise PATH_BODY_MISMATCH.error(field=camel)

    return guard


def _versioned_guard(route: "AppRoute") -> Callable[[Request], Awaitable[None]]:
    """W20: thiếu `baseVersion` → 428, **trước** Pydantic (HOP-DONG-MOI §1.2)."""

    async def guard(request: Request) -> None:
        body = await _json_body(request)
        if not isinstance(body, dict) or BASE_VERSION_KEY not in body:
            raise PRECONDITION_REQUIRED.error()

    return guard


def _idempotency_guard(route: "AppRoute") -> Callable[[Request], Awaitable[None]]:
    """Nhận việc idempotency — chạy **sau** mọi dependency quyền của route (BE-00 §7)."""

    async def guard(request: Request) -> None:
        raw = request.headers.get(idempotency.HEADER)
        if raw is None:
            return
        principal: Principal = request.state.principal
        clock: Clock = request.app.state.clock
        body = await request.body()
        request.state.idempotency_claim = await idempotency.begin(
            request.app.state.sessionmaker,
            user_id=principal.user_id,
            method=request.method,
            route_template=route.path_format,
            key=idempotency.check_key(raw),
            digest=idempotency.request_digest(request.method, request.url.path, request.url.query, body),
            now=clock.now(),
        )

    return guard


class AppRoute(APIRoute):
    """Route **được bảo vệ**: đòi `Authorization: Bearer` trước khi đọc thân."""

    protected: ClassVar[bool] = True

    def __init__(self, path: str, endpoint: Callable[..., Any], **kwargs: Any) -> None:
        super().__init__(path, endpoint, **kwargs)
        self.options = options_of(endpoint)
        self.wire_method = next(iter(sorted((self.methods or set()) - {"HEAD"})), "GET")
        self.uses_idempotency = (
            self.protected
            and self.options.idempotency != "off"
            and not self.options.versioned
            and self.wire_method != "GET"
        )
        # Gắn SAU super().__init__(): `dependencies=` được FastAPI chèn vào đầu, còn
        # guard của khung phải chạy cuối cùng, sau quyền và rate limit (BE-00 §7).
        for build in self._guard_builders():
            self.dependant.dependencies.append(get_dependant(path=self.path_format, call=build(self)))

    def _guard_builders(self) -> list[Callable[["AppRoute"], Callable[[Request], Awaitable[None]]]]:
        """Guard nào áp cho route này — chỉ gắn cái thật sự cần, để route GET không đọc thân."""
        builders: list[Callable[[AppRoute], Callable[[Request], Awaitable[None]]]] = []
        if self.dependant.body_params and self.dependant.path_params:
            builders.append(_path_body_guard)
        if self.options.versioned:
            builders.append(_versioned_guard)
        if self.uses_idempotency:
            builders.append(_idempotency_guard)
        return builders

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original = super().get_route_handler()

        async def handler(request: Request) -> Response:
            if self.protected:
                request.state.principal = await _principal_of(request)
            request.state.idempotency_claim = None
            maker: async_sessionmaker[AsyncSession] = request.app.state.sessionmaker
            session = maker()
            request.state.db_session = session
            log_token = bind_log_context(routeTemplate=self.path_format, method=self.wire_method)
            try:
                try:
                    response = await original(request)
                except idempotency.Replay as replay:
                    await _abort(request, session, maker)
                    return replay.response
                except BaseException:
                    await _abort(request, session, maker)
                    raise
                return await _finish(request, session, maker, response)
            finally:
                # Token của contextvar mang sẵn biến của nó; `packages.core.logging`
                # không phơi hàm gỡ, mà không gỡ thì ngữ cảnh route rò sang request sau
                # khi hai request dùng chung một task (client ASGI của test).
                log_token.var.reset(log_token)

        return handler


class PublicRoute(AppRoute):
    """Route công khai: không xác thực, không idempotency (BE-00 §7, [7] của B0-06)."""

    protected: ClassVar[bool] = False


def _router(route_class: type[AppRoute], kwargs: dict[str, Any]) -> APIRouter:
    """Router mang sẵn tiền tố `/api`, để đường của route là đường thật ngay lúc khai.

    Tiền tố đặt ở đây chứ không ở `include_router(prefix=…)`: từ FastAPI 0.141,
    `include_router` không chép route vào app nữa mà bọc chúng trong một router
    trung gian và **dựng lại** `dependant` cho đường đã thêm tiền tố — làm rơi mất
    guard mà `AppRoute` gắn cuối danh sách dependency.
    """
    prefix = API_PREFIX + kwargs.pop("prefix", "")
    return APIRouter(route_class=route_class, prefix=prefix, **kwargs)


def protected_router(**kwargs: Any) -> APIRouter:
    """Router mặc định của mọi module: mọi route đều được bảo vệ."""
    return _router(AppRoute, kwargs)


def public_router(**kwargs: Any) -> APIRouter:
    """Router cho các `operationId` được phép công khai (BE-00 §5, khối [7] của B0-06)."""
    return _router(PublicRoute, kwargs)


def mount_routers(app: FastAPI, routers: Sequence[tuple[str, APIRouter]]) -> None:
    """Đưa route của từng router thẳng vào app, giữ nguyên chính đối tượng `AppRoute`.

    `app.routes` vì thế chứa route thật (middleware khớp được đường, `operations()`
    đọc được `dependant`). Handler phải dựng lại sau khi gắn `app` làm nguồn
    `dependency_overrides`: `APIRoute.__init__` đã chốt nguồn đó vào `self.app`,
    mà lúc router được khai thì app chưa tồn tại.
    """
    for _name, router in routers:
        for route in router.routes:
            assert isinstance(route, AppRoute)  # noqa: S101 — `check_routers` đã kiểm trước đó
            route.dependency_overrides_provider = app
            route.app = request_response(route.get_route_handler())
            app.router.routes.append(route)


async def _abort(request: Request, session: AsyncSession, maker: async_sessionmaker[AsyncSession]) -> None:
    """Lượt chạy hỏng: rollback, đóng session, xoá dòng idempotency của chính mình."""
    await session.rollback()
    await session.close()
    claim = request.state.idempotency_claim
    if claim is not None:
        await idempotency.discard(maker, claim)


async def _finish(
    request: Request,
    session: AsyncSession,
    maker: async_sessionmaker[AsyncSession],
    response: Response,
) -> Response:
    """Hoàn tất idempotency → commit → chờ callback sau commit → đóng session."""
    claim: idempotency.Claim | None = request.state.idempotency_claim
    keep = claim is not None and idempotency.storable(response)
    try:
        if keep and claim is not None:
            clock: Clock = request.app.state.clock
            await idempotency.complete(session, claim, response, clock.now())
        await session.commit()
        await after_commit_idle(session)
    except BaseException:
        await _abort(request, session, maker)
        raise
    await session.close()
    if claim is not None and not keep:
        # 401/408/429 hay 5xx do handler trả về: không lưu, để lượt sau chạy lại thật.
        await idempotency.discard(maker, claim)
    return response


def route_of(scope: Scope) -> AppRoute | None:
    """Route khớp `scope`; khớp đường mà lệch method vẫn tính (giới hạn thân áp cho mọi method)."""
    partial: AppRoute | None = None
    for route in scope["app"].routes:
        if not isinstance(route, AppRoute):
            continue
        match, _ = route.matches(scope)
        if match is Match.FULL:
            return route
        if match is Match.PARTIAL and partial is None:
            partial = route
    return partial


def body_limit_of(scope: Scope) -> int:
    """Trần thân của route khớp; không khớp route nào thì dùng trần chung 1 MiB."""
    route = route_of(scope)
    return DEFAULT_BODY_LIMIT if route is None else route.options.body_limit


def check_routers(routers: Sequence[tuple[str, APIRouter]]) -> None:
    """Mỗi `router.py` phải góp ≥ 1 route và mọi route phải là `AppRoute` (BE-00 §2)."""
    for name, router in routers:
        if not router.routes:
            raise RuntimeError(f"{name}: ROUTERS có router không góp route nào")
        for route in router.routes:
            if not isinstance(route, AppRoute):
                raise RuntimeError(f"{name}: route {route!r} không dùng AppRoute (protected_router/public_router)")
