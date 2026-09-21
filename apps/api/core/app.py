"""`create_app` — dựng app FastAPI của AppBack (BE-00 §2, §5, §7).

Ba điều đáng nhớ:

- **không kết nối lúc tạo.** `create_app()` chỉ dò route và khai middleware; engine,
  Redis và kho mở trong `lifespan`, nên công cụ nào chỉ cần schema (bước 8, cổng
  case) không phải dựng Postgres;
- **cấu hình sai là không khởi động.** `create_app(settings=None)` đọc thẳng
  `get_core_settings()`; bản `SCHEMA_SETTINGS` chỉ dành cho công cụ đọc schema và
  phải được truyền **tường minh** (`openapi.real_app`). Lùi âm thầm về nó ở đây là
  cho một production thiếu `SECRET_KEY` chạy ở chế độ `ci` (R-17);
- **route tự dò.** Mỗi module khai `ROUTERS` trong `apps/api/<module>/router.py`;
  thêm module không phải sửa file này (BE-00 §2). `lifespan` của từng router được
  gộp vào `lifespan` của app;
- **verifier chọn theo môi trường.** Có `apps/api/auth/verifier` thì dùng nó và
  nhập lỗi thì **ném ra**; chưa có thì `dev`/`ci`/`test` chạy `DenyAllTokenVerifier`
  (mọi token 401) còn `staging`/`production` từ chối khởi động — một API thật mà
  không có ai kiểm token thì thà không lên.
"""

import asyncio
import importlib
import importlib.util
import logging
from collections.abc import AsyncIterator, Sequence
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any, Final

from fastapi import APIRouter, FastAPI
from pydantic import ValidationError
from starlette.middleware import Middleware

from apps.api.core import extensions, ratelimit
from apps.api.core.auth import DenyAllTokenVerifier, FakeTokenVerifier, TokenVerifier
from apps.api.core.errors import install_error_handlers
from apps.api.core.middleware import (
    AccessLogMiddleware,
    BodyLimitMiddleware,
    FinalErrorMiddleware,
    RequestIdMiddleware,
    SecurityHeadersMiddleware,
)
from apps.api.core.routing import API_PREFIX, AppRoute, check_routers, mount_routers
from packages.core.clock import Clock, SystemClock
from packages.core.settings import CoreSettings, get_core_settings
from packages.db.engine import create_engine, create_sessionmaker
from packages.db.settings import get_database_settings
from packages.messaging.redis import assert_broker_policy, broker_redis_sync, cache_redis, safe_redis, streams_redis
from packages.messaging.streams import EventBus
from packages.storage.factory import create_storage
from packages.storage.settings import get_storage_settings

_log: Final = logging.getLogger(__name__)

ROUTER_SUBMODULE: Final = "router"
ROUTERS_ATTR: Final = "ROUTERS"
VERIFIER_MODULE: Final = "apps.api.auth.verifier"
VERIFIER_FACTORY: Final = "build_verifier"

CLAIM_POOL_SIZE: Final = 5
"""Pool riêng của giao dịch idempotency (`begin`, `discard`). Mỗi kết nối chỉ giữ một câu
lệnh rồi commit, nên 5 kết nối phục vụ hàng nghìn lượt nhận việc mỗi giây; đổi lại mỗi
tiến trình API mở thêm tối đa 5 kết nối Postgres."""

OPENAPI_ENVS: Final = frozenset({"dev", "test", "ci"})
OPENAPI_URL: Final = f"{API_PREFIX}/openapi.json"

SCHEMA_SETTINGS: Final = CoreSettings(
    app_env="ci",
    public_base_url="http://localhost:8000",
    secret_key="schema-only-secret-not-used-for-signing",  # noqa: S106 — chỉ để dựng app đọc schema
)
"""Cấu hình thay thế cho lượt chạy **chỉ đọc schema** (bước 8, `case_gate`): ở đó
không có biến môi trường thật và cũng không có kết nối nào được mở."""


def schema_settings() -> CoreSettings:
    """Cấu hình thật nếu môi trường có đủ, còn lại là bản chỉ-đọc-schema.

    **Chỉ** cho công cụ đọc schema (bước 8, `case_gate`): nuốt `ValidationError` là có
    chủ đích ở đó và là lỗ hổng ở mọi nơi khác, nên `create_app` không gọi hàm này.
    """
    try:
        return get_core_settings()
    except ValidationError:
        return SCHEMA_SETTINGS


def discover_routers() -> list[tuple[str, APIRouter]]:
    """`[(tên module, router)]` của mọi `apps/api/<module>/router.py`, theo thứ tự tên."""
    found: list[tuple[str, APIRouter]] = []
    for name, value in extensions.discover(ROUTER_SUBMODULE, ROUTERS_ATTR):
        if not isinstance(value, tuple | list) or not all(isinstance(item, APIRouter) for item in value):
            raise RuntimeError(f"{name}.{ROUTERS_ATTR} phải là tuple[APIRouter, ...]")
        found.extend((name, router) for router in value)
    return found


