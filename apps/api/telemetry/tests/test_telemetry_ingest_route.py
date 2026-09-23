"""`POST /api/telemetry` — #37 (B7-01 [8]: C01, C11, C12, an toàn)."""

import json
import socket
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import event
from sqlalchemy.engine import Engine

from apps.api.core.app import create_app
from apps.api.core.auth import FakeTokenVerifier
from apps.api.telemetry import router as telemetry_router
from apps.api.telemetry.settings import get_telemetry_settings
from packages.core.settings import get_core_settings
from packages.observability.exporter import CONTENT_TYPE
from packages.observability.settings import reset_observability_settings_cache
from packages.testing.fixtures.api import make_api_client
from packages.testing.fixtures.clock import FakeClock

PATH = "/api/telemetry"


def _body(**overrides: object) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "sessionId": "sess-route",
        "sentAtMs": 1,
        "reason": "manual",
        "events": [],
        "droppedCount": 0,
        **overrides,
    }


@contextmanager
def _count_sql() -> Iterator[list[str]]:
    """Đếm câu SQL gửi xuống Postgres trong khối `with` — #37 phải là 0."""
    statements: list[str] = []

    def on_execute(_conn: Any, _cursor: Any, statement: str, *_rest: Any) -> None:
        statements.append(statement)

    event.listen(Engine, "before_cursor_execute", on_execute)
    try:
        yield statements
    finally:
        event.remove(Engine, "before_cursor_execute", on_execute)


async def test_telemetry_ingest_batch__C01(api_client: httpx.AsyncClient) -> None:
    body = _body(
        events=[
            {"sequence": 0, "atMs": 1, "event": {"name": "ai.started"}},
            {"sequence": 1, "atMs": 2, "event": {"name": "ai.finished", "durationMs": 100}},
            {"sequence": 2, "atMs": 3, "event": {"name": "wall.edit"}},
        ],
        droppedCount=2,
    )
    response = await api_client.post(PATH, json=body)
    assert response.status_code == 204
    assert response.content == b""


async def test_telemetry_ingest_batch__C11(api_client: httpx.AsyncClient) -> None:
    """`rate_limit` khai lúc nạp route; gửi đúng hạn mức rồi thêm một lượt → 429."""
    limit = telemetry_router._settings.telemetry_rate_limit
    body = _body()
    for _ in range(limit):
        response = await api_client.post(PATH, json=body)
        assert response.status_code == 204
    over = await api_client.post(PATH, json=body)
    assert over.status_code == 429
    assert 1 <= int(over.headers["retry-after"]) <= 10


async def test_telemetry_ingest_batch__C12_content_length(api_client: httpx.AsyncClient) -> None:
    max_bytes = get_telemetry_settings().telemetry_body_max_bytes
    oversized = b"x" * (max_bytes + 1)
    response = await api_client.post(PATH, content=oversized, headers={"content-type": "application/json"})
    assert response.status_code == 413


async def test_telemetry_ingest_batch__C12_streamed(api_client: httpx.AsyncClient) -> None:
    max_bytes = get_telemetry_settings().telemetry_body_max_bytes
    chunk = b"x" * 4096

    async def stream() -> AsyncIterator[bytes]:
        sent = 0
        while sent <= max_bytes:
            sent += len(chunk)
            yield chunk

    response = await api_client.post(PATH, content=stream(), headers={"content-type": "application/json"})
    assert response.status_code == 413


async def test_text_plain_beacon_fallback_is_accepted(api_client: httpx.AsyncClient) -> None:
    payload = json.dumps(_body()).encode("utf-8")
    response = await api_client.post(PATH, content=payload, headers={"content-type": "text/plain;charset=UTF-8"})
    assert response.status_code == 204


async def test_unsupported_content_type_is_422(api_client: httpx.AsyncClient) -> None:
    response = await api_client.post(PATH, json=_body(), headers={"content-type": "application/xml"})
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"


async def test_malformed_json_body_is_400(api_client: httpx.AsyncClient) -> None:
    response = await api_client.post(PATH, content=b"[" * 40_000, headers={"content-type": "application/json"})
    assert response.status_code == 400
    assert response.json()["code"] == "MALFORMED_JSON"


async def test_envelope_violation_is_422_with_field(api_client: httpx.AsyncClient) -> None:
    response = await api_client.post(PATH, json=_body(schemaVersion=2))
    assert response.status_code == 422
    assert response.json()["field"] == "schemaVersion"


async def test_foreign_origin_is_403(api_client: httpx.AsyncClient) -> None:
    response = await api_client.post(PATH, json=_body(), headers={"origin": "https://khac.example.com"})
    assert response.status_code == 403
    assert response.json()["code"] == "ORIGIN_MISMATCH"


async def test_missing_origin_is_still_204(api_client: httpx.AsyncClient) -> None:
    response = await api_client.post(PATH, json=_body())
    assert response.status_code == 204


async def test_garbage_authorization_header_is_still_204(api_client: httpx.AsyncClient) -> None:
    """#37 công khai: `Authorization` rác không gây 401 (không đọc header đó)."""
    response = await api_client.post(PATH, json=_body(), headers={"Authorization": "Bearer rac-hoan-toan"})
    assert response.status_code == 204


async def test_ingest_does_not_query_the_database(api_client: httpx.AsyncClient, api_app: FastAPI) -> None:
    with _count_sql() as statements:
        response = await api_client.post(PATH, json=_body())
    assert response.status_code == 204
    assert statements == []


async def test_one_hundred_batches_of_twenty_events_are_fast(api_client: httpx.AsyncClient) -> None:
    """100 lô 20 sự kiện < 2 s; trần khởi động ≤ 10 lô đầu, tổng ≤ `TELEMETRY_RATE_LIMIT`."""
    limit = telemetry_router._settings.telemetry_rate_limit
    batch_count = min(100, limit)
    events = [{"sequence": i, "atMs": i, "event": {"name": "wall.edit"}} for i in range(20)]
    body = _body(events=events)
    warmup = min(10, batch_count)
    for _ in range(warmup):
        await api_client.post(PATH, json=body)
    started = time.monotonic()
    for _ in range(batch_count - warmup):
        response = await api_client.post(PATH, json=body)
        assert response.status_code == 204
    elapsed = time.monotonic() - started
    assert elapsed < 2.0, f"{batch_count - warmup} lô mất {elapsed:.2f}s"


async def test_exporter_answers_during_lifespan_and_stops_after(
    monkeypatch: pytest.MonkeyPatch, api_env: None, fake_clock: FakeClock
) -> None:
    """`make_api_client(api_app)` với `METRICS_PORT` tự do → exporter trả lời trong lifespan, tắt sau."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()

    monkeypatch.setenv("METRICS_HOST", "127.0.0.1")
    monkeypatch.setenv("METRICS_PORT", str(port))
    reset_observability_settings_cache()
    app = create_app(get_core_settings(), token_verifier=FakeTokenVerifier(), clock=fake_clock)

    async with make_api_client(app):
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://127.0.0.1:{port}/metrics")
        assert response.status_code == 200
        assert response.headers["content-type"] == CONTENT_TYPE

    async with httpx.AsyncClient() as client:
        with pytest.raises(httpx.ConnectError):
            await client.get(f"http://127.0.0.1:{port}/metrics")
    reset_observability_settings_cache()
