"""Nhánh hiếm của khung: scope không phải HTTP, thân không phải JSON, lỗi lệnh Redis.

Những đường này chỉ chạy khi có sự cố, nhưng đó đúng là lúc chúng phải đúng: một
middleware ném ở scope `lifespan` là app không khởi động được, còn một lỗi lệnh
Redis bị xếp nhầm thành 503 là che mất bug của chính mình (R-16).
"""

import hashlib
import hmac
import json
from collections.abc import Awaitable
from datetime import datetime, timedelta
from typing import Any, Final, cast
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.requests import Request
from starlette.types import Message, Receive, Scope, Send

from apps.api.core import openapi as openapi_module
from apps.api.core.auth import Principal
from apps.api.core.errors import validation_error
from apps.api.core.idempotency import _blocked, _Existing
from apps.api.core.jobs import MAX_BATCHES, run_purge_expired_idempotency
from apps.api.core.middleware import (
    AccessLogMiddleware,
    BodyLimitMiddleware,
    FinalErrorMiddleware,
    RequestIdMiddleware,
    SecurityHeadersMiddleware,
)
from apps.api.core.pagination import _b64, _canonical, _filters_digest, decode_cursor
from apps.api.core.ratelimit import key_ip, rate_limit
from apps.api.core.routing import _json_body
from apps.api.core.tests.sample import ItemOut, sample_app, sample_client, sample_row_ids
from packages.core.errors import AppError
from packages.core.keys import current_key
from packages.db.models.idempotency import STATE_COMPLETED, STATE_IN_PROGRESS, IdempotencyRecord
from packages.messaging.redis import AsyncRedis
from packages.testing.fixtures.api import auth_headers
from packages.testing.fixtures.clock import FakeClock

__all__ = ["sample_app", "sample_client"]

KEY: Final = "khoa-noi-bo-0001"
CURSOR_OP: Final = "sample_list_page"
ULID: Final = "01JABCDEFGHJKMNPQRSTVWXYZ0"

MIDDLEWARES: Final = (
    RequestIdMiddleware,
    AccessLogMiddleware,
    SecurityHeadersMiddleware,
    BodyLimitMiddleware,
    FinalErrorMiddleware,
)


def _request(body: bytes) -> Request:
    """Request tối thiểu có sẵn thân — `_json_body` chỉ gọi `await request.body()`."""
    request = Request({"type": "http", "method": "POST", "path": "/", "headers": []})
    request._body = body
    return request


# ---------------------------------------------------------------------------
# Middleware ở scope không phải HTTP
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("middleware", MIDDLEWARES, ids=lambda cls: cls.__name__)
async def test_middleware_passes_through_non_http_scope(middleware: Any) -> None:
    """Scope `lifespan`/`websocket` đi thẳng: middleware của ta chỉ nói về HTTP."""
    seen: list[Scope] = []

    async def inner(scope: Scope, receive: Receive, send: Send) -> None:
        seen.append(scope)

    async def receive() -> Message:
        return {"type": "lifespan.startup"}

    async def send(message: Message) -> None: ...

    await middleware(inner)({"type": "lifespan"}, receive, send)
    assert [scope["type"] for scope in seen] == ["lifespan"]


async def test_final_error_reraises_after_response_started() -> None:
    """Đã gửi `http.response.start` thì không dựng được response khác — phải ném tiếp."""

    async def inner(scope: Scope, receive: Receive, send: Send) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})
        raise RuntimeError("hỏng giữa chừng")

    sent: list[Message] = []

    async def send(message: Message) -> None:
        sent.append(message)

    async def receive() -> Message:
        return {"type": "http.request", "body": b""}

    with pytest.raises(RuntimeError, match="giữa chừng"):
        await FinalErrorMiddleware(inner)({"type": "http", "headers": []}, receive, send)
    assert len(sent) == 1


# ---------------------------------------------------------------------------
# Thân không phải JSON
# ---------------------------------------------------------------------------


async def test_json_body_of_empty_body() -> None:
    assert await _json_body(_request(b"")) is None


async def test_json_body_of_broken_json() -> None:
    """JSON hỏng đã thành 400 ở chỗ khác; guard chỉ cần không ném."""
    assert await _json_body(_request(b"{khong-phai-json")) is None