def _token_verifier(app: FastAPI, settings: CoreSettings, given: TokenVerifier | None) -> TokenVerifier:
    """Chọn verifier theo [2] của B0-06; tham số truyền vào luôn thắng."""
    if given is not None:
        if isinstance(given, FakeTokenVerifier) and settings.app_env != "test":
            raise RuntimeError(f"FakeTokenVerifier chỉ dùng khi APP_ENV=test, không phải {settings.app_env}")
        return given
    if _verifier_module_exists():
        module = importlib.import_module(VERIFIER_MODULE)  # nhập lỗi thì ném ra, không lùi về DenyAll
        build = getattr(module, VERIFIER_FACTORY)
        verifier: TokenVerifier = build(app)
        return verifier
    if settings.app_env not in OPENAPI_ENVS:
        raise RuntimeError(f"{VERIFIER_MODULE} chưa có: không khởi động được ở {settings.app_env}")
    _log.warning("token_verifier_deny_all", extra={"appEnv": settings.app_env})
    return DenyAllTokenVerifier()


def _verifier_module_exists() -> bool:
    """`apps.api.auth.verifier` đã hợp nhất chưa — chỉ tìm, không nạp."""
    try:
        return importlib.util.find_spec(VERIFIER_MODULE) is not None
    except ModuleNotFoundError:
        return False  # gói cha `apps.api.auth` chưa có (B1-01 chưa hợp nhất)


def _checked_clock(settings: CoreSettings, clock: Clock | None) -> Clock:
    """Đồng hồ giả chỉ hợp lệ ở `APP_ENV=test` (BE-00 §2.2)."""
    if clock is None:
        return SystemClock()
    if not isinstance(clock, SystemClock) and settings.app_env != "test":
        raise RuntimeError(f"clock tiêm chỉ dùng khi APP_ENV=test, không phải {settings.app_env}")
    return clock


def _lifespan(routers: Sequence[tuple[str, APIRouter]]) -> Any:
    """`lifespan` của app: mở tài nguyên, gộp `lifespan` của từng router, rồi đóng lại."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Mở hai engine, Redis, kho; kiểm chính sách broker; chạy `lifespan` của từng router; đóng hết khi dừng."""
        database = get_database_settings()
        engine = create_engine(database)
        app.state.engine = engine
        app.state.sessionmaker = create_sessionmaker(engine)
        # `begin` chạy khi session của request có thể đã giữ một kết nối (dependency quyền
        # đọc DB). Lấy kết nối thứ hai từ **cùng** pool là N lượt ghi đồng thời giữ N kết
        # nối rồi cùng chờ nhau tới `pool_timeout` → cả loạt 503. Pool riêng cắt vòng chờ đó.
        claims = create_engine(database.model_copy(update={"db_pool_size": CLAIM_POOL_SIZE, "db_max_overflow": 0}))
        app.state.claim_sessionmaker = create_sessionmaker(claims)
        cache, safe, streams = cache_redis(), safe_redis(), streams_redis()
        app.state.cache_redis, app.state.safe_redis, app.state.streams_redis = cache, safe, streams
        app.state.broker_sync = broker_redis_sync()
        app.state.event_bus = EventBus(streams)
        app.state.storage = create_storage(get_storage_settings(), app.state.settings, app.state.clock)
        ratelimit.install(app, cache=cache, safe=safe)
        try:
            # Broker `allkeys-lru` là **mất việc**, không phải chậm: thà không khởi động.
            # `assert_broker_policy` chỉ có bản đồng bộ (nó cũng chạy trong tín hiệu Celery,
            # nơi chưa có vòng sự kiện), nên ở đây phải đẩy sang luồng khác (NO-026, R-23).
            await asyncio.to_thread(assert_broker_policy, app.state.broker_sync)
            async with AsyncExitStack() as stack:
                for _name, router in routers:
                    await stack.enter_async_context(router.lifespan_context(app))
                yield
        finally:
            app.state.broker_sync.close()
            for client in (cache, safe, streams):
                await client.aclose()
            await claims.dispose()
            await engine.dispose()

    return lifespan


def create_app(
    settings: CoreSettings | None = None,
    *,
    token_verifier: TokenVerifier | None = None,
    clock: Clock | None = None,
    routers: Sequence[tuple[str, APIRouter]] | None = None,
) -> FastAPI:
    """App của AppBack; biến môi trường sai → ném `ValidationError` ngay (fail-closed).

    `routers` chỉ để test dựng app thử — mặc định là dò thật.
    """
    resolved = settings if settings is not None else get_core_settings()
    mounted = list(routers) if routers is not None else discover_routers()
    check_routers(mounted)
    app = FastAPI(
        title="AppBack API",
        version="1.0.0",
        openapi_url=OPENAPI_URL if resolved.app_env in OPENAPI_ENVS else None,
        docs_url=None,
        redoc_url=None,
        separate_input_output_schemas=False,  # giữ `properties` đúng alias cho response (K01)
        generate_unique_id_function=lambda route: route.name,
        lifespan=_lifespan(mounted),
        middleware=[
            Middleware(RequestIdMiddleware),
            Middleware(AccessLogMiddleware),
            Middleware(SecurityHeadersMiddleware),
            Middleware(BodyLimitMiddleware),
            Middleware(FinalErrorMiddleware),
        ],
    )
    app.state.settings = resolved
    app.state.clock = _checked_clock(resolved, clock)
    app.state.token_verifier = _token_verifier(app, resolved, token_verifier)
    install_error_handlers(app)
    mount_routers(app, mounted)
    return app


def app_routes(app: FastAPI) -> list[AppRoute]:
    """Mọi route nghiệp vụ của app (bỏ route schema mà FastAPI tự thêm)."""
    return [route for route in app.routes if isinstance(route, AppRoute)]
