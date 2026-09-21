"""`create_app`: chọn verifier, dò router, gộp `lifespan`, cổng đồng hồ tiêm."""

import importlib
from types import ModuleType
from typing import Any, Final

import httpx
import pytest
from fastapi import APIRouter, FastAPI
from pydantic import ValidationError

from apps.api.core import app as app_module
from apps.api.core import extensions
from apps.api.core import openapi as openapi_module
from apps.api.core.app import (
    OPENAPI_URL,
    SCHEMA_SETTINGS,
    VERIFIER_MODULE,
    app_routes,
    create_app,
    discover_routers,
    schema_settings,
)
from apps.api.core.auth import DenyAllTokenVerifier, FakeTokenVerifier, Principal
from apps.api.core.routing import AppRoute, check_routers, protected_router
from apps.api.core.tests.sample import SAMPLE_ROUTERS, ItemOut, lifespan_router
from packages.core.clock import SystemClock
from packages.core.settings import CoreSettings, get_core_settings, reset_settings_cache
from packages.db.engine import GATE_CONNECT_TIMEOUT_S
from packages.db.settings import get_database_settings
from packages.testing.fixtures.api import make_api_client
from packages.testing.fixtures.clock import FakeClock

HKDF_SEED: Final = "khoa-du-dai-cho-hkdf-trong-test-01"


def _settings(env: str) -> CoreSettings:
    """Cấu hình tối thiểu cho một môi trường bất kỳ (không chạm biến môi trường)."""
    return CoreSettings(app_env=env, public_base_url="https://appback.test", secret_key=HKDF_SEED)


def _verifier_module(monkeypatch: pytest.MonkeyPatch, build: Any) -> None:
    """Giả lập `apps.api.auth.verifier` đã hợp nhất (B1-01 chưa có trong repo)."""
    module = ModuleType(VERIFIER_MODULE)
    module.build_verifier = build  # type: ignore[attr-defined]  # module giả dựng tại chỗ
    original = importlib.import_module
    monkeypatch.setattr(app_module, "_verifier_module_exists", lambda: True)
    monkeypatch.setattr(
        importlib,
        "import_module",
        lambda name, package=None: module if name == VERIFIER_MODULE else original(name, package),
    )


def test_deny_all_when_no_auth_module() -> None:
    """Chưa có B1-01: `dev`/`ci`/`test` chạy với verifier từ chối mọi token."""
    app = create_app(_settings("dev"), routers=[])
    assert isinstance(app.state.token_verifier, DenyAllTokenVerifier)


def test_production_without_auth_module_refuses_to_start() -> None:
    """API thật mà không ai kiểm token thì thà không lên."""
    with pytest.raises(RuntimeError, match=VERIFIER_MODULE):
        create_app(_settings("production"), routers=[])


def test_fake_verifier_only_in_test_env() -> None:
    with pytest.raises(RuntimeError, match="APP_ENV=test"):
        create_app(_settings("dev"), token_verifier=FakeTokenVerifier(), routers=[])


def test_given_verifier_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tham số truyền vào thắng cả module auth đã có."""
    _verifier_module(monkeypatch, lambda _app: DenyAllTokenVerifier())
    given = FakeTokenVerifier()
    app = create_app(_settings("test"), token_verifier=given, routers=[])
    assert app.state.token_verifier is given


def test_auth_module_is_used_when_present(monkeypatch: pytest.MonkeyPatch) -> None:
    built = DenyAllTokenVerifier()
    _verifier_module(monkeypatch, lambda _app: built)
    app = create_app(_settings("production"), routers=[])
    assert app.state.token_verifier is built


def test_auth_module_import_error_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    """Module có thật mà nhập hỏng thì **ném ra**, không lùi về `DenyAll`."""

    def explode(name: str, *args: object, **kwargs: object) -> ModuleType:
        raise ImportError(f"hong: {name}")

    monkeypatch.setattr(app_module, "_verifier_module_exists", lambda: True)
    monkeypatch.setattr(importlib, "import_module", explode)
    with pytest.raises(ImportError, match="hong"):
        create_app(_settings("dev"), routers=[])


def test_verifier_module_exists_is_false_today() -> None:
    """`apps.api.auth` chưa hợp nhất: `find_spec` không được ném ra ngoài."""
    assert app_module._verifier_module_exists() is False


def test_injected_clock_only_in_test_env(fake_clock: FakeClock) -> None:
    with pytest.raises(RuntimeError, match="APP_ENV=test"):
        create_app(_settings("dev"), clock=fake_clock, routers=[])


def test_system_clock_is_allowed_everywhere() -> None:
    clock = SystemClock()
    assert create_app(_settings("dev"), clock=clock, routers=[]).state.clock is clock


def test_default_clock_is_system_clock() -> None:
    assert isinstance(create_app(_settings("dev"), routers=[]).state.clock, SystemClock)


@pytest.mark.parametrize(("env", "expected"), [("dev", OPENAPI_URL), ("test", OPENAPI_URL), ("ci", OPENAPI_URL)])
def test_openapi_url_in_safe_envs(env: str, expected: str) -> None:
    assert create_app(_settings(env), routers=[]).openapi_url == expected


def test_openapi_url_hidden_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sơ đồ API không phơi ở `staging`/`production`."""
    _verifier_module(monkeypatch, lambda _app: DenyAllTokenVerifier())
    assert create_app(_settings("production"), routers=[]).openapi_url is None


