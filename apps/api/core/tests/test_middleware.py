"""Bốn lớp middleware ASGI: id request, log truy cập, header bảo mật, trần thân."""

import logging
from collections.abc import AsyncIterator
from typing import Final

import httpx
import pytest

from apps.api.core.auth import Principal
from apps.api.core.middleware import (
    CACHE_CONTROL,
    NO_STORE,
    REQUEST_ID_RE,
    SECURITY_HEADERS,
    _content_length,
    incoming_request_id,
    new_request_id,
)
from apps.api.core.routing import DEFAULT_BODY_LIMIT
from apps.api.core.tests.sample import sample_app, sample_client
from packages.testing.fixtures.api import auth_headers

__all__ = ["sample_app", "sample_client"]

GIVEN_ID: Final = "abc-123-def-456"
CHUNK: Final = b"y" * 65536


def _headers(principal: Principal) -> dict[str, str]:
    """Header `Authorization` của người gọi mẫu."""
    return auth_headers(principal)


def _scope(headers: list[tuple[bytes, bytes]]) -> dict[str, object]:
    """Scope ASGI tối thiểu chỉ có header."""
    return {"type": "http", "headers": headers}


def test_new_request_id_matches_pattern() -> None:
    """Id sinh ra phải hợp mẫu W6 để FE gửi lại được."""
    assert REQUEST_ID_RE.fullmatch(new_request_id())


def test_incoming_request_id_keeps_valid_header() -> None:
    """Id đúng mẫu W6 được giữ nguyên để nối log hai phía FE và BE."""
    assert incoming_request_id(_scope([(b"x-request-id", GIVEN_ID.encode())])) == GIVEN_ID


def test_incoming_request_id_replaces_bad_header() -> None:
    """Sai mẫu (quá ngắn, ký tự lạ) → sinh mới, không bao giờ trả lại nguyên trạng."""
    assert incoming_request_id(_scope([(b"x-request-id", b"x")])) != "x"
    assert incoming_request_id(_scope([(b"x-request-id", b"co dau cach!")])) != "co dau cach!"


def test_incoming_request_id_when_missing() -> None:
    """Không có header thì vẫn luôn có id."""
    assert len(incoming_request_id(_scope([]))) >= 8


async def test_request_id_is_echoed(sample_client: httpx.AsyncClient) -> None:
    """W6: id hợp lệ của FE được trả lại nguyên vẹn."""
    response = await sample_client.get("/api/sample/public", headers={"X-Request-Id": GIVEN_ID})
    assert response.headers["X-Request-Id"] == GIVEN_ID
    assert response.json() == {"name": "public"}


async def test_request_id_present_on_errors(sample_client: httpx.AsyncClient, fake_principal: Principal) -> None:
    """500 cũng phải mang `X-Request-Id` và chính id đó nằm trong thân W7."""
    response = await sample_client.post("/api/sample/boom", json={"name": "a"}, headers=_headers(fake_principal))
    assert response.status_code == 500
    assert response.json()["requestId"] == response.headers["X-Request-Id"]


async def test_security_headers_on_every_response(sample_client: httpx.AsyncClient) -> None:
    """Bốn header của BE-00 §11 có mặt trên cả response thành công lẫn lỗi."""
    for path, expected in (("/api/sample/public", 200), ("/api/khong-co", 404)):
        response = await sample_client.get(path)
        assert response.status_code == expected
        for name, value in SECURITY_HEADERS:
            assert response.headers[name] == value
        assert response.headers[CACHE_CONTROL] == NO_STORE


async def test_access_log_hides_real_path(api_client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture) -> None:
    """K11: log truy cập ghi khuôn đường, không bao giờ ghi đường thật (app **thật**)."""
    hidden_part = "khong-duoc-vao-log"
    with caplog.at_level(logging.INFO, logger="apps.api.core.middleware"):
        await api_client.get(f"/api/files/{hidden_part}")
    records = [record for record in caplog.records if record.msg == "http_access"]
    assert records, "phải có đúng một dòng log truy cập"
    assert records[-1].routeTemplate == "/api/files/{token}"  # type: ignore[attr-defined]  # trường `extra` của lời gọi log
    assert all(hidden_part not in str(value) for value in records[-1].__dict__.values())


async def test_access_log_for_unmatched_path(
    sample_client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    """Đường không khớp route nào vẫn có dòng log, khuôn đường là `-`."""
    with caplog.at_level(logging.INFO, logger="apps.api.core.middleware"):
        await sample_client.get("/api/khong-khop-route-nao")
    records = [record for record in caplog.records if record.msg == "http_access"]
    assert records[-1].routeTemplate == "-"  # type: ignore[attr-defined]  # như trên


async def test_content_length_over_limit_is_413(sample_client: httpx.AsyncClient, fake_principal: Principal) -> None:
    """C12: `Content-Length` vượt trần → 413 ngay, handler không chạy."""
    response = await sample_client.post(
        "/api/sample/items",
        content=b"a" * (DEFAULT_BODY_LIMIT + 1),
        headers={**_headers(fake_principal), "Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json()["code"] == "PAYLOAD_TOO_LARGE"


async def test_streamed_body_over_limit_is_413(sample_client: httpx.AsyncClient, fake_principal: Principal) -> None:
    """Luồng không khai độ dài → đếm byte, vượt trần thì cũng 413."""

    async def body() -> AsyncIterator[bytes]:
        """Thân luồng không khai độ dài, lớn hơn trần."""
        for _ in range(DEFAULT_BODY_LIMIT // len(CHUNK) + 2):
            yield CHUNK

    response = await sample_client.post(
        "/api/sample/items",
        content=body(),
        headers={**_headers(fake_principal), "Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json()["code"] == "PAYLOAD_TOO_LARGE"


async def test_route_body_limit_is_per_route(sample_client: httpx.AsyncClient, fake_principal: Principal) -> None:
    """Route khai trần rộng hơn thì thân 2 MiB vẫn qua được (BE-00 §11)."""
    payload = '{"name": "' + "z" * (2 * 1024 * 1024) + '"}'
    response = await sample_client.post(
        "/api/sample/big",
        content=payload.encode(),
        headers={**_headers(fake_principal), "Content-Type": "application/json"},
    )
    assert response.status_code == 200


def test_content_length_of_scope() -> None:
    """`Content-Length` vắng hay không phải số → `None`, để lớp đếm byte tự lo."""
    assert _content_length(_scope([])) is None
    assert _content_length(_scope([(b"content-length", b"khong-phai-so")])) is None
    assert _content_length(_scope([(b"content-length", b"12")])) == 12
