"""C16 của #48 (nhãn NFC) và C11, C24 của N38 (hạn mức theo IP, chặn `Origin` lệch) — từng đỏ trước FIX-2450."""

import unicodedata

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.project_settings.tests.support import headers_of
from apps.api.share_links.router import OPEN_RATE_LIMIT
from apps.api.share_links.tests.test_routes import _create_link, _links_path, _setup

PROBES = OPEN_RATE_LIMIT + 1
"""Lượt thứ `OPEN_RATE_LIMIT + 1` trong một cửa sổ phải bị chặn."""


async def test_share_links_open__C11(api_client: httpx.AsyncClient) -> None:
    """Dò token lặp từ một IP: `OPEN_RATE_LIMIT` lượt đầu 404, lượt kế 429 `RATE_LIMITED` + `Retry-After`."""
    statuses = []
    for i in range(PROBES):
        response = await api_client.get(f"/api/share/probe-{i}")
        statuses.append(response.status_code)
    assert statuses[:-1] == [404] * OPEN_RATE_LIMIT
    assert statuses[-1] == 429
    assert response.json()["code"] == "RATE_LIMITED"
    assert "retry-after" in response.headers


async def test_share_links_open__C24(api_client: httpx.AsyncClient) -> None:
    """`Origin` lệch → 403 `ORIGIN_MISMATCH`."""
    response = await api_client.get("/api/share/any-token", headers={"Origin": "https://evil.example"})
    assert response.status_code == 403
    assert response.json()["code"] == "ORIGIN_MISMATCH"


async def test_share_links_create__C16(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Nhãn NFD → lưu và trả NFC (K20), kể cả khi đọc lại từ danh sách."""
    project, _, engineer, _, _ = await _setup(db_session)
    nfd = unicodedata.normalize("NFD", "Khách Hàng Ở Huế")
    link = await _create_link(api_client, project, engineer, label=nfd)
    nfc = unicodedata.normalize("NFC", nfd)
    assert link["label"] == nfc
    listed = (await api_client.get(_links_path(project), headers=headers_of(engineer))).json()
    assert listed[0]["label"] == nfc
