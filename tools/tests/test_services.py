"""packages/testing/fixtures/services.py — [8]: mỗi dịch vụ lên thật (K23: không mock)."""

from __future__ import annotations

import io
import smtplib
import socket
from urllib.parse import urlparse

import asyncpg
import httpx
import pytest
import redis
from minio import Minio

from packages.testing.fixtures.services import (
    ephemeral_minio,
    ephemeral_postgres,
    ephemeral_redis,
    refused_url,
)

# Container đã dừng: IPv4 của host.docker.internal từ chối (111), IPv6 không tới được (101);
# asyncpg / socket gộp các lỗi này thành OSError.
_STOPPED = r"Errno (101|111)"


def _pg_dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def _select_one(url: str) -> int:
    conn = await asyncpg.connect(_pg_dsn(url), timeout=5)
    try:
        value: int = await conn.fetchval("select 1")
        return value
    finally:
        await conn.close()


async def test_postgres_16_lên_thật(postgres_url: str) -> None:
    conn = await asyncpg.connect(_pg_dsn(postgres_url))
    try:
        version: str = await conn.fetchval("show server_version")
    finally:
        await conn.close()
    assert version.startswith("16")


@pytest.mark.parametrize(
    ("fixture", "policy"),
    [("redis_broker_url", "noeviction"), ("redis_cache_url", "allkeys-lru")],
)
def test_redis_maxmemory_policy(request: pytest.FixtureRequest, fixture: str, policy: str) -> None:
    client = redis.Redis.from_url(request.getfixturevalue(fixture), decode_responses=True)
    assert client.config_get("maxmemory-policy") == {"maxmemory-policy": policy}


def test_minio_ghi_đọc(minio_endpoint: tuple[str, str, str]) -> None:
    endpoint, access_key, secret_key = minio_endpoint
    client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=False)
    client.make_bucket("b0-01")
    data = b"xin chao"
    client.put_object("b0-01", "k.txt", io.BytesIO(data), len(data))
    resp = client.get_object("b0-01", "k.txt")
    try:
        assert resp.read() == data
    finally:
        resp.close()
        resp.release_conn()


def test_mailpit_nhận_thư(mailpit: tuple[str, int, int]) -> None:
    host, smtp_port, api_port = mailpit
    with smtplib.SMTP(host, smtp_port, timeout=10) as smtp:
        smtp.sendmail("a@example.test", ["b@example.test"], "Subject: B0-01\r\n\r\nxin chao")
    body = httpx.get(f"http://{host}:{api_port}/api/v1/messages", timeout=10).json()
    assert [m["Subject"] for m in body["messages"]] == ["B0-01"]


def test_ephemeral_redis_dừng_xong_bản_dùng_chung_vẫn_chạy(redis_broker_url: str) -> None:
    eph = ephemeral_redis("noeviction")
    client = eph.get_client(socket_connect_timeout=2)
    assert client.ping()
    eph.stop()
    with pytest.raises(redis.exceptions.ConnectionError):
        client.ping()
    assert redis.Redis.from_url(redis_broker_url).ping()


async def test_ephemeral_postgres_dừng_xong_bản_dùng_chung_vẫn_chạy(postgres_url: str) -> None:
    eph = ephemeral_postgres()
    url = eph.get_connection_url()
    assert await _select_one(url) == 1
    eph.stop()
    with pytest.raises(OSError, match=_STOPPED):
        await _select_one(url)
    assert await _select_one(postgres_url) == 1


def test_ephemeral_minio_dừng_xong_hỏng_kết_nối() -> None:
    eph = ephemeral_minio()
    cfg = eph.get_config()
    client = Minio(cfg["endpoint"], access_key=cfg["access_key"], secret_key=cfg["secret_key"], secure=False)
    assert client.bucket_exists("khong-co") is False
    host, port = cfg["endpoint"].rsplit(":", 1)
    eph.stop()
    with pytest.raises(OSError, match=_STOPPED):
        socket.create_connection((host, int(port)), timeout=2)


def test_refused_url_bị_từ_chối() -> None:
    url = urlparse(refused_url("redis"))
    assert url.scheme == "redis"
    assert url.hostname is not None
    assert url.port is not None
    with pytest.raises(ConnectionRefusedError):
        socket.create_connection((url.hostname, url.port), timeout=2)
