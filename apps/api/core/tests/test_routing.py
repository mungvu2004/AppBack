"""Thứ tự của `AppRoute`: xác thực → session → dependency → guard → commit (BE-00 §5, §7)."""

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Final

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.core.auth import Principal
from apps.api.core.routing import DEFAULT_BODY_LIMIT, AppRoute, PublicRoute, options_of, route_options
from apps.api.core.tests.sample import (
    after_commit_marks,
    build_sample_app,
    clear_after_commit_marks,
    sample_app,
    sample_client,
    sample_row_ids,
)
from packages.db.models.idempotency import IdempotencyRecord
from packages.messaging.celery_app import reset_producer_app
from packages.messaging.redis import BROKER_POLICY
from packages.messaging.settings import reset_messaging_settings_cache
from packages.testing.fixtures.api import auth_headers, make_api_client
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.services import ephemeral_redis

__all__ = ["clear_after_commit_marks", "sample_app", "sample_client"]

_log: Final = logging.getLogger(__name__)

CHUNK: Final = b"x" * 65536
HUGE_CHUNKS: Final = 1024
DEAD_BROKER_CEILING_S: Final = 1.0
"""BE-00 §7: callback sau commit không được giữ đường trả response."""


def _headers(principal: Principal) -> dict[str, str]:
    """Header `Authorization` của người gọi mẫu."""
    return auth_headers(principal)


async def test_public_route_needs_no_token(sample_client: httpx.AsyncClient) -> None:
    """Route công khai không đọc `Authorization` (khối [7] của B0-06)."""
    response = await sample_client.get("/api/sample/public")
    assert response.status_code == 200
    assert response.json() == {"name": "public"}


async def test_protected_route_without_token_is_401(sample_client: httpx.AsyncClient) -> None:
    """Thiếu `Authorization: Bearer` → 401 `UNAUTHENTICATED` (W10)."""
    response = await sample_client.post("/api/sample/items", json={"name": "a"})
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"


async def test_bad_scheme_is_401(sample_client: httpx.AsyncClient) -> None:
    """Header sai lược đồ (`Basic`) cũng là 401, không phải 400."""
    response = await sample_client.post("/api/sample/items", json={"name": "a"}, headers={"Authorization": "Basic abc"})
    assert response.status_code == 401


async def test_auth_runs_before_body_is_read(sample_app: FastAPI) -> None:
    """Thân 64 MiB không token → 401 và app đọc rất ít byte (W10: 401 trước 400)."""
    sent = 0

    async def body() -> AsyncIterator[bytes]:
        nonlocal sent
        for _ in range(HUGE_CHUNKS):
            sent += len(CHUNK)
            yield CHUNK

    async with make_api_client(sample_app) as client:
        response = await client.post("/api/sample/huge", content=body())
    assert response.status_code == 401
    assert sent <= len(CHUNK), f"app đã đọc {sent} byte thân trước khi trả 401"


async def test_path_body_mismatch_is_422(
    sample_client: httpx.AsyncClient, sample_app: FastAPI, fake_principal: Principal
) -> None:
    """W21: khoá thân camelCase lệch tham số đường → 422 `PATH_BODY_MISMATCH`, không ghi gì."""
    response = await sample_client.post(
        "/api/sample/projects/prj-1/items",
        json={"projectId": "prj-2", "name": "a"},
        headers=_headers(fake_principal),
    )
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "PATH_BODY_MISMATCH"
    assert body["field"] == "projectId"
    assert await sample_row_ids(sample_app.state.sessionmaker) == [], "guard chạy trước handler nên DB không đổi"


async def test_path_body_match_writes(
    sample_client: httpx.AsyncClient, sample_app: FastAPI, fake_principal: Principal
) -> None:
    """Khớp id thì handler chạy và ghi được commit (K22)."""
    response = await sample_client.post(
        "/api/sample/projects/prj-1/items",
        json={"projectId": "prj-1", "name": "a"},
        headers=_headers(fake_principal),
    )
    assert response.status_code == 200
    assert await sample_row_ids(sample_app.state.sessionmaker) == ["prj-1"]


async def test_versioned_route_without_base_version_is_428(
    sample_client: httpx.AsyncClient, fake_principal: Principal
) -> None:
    """Thiếu `baseVersion` → 428 `PRECONDITION_REQUIRED`, không rơi vào 422 của Pydantic."""
    response = await sample_client.put(
        "/api/sample/versions/prj-1",
        json={"body": {"name": "a"}},
        headers=_headers(fake_principal),
    )
    assert response.status_code == 428
    assert response.json()["code"] == "PRECONDITION_REQUIRED"


async def test_versioned_route_negative_base_version_is_422(
    sample_client: httpx.AsyncClient, fake_principal: Principal
) -> None:
    """`baseVersion` âm qua được guard 428 rồi mới hỏng ở Pydantic (422 `VALIDATION`)."""
    response = await sample_client.put(
        "/api/sample/versions/prj-1",
        json={"baseVersion": -1, "body": {"name": "a"}},
        headers=_headers(fake_principal),
    )
    assert response.status_code == 422
    assert response.json()["field"] == "baseVersion"