def test_discover_routers_finds_real_modules() -> None:
    """Hôm nay repo có đúng hai module có `router.py`."""
    names = [name for name, _router in discover_routers()]
    assert names == ["apps.api.files.router", "apps.api.health.router"]


def test_discover_routers_rejects_wrong_type(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(extensions, "discover", lambda *_args: [("apps.api.x.router", "khong-phai-router")])
    with pytest.raises(RuntimeError, match="tuple"):
        discover_routers()


def test_check_routers_rejects_empty_router() -> None:
    """Mỗi `router.py` phải góp ít nhất một route (BE-00 §2)."""
    with pytest.raises(RuntimeError, match="không góp route"):
        check_routers([("apps.api.trong.router", protected_router())])


def test_check_routers_rejects_plain_api_route() -> None:
    """Route không dùng `AppRoute` là route không có xác thực, guard hay idempotency."""
    plain = APIRouter()

    @plain.get("/tran", name="tran")
    async def tran() -> ItemOut:
        return ItemOut(name="tran")

    with pytest.raises(RuntimeError, match="AppRoute"):
        check_routers([("apps.api.tran.router", plain)])


def test_app_routes_skips_schema_route() -> None:
    """`app_routes` chỉ trả route nghiệp vụ, bỏ route OpenAPI FastAPI tự thêm."""
    app = create_app(_settings("test"), token_verifier=FakeTokenVerifier(), routers=list(SAMPLE_ROUTERS))
    assert all(isinstance(route, AppRoute) for route in app_routes(app))
    assert len(app_routes(app)) < len(app.routes)


def test_schema_settings_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bước 8 và cổng case chạy khi chưa có biến môi trường nào."""
    for name in ("APP_ENV", "PUBLIC_BASE_URL", "SECRET_KEY"):
        monkeypatch.delenv(name, raising=False)
    reset_settings_cache()
    assert schema_settings() is SCHEMA_SETTINGS
    reset_settings_cache()


def test_schema_settings_prefers_real_env(storage_env: None) -> None:
    assert schema_settings() is get_core_settings()


async def test_router_lifespans_are_merged(api_env: None, fake_clock: FakeClock, fake_principal: Principal) -> None:
    """Hai router, mỗi cái một `lifespan`: cả hai mount được và cả hai `lifespan` chạy."""
    log: list[str] = []
    routers = [
        ("apps.api.mot.router", lifespan_router("mot", log)),
        ("apps.api.hai.router", lifespan_router("hai", log)),
    ]
    app: FastAPI = create_app(
        get_core_settings(), token_verifier=FakeTokenVerifier(), clock=fake_clock, routers=routers
    )
    async with make_api_client(app) as client:
        assert log == ["mot:mở", "hai:mở"]
        for name in ("mot", "hai"):
            response = await client.get(
                f"/api/{name}/ping", headers={"Authorization": f"Bearer fake:{fake_principal.user_id}:sid:admin"}
            )
            assert response.status_code == 200, response.text
            assert response.json() == {"name": name}
    assert log == ["mot:mở", "hai:mở", "hai:đóng", "mot:đóng"]


async def test_lifespan_closes_resources(api_env: None, fake_clock: FakeClock) -> None:
    """Đóng `lifespan` phải nhả engine và mọi client Redis."""
    app = create_app(get_core_settings(), token_verifier=FakeTokenVerifier(), clock=fake_clock, routers=[])
    async with make_api_client(app) as client:
        assert isinstance(client, httpx.AsyncClient)
        engine = app.state.engine
    assert engine.pool.checkedout() == 0


@pytest.mark.parametrize(
    "broken",
    [{"APP_ENV": "production", "SECRET_KEY": None}, {"APP_ENV": None, "APP_ENVIRONMENT": "production"}],
    ids=["production thiếu SECRET_KEY", "gõ nhầm tên APP_ENV"],
)
def test_create_app_fails_fast_on_invalid_env(broken: dict[str, str | None], monkeypatch: pytest.MonkeyPatch) -> None:
    """Cấu hình sai là **không khởi động**, không lùi về bản chỉ-đọc-schema (`ci`) — R-17.

    Lùi về `SCHEMA_SETTINGS` ở đây là cho production thiếu một biến chạy như `ci`: phơi
    `/api/openapi.json` và lách chốt "production chưa có verifier thì không lên".
    """
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://appback.test")
    monkeypatch.setenv("SECRET_KEY", HKDF_SEED)
    for name, value in broken.items():
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    reset_settings_cache()
    try:
        with pytest.raises(ValidationError):
            create_app(routers=[])
    finally:
        reset_settings_cache()


def test_schema_app_builds_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Chỉ công cụ đọc schema (bước 8, `case_gate`) được dựng app khi thiếu biến môi trường."""
    for name in ("APP_ENV", "PUBLIC_BASE_URL", "SECRET_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(openapi_module, "_cached_app", None)
    reset_settings_cache()
    try:
        assert openapi_module.real_app().state.settings is SCHEMA_SETTINGS
    finally:
        reset_settings_cache()


def test_api_env_uses_gate_connect_timeout(api_env: None) -> None:
    """App thử bắt tay Postgres với trần của đường cổng (180 s), không phải 10 s của request."""
    assert get_database_settings().db_connect_timeout_s == int(GATE_CONNECT_TIMEOUT_S)