async def test_path_body_guard_ignores_non_object_body(
    sample_client: httpx.AsyncClient, fake_principal: Principal
) -> None:
    """Thân là mảng: guard W21 không có khoá nào để so, để Pydantic trả 422."""
    response = await sample_client.post(
        "/api/sample/projects/prj-1/items", json=[1, 2], headers=auth_headers(fake_principal)
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Thân lỗi
# ---------------------------------------------------------------------------


def test_validation_error_drops_field_outside_the_wire_pattern() -> None:
    """loc bắt đầu bằng chỉ số mảng ghép ra `field` sai mẫu W7 → bỏ hẳn khoá `field`."""
    exc = RequestValidationError([{"type": "missing", "loc": ("body", 0, "name"), "msg": "", "input": {}}])
    body = json.loads(bytes(validation_error(exc, "rid-12345678").body))
    assert body["code"] == "VALIDATION"
    assert "field" not in body


def test_validation_error_without_any_error_keeps_count() -> None:
    body = json.loads(bytes(validation_error(RequestValidationError([]), "rid-12345678").body))
    assert body == {"code": "VALIDATION", "requestId": "rid-12345678", "count": 0}


async def test_unknown_role_in_token_is_401(sample_client: httpx.AsyncClient) -> None:
    """Vai ngoài ba vai của hợp đồng → 401, không phải 500 (K34)."""
    response = await sample_client.get(
        "/api/sample/optional", headers={"Authorization": f"Bearer fake:usr_{ULID}:sid:owner"}
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Idempotency: nhánh hiếm
# ---------------------------------------------------------------------------


def test_blocked_without_row_asks_to_retry() -> None:
    """Dòng biến mất giữa hai lệnh → 503, không bao giờ chạy tiếp như chưa có gì."""
    with pytest.raises(AppError, match="IDEMPOTENCY_IN_PROGRESS"):
        _blocked(None, "digest")


def test_blocked_replay_without_body_is_internal() -> None:
    """Thân lớn hơn 1 MiB không lưu được → lượt lặp trả 500, **không** chạy lại handler."""
    record = _Existing(
        request_hash="digest",
        state=STATE_COMPLETED,
        status_code=200,
        content_type="application/json",
        response_body=None,
    )
    with pytest.raises(AppError, match="INTERNAL"):
        _blocked(record, "digest")


async def test_unstorable_status_deletes_the_record(
    sample_client: httpx.AsyncClient, sample_app: FastAPI, fake_principal: Principal
) -> None:
    """Handler trả 429: không lưu, để lượt sau chạy lại thật (BE-00 §7)."""
    headers = {**auth_headers(fake_principal), "Idempotency-Key": KEY}
    response = await sample_client.post("/api/sample/throttled", json={"name": "a"}, headers=headers)
    assert response.status_code == 429
    async with sample_app.state.sessionmaker() as session:
        assert (await session.execute(_count_stmt())).scalar_one() == 0


async def test_failed_commit_rolls_back(
    sample_client: httpx.AsyncClient, sample_app: FastAPI, fake_principal: Principal
) -> None:
    """Giao dịch hỏng mà handler nuốt lỗi: `commit()` ném → 500 và không ghi gì."""
    headers = {**auth_headers(fake_principal), "Idempotency-Key": KEY}
    response = await sample_client.post("/api/sample/broken-tx", json={"name": "a"}, headers=headers)
    assert response.status_code == 500
    assert await sample_row_ids(sample_app.state.sessionmaker) == []
    async with sample_app.state.sessionmaker() as session:
        assert (await session.execute(_count_stmt())).scalar_one() == 0


def _count_stmt() -> Any:
    from sqlalchemy import func, select

    return select(func.count()).select_from(IdempotencyRecord)


# ---------------------------------------------------------------------------
# Cursor, rate limit, metadata
# ---------------------------------------------------------------------------


def test_cursor_with_non_object_position_is_422(storage_env: None) -> None:
    """Cursor ký đúng nhưng vị trí không phải object → vẫn là 422, không AttributeError."""
    raw = _canonical({"o": CURSOR_OP, "f": _filters_digest({}), "p": 1})
    mac = hmac.new(current_key("cursor"), raw, hashlib.sha256).digest()
    with pytest.raises(AppError, match="CURSOR_INVALID"):
        decode_cursor(f"{_b64(raw)}.{_b64(mac)}", CURSOR_OP, {})


async def test_rate_limit_without_installed_store_is_a_programming_error() -> None:
    """Quên gọi `install` trong `lifespan` phải lộ ra ngay, không âm thầm cho qua."""
    dependency = rate_limit("x", limit=1, window_s=60, key=key_ip, store="cache", on_error="open")
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": [], "app": FastAPI()})
    with pytest.raises(RuntimeError, match="chưa được nạp"):
        await dependency(request)


async def test_redis_command_error_is_not_masked_as_503(
    sample_client: httpx.AsyncClient, cache_client: AsyncRedis, fake_principal: Principal
) -> None:
    """Lỗi **lệnh** Redis là bug của ta: phải nổi lên thành 500, không hoá thành 503 (R-16)."""
    # `redis-py` khai kiểu trả của mọi lệnh là `Awaitable | Any` (một lớp lệnh dùng chung
    # cho bản sync và bản async), nên nơi gọi phải tự nói mình chờ kiểu gì.
    await cast("Awaitable[int]", cache_client.hset("rl:sample_ip:127.0.0.1", "x", "1"))
    response = await sample_client.get("/api/sample/limited", headers=auth_headers(fake_principal))
    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL"


def test_embedded_scalar_body_has_no_path_mirror(sample_app: FastAPI) -> None:
    """Thân là tham số nhúng (không phải model): `body_mirrors_path` vẫn tính được."""
    operation = next(item for item in openapi_module.operations(sample_app) if item.op == "sample_write_scalar")
    assert operation.has_body is True
    assert operation.body_mirrors_path is False


def test_optional_fields_stop_at_self_reference() -> None:
    """Model tự tham chiếu không làm hàm dò đệ quy vô hạn."""

    class Node(BaseModel):
        name: str
        child: "Node | None" = None

    assert openapi_module._has_optional_fields(Node, frozenset()) is True
    assert openapi_module._has_optional_fields(Node, frozenset({Node})) is False


def test_optional_fields_found_only_in_a_nested_model() -> None:
    class Inner(BaseModel):
        note: str | None = None

    class Outer(BaseModel):
        inner: Inner

    assert openapi_module._has_optional_fields(Outer, frozenset()) is True


def test_response_flags_without_response_model() -> None:
    assert isinstance(openapi_module.operations()[0].returns_list, bool)


# ---------------------------------------------------------------------------
# Lịch dọn rác: trần vòng lặp
# ---------------------------------------------------------------------------


async def test_purge_stops_at_the_batch_ceiling(
    db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Quá trần vòng lặp thì lượt này dừng, lượt lịch sau làm tiếp (R-21)."""
    now = fake_clock.now()
    async with db_sessionmaker() as session:
        for index in range(MAX_BATCHES + 1):
            session.add(_expired(now, f"het-han-{index:04d}"))
        await session.commit()

    removed = await run_purge_expired_idempotency(db_sessionmaker, fake_clock, batch=1)
    assert removed == MAX_BATCHES
    assert await _remaining(db_sessionmaker) == 1


def _expired(now: datetime, key: str) -> IdempotencyRecord:
    return IdempotencyRecord(
        user_id=f"usr_{ULID}",
        method="POST",
        route_template="/api/sample/items",
        key=key,
        request_hash="0" * 64,
        state=STATE_IN_PROGRESS,
        claim_token=uuid4(),
        lease_until=now,
        expires_at=now - timedelta(seconds=1),
    )


async def _remaining(maker: async_sessionmaker[AsyncSession]) -> int:
    async with maker() as session:
        return int((await session.execute(_count_stmt())).scalar_one())


def test_item_out_is_a_wire_model() -> None:
    """Giữ `ItemOut` được dùng ở đây để import mẫu không bị coi là thừa."""
    assert ItemOut(name="a").model_dump() == {"name": "a"}