async def test_versioned_route_ignores_idempotency_header(
    sample_client: httpx.AsyncClient, sample_app: FastAPI, fake_principal: Principal
) -> None:
    """Route GV không dùng bảng idempotency (BE-00 §7)."""
    headers = {**_headers(fake_principal), "Idempotency-Key": "abcdefgh"}
    payload = {"baseVersion": 1, "body": {"name": "a"}}
    first = await sample_client.put("/api/sample/versions/prj-1", json=payload, headers=headers)
    second = await sample_client.put("/api/sample/versions/prj-1", json=payload, headers=headers)
    assert (first.status_code, second.status_code) == (200, 200)
    assert await _idempotency_count(sample_app.state.sessionmaker) == 0


async def test_malformed_json_is_400(sample_client: httpx.AsyncClient, fake_principal: Principal) -> None:
    """JSON hỏng → 400 `MALFORMED_JSON` (W8: luôn có mã rõ)."""
    response = await sample_client.post(
        "/api/sample/items",
        content=b"{khong-phai-json",
        headers={**_headers(fake_principal), "Content-Type": "application/json"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "MALFORMED_JSON"


async def test_unknown_exception_is_500_without_stack(
    sample_client: httpx.AsyncClient, fake_principal: Principal
) -> None:
    """Ngoại lệ lạ → 500 `INTERNAL`, thân không có `Traceback`."""
    response = await sample_client.post("/api/sample/boom", json={"name": "a"}, headers=_headers(fake_principal))
    assert response.status_code == 500
    assert response.json() == {"code": "INTERNAL", "requestId": response.headers["X-Request-Id"]}
    assert "Traceback" not in response.text


async def test_after_commit_callbacks_finish_before_response(
    sample_client: httpx.AsyncClient,
    sample_app: FastAPI,
    fake_principal: Principal,
    clear_after_commit_marks: None,
) -> None:
    """`AppRoute` chờ `after_commit_idle` xong mới trả response (BE-00 §7)."""
    response = await sample_client.post(
        "/api/sample/after-commit", json={"name": "sau-commit"}, headers=_headers(fake_principal)
    )
    assert response.status_code == 200
    assert after_commit_marks == ["sau-commit"]
    assert await sample_row_ids(sample_app.state.sessionmaker) == ["sau-commit"]


async def test_handler_exception_rolls_back(
    sample_client: httpx.AsyncClient, sample_app: FastAPI, fake_principal: Principal
) -> None:
    """Ngoại lệ → rollback: bảng mẫu không còn dòng nào."""
    await sample_client.post("/api/sample/boom", json={"name": "a"}, headers=_headers(fake_principal))
    assert await sample_row_ids(sample_app.state.sessionmaker) == []


def test_route_options_rejects_big_body_with_idempotency() -> None:
    """Trần thân > 1 MiB mà vẫn `auto` → `ValueError` ngay lúc nạp module."""
    with pytest.raises(ValueError, match="idempotency='off'"):
        route_options(body_limit=DEFAULT_BODY_LIMIT + 1)


def test_route_options_rejects_zero_body_limit() -> None:
    with pytest.raises(ValueError, match="≥ 1 byte"):
        route_options(body_limit=0)


def test_options_of_defaults() -> None:
    """Endpoint không khai gì thì nhận mặc định của hiến chương."""

    async def endpoint() -> None: ...

    assert options_of(endpoint).body_limit == DEFAULT_BODY_LIMIT
    assert options_of(endpoint).idempotency == "auto"


def test_public_route_is_not_protected() -> None:
    """`PublicRoute` là `AppRoute` nhưng không bảo vệ (quét route dựa vào điều này)."""
    assert issubclass(PublicRoute, AppRoute)
    assert PublicRoute.protected is False
    assert AppRoute.protected is True


async def _idempotency_count(maker: async_sessionmaker[AsyncSession]) -> int:
    """Số dòng idempotency còn lại."""
    async with maker() as session:
        return int((await session.execute(select(func.count()).select_from(IdempotencyRecord))).scalar_one())


async def test_response_is_not_blocked_by_a_dead_broker(
    api_env: None, fake_clock: FakeClock, fake_principal: Principal, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Broker chết sau commit: callback chạy trên executor riêng, request khác vẫn xong nhanh.

    Callback sau commit là I/O **chặn** (`send_task`, `XADD`); chạy nó trên vòng sự
    kiện thì một broker treo là cả API treo (BE-00 §7). Dùng một Redis thật, đời
    sống ngắn, rồi dừng hẳn container — không mock (K23).
    """
    container = ephemeral_redis(BROKER_POLICY)
    url = f"redis://{container.get_container_host_ip()}:{container.get_exposed_port(6379)}/0"
    monkeypatch.setenv("REDIS_BROKER_URL", url)
    reset_messaging_settings_cache()
    reset_producer_app()
    app = build_sample_app(fake_clock)
    headers = _headers(fake_principal)

    try:
        async with make_api_client(app) as client:
            container.stop()
            started = time.perf_counter()
            blocked, other = await asyncio.gather(
                client.post("/api/sample/dead-broker", json={"name": "a"}, headers=headers),
                client.get("/api/sample/public"),
            )
            elapsed = time.perf_counter() - started
    finally:
        with suppress(Exception):
            container.stop()
        reset_messaging_settings_cache()
        reset_producer_app()

    _log.info("dead_broker_elapsed %.3fs", elapsed)  # BE-00 §12: số đo in bằng logging
    assert (blocked.status_code, other.status_code) == (200, 200)
    assert elapsed < DEAD_BROKER_CEILING_S, f"mất {elapsed:.3f}s, trần {DEAD_BROKER_CEILING_S}s"
