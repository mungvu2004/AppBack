"""`GET /api/health` và `GET /api/ready` (B0-06 [2])."""

import asyncio
from datetime import timedelta
from typing import Final

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis
from starlette.requests import Request

from apps.api.core.app import create_app
from apps.api.core.auth import FakeTokenVerifier
from apps.api.health import router as health_router
from apps.api.health.router import PROBE_KEY, READY_CACHE, READY_LIMIT, ReadyCache, probe
from packages.core.settings import get_core_settings
from packages.messaging.settings import reset_messaging_settings_cache
from packages.testing.fixtures.api import make_api_client
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.services import refused_url

HEALTH: Final = "/api/health"
READY: Final = "/api/ready"
SLOW_S: Final = 60.0
GUARD_S: Final = 30.0


async def test_health_live_is_public_and_touches_nothing(api_client: httpx.AsyncClient) -> None:
    """Sống hay chưa: không token, không phụ thuộc, luôn 200."""
    response = await api_client.get(HEALTH)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_health_live_opens_no_connection(api_client: httpx.AsyncClient, api_app: FastAPI) -> None:
    """`health_live` không chạm phụ thuộc: pool CSDL vẫn chưa mở kết nối nào.

    Đây là điều tách nó khỏi `health_ready`: probe của orchestrator không được giết
    một tiến trình khoẻ chỉ vì Postgres chập chờn.
    """
    pool = api_app.state.engine.pool
    assert (await api_client.get(HEALTH)).status_code == 200
    assert pool.checkedin() + pool.checkedout() == 0

    assert (await api_client.get(READY)).status_code == 200
    assert pool.checkedin() >= 1, "health_ready thì phải thật sự hỏi Postgres"


async def test_health_ready_is_ok_with_real_services(api_client: httpx.AsyncClient) -> None:
    """Đủ Postgres, hai Redis và kho thật → 200."""
    response = await api_client.get(READY)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_health_ready_result_is_cached(api_client: httpx.AsyncClient, api_app: FastAPI) -> None:
    """Kết quả dùng lại trong 2 giây: probe của k8s gọi mỗi giây."""
    await api_client.get(READY)
    api_app.state.ready_cache = ReadyCache(until=api_app.state.clock.now() + READY_CACHE, healthy=False)
    assert (await api_client.get(READY)).status_code == 503


async def test_health_ready_recomputes_after_cache_expires(
    api_client: httpx.AsyncClient, api_app: FastAPI, fake_clock: FakeClock
) -> None:
    """Hết hạn cache thì kiểm lại thật, không giữ mãi kết quả cũ."""
    api_app.state.ready_cache = ReadyCache(until=fake_clock.now(), healthy=False)
    fake_clock.advance(READY_CACHE + timedelta(seconds=1))
    assert (await api_client.get(READY)).status_code == 200


async def test_health_ready_is_503_when_redis_is_down(api_app: FastAPI, api_client: httpx.AsyncClient) -> None:
    """Redis dừng → 503 `DEPENDENCY_UNAVAILABLE` kèm `Retry-After`, không lộ lý do."""
    dead = refused_url("redis")
    api_app.state.cache_redis = Redis.from_url(dead, socket_connect_timeout=1)
    api_app.state.safe_redis = Redis.from_url(dead, socket_connect_timeout=1)

    response = await api_client.get(READY)
    assert response.status_code == 503
    assert response.json()["code"] == "DEPENDENCY_UNAVAILABLE"
    assert int(response.headers["Retry-After"]) >= 1


async def test_app_refuses_a_broker_that_evicts_keys(
    api_env: None, fake_clock: FakeClock, redis_cache_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Broker chạy `allkeys-lru` là **mất việc**: app từ chối khởi động (BE-00 §1, NO-026)."""
    monkeypatch.setenv("REDIS_BROKER_URL", redis_cache_url)
    reset_messaging_settings_cache()
    app = create_app(get_core_settings(), token_verifier=FakeTokenVerifier(), clock=fake_clock)

    with pytest.raises(RuntimeError, match="noeviction"):
        async with make_api_client(app):
            pass


async def test_probe_returns_false_when_database_is_gone(api_app: FastAPI, api_client: httpx.AsyncClient) -> None:
    """Postgres đứt → `probe` trả `False` chứ không ném ra ngoài."""
    await api_app.state.engine.dispose(close=True)
    api_app.state.sessionmaker = _broken_sessionmaker()
    request = _request_of(api_app)
    assert await probe(request) is False


async def test_ready_rate_limit_is_by_ip(api_client: httpx.AsyncClient) -> None:
    """Endpoint công khai có hạn mức theo IP; hạn mức phải đủ rộng cho probe thật."""
    assert READY_LIMIT >= 60
    for _ in range(3):
        assert (await api_client.get(READY)).status_code == 200


def test_probe_key_is_a_valid_object_key() -> None:
    """Khoá canh phải qua được `check_key` của kho (BE-00 §8)."""
    from packages.storage.keys import check_key

    assert check_key(PROBE_KEY) == PROBE_KEY


def _broken_sessionmaker() -> object:
    """Sessionmaker luôn ném khi mở session — đủ để `probe` thấy phụ thuộc hỏng."""

    def broken() -> object:
        raise OSError("mất kết nối")

    return broken


def _request_of(app: FastAPI) -> Request:
    """Request tối thiểu mà `probe` cần: chỉ `scope["app"]`."""
    return Request({"type": "http", "app": app, "headers": []})


class _SlowStorage:
    """Kho trả lời chậm hơn hẳn trần của probe — dựng "phụ thuộc treo" mà không dừng dịch vụ."""

    async def stat(self, key: str) -> None:
        """Treo lâu hơn mọi trần hợp lý."""
        await asyncio.sleep(SLOW_S)


async def test_probe_gives_up_at_its_deadline(
    api_app: FastAPI, api_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Một phụ thuộc treo không giữ probe quá trần tổng: probe trả "chưa sẵn sàng".

    `wait_for` với trần rộng chỉ là lưới an toàn của test: bỏ trần tổng khỏi `probe` thì
    lưới này nổ `TimeoutError` và test đỏ, không phải chờ hết `SLOW_S`.
    """
    api_app.state.storage = _SlowStorage()
    monkeypatch.setattr(health_router, "PROBE_TIMEOUT_S", 0.1)
    assert await asyncio.wait_for(probe(_request_of(api_app)), timeout=GUARD_S) is False
