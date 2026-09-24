"""packages/testing/fixtures/services.py — [8]: mỗi dịch vụ lên thật (K23: không mock)."""

from __future__ import annotations

import inspect
import io
import smtplib
import socket
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import asyncpg
import httpx
import pytest
import redis
import yaml
from minio import Minio

from packages.db.engine import GATE_CONNECT_TIMEOUT_S
from packages.testing.fixtures.services import (
    ephemeral_minio,
    ephemeral_postgres,
    ephemeral_redis,
    refused_url,
)

# Bản ephemeral đi cổng map của máy chủ Docker ở mọi nơi (FIX-009: IP bridge bị cấp lại ngay), nên bản đã
# dừng hỏng ngay: cổng host bị từ chối (111), IPv6 không tới (101) — đo 2026-09-22: 9/9 lượt, 0,0 s.
_STOPPED = r"^$|timed out|Errno (101|111)"
"""Lỗi hợp lệ của bản đã dừng: 111/101 (cổng host đóng), `''` (hết giờ của asyncpg) và `timed out`
(socket) khi chặng `host.docker.internal` kẹt (NO-007). Đều là `OSError`."""
_STOPPED_TIMEOUT_S = 5
"""Trần bắt tay tới bản **đã dừng**: chỉ để test không treo; mọi đường đều hỏng trong trần này."""
REPO_ROOT = Path(__file__).resolve().parents[2]


def _pg_dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def _select_one(url: str, *, connect_timeout_s: float = GATE_CONNECT_TIMEOUT_S) -> int:
    """`SELECT 1` qua kết nối mới; trần mặc định là của đường cổng (NO-042: chặng Docker có lúc kẹt ~68 s)."""
    conn = await asyncpg.connect(_pg_dsn(url), timeout=connect_timeout_s)
    try:
        value: int = await conn.fetchval("select 1")
        return value
    finally:
        await conn.close()


async def test_postgres_16_lên_thật(postgres_url: str) -> None:
    conn = await asyncpg.connect(_pg_dsn(postgres_url), timeout=GATE_CONNECT_TIMEOUT_S)
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
    host, port = eph.get_container_host_ip(), eph.get_exposed_port(6379)
    # Bản còn chạy chịu trần cổng (ephemeral đi `host.docker.internal`, NO-007); bản đã dừng trần ngắn.
    assert eph.get_client(socket_connect_timeout=GATE_CONNECT_TIMEOUT_S).ping()
    eph.stop()
    stopped = redis.Redis(host=host, port=port, socket_connect_timeout=_STOPPED_TIMEOUT_S)
    with pytest.raises((redis.exceptions.ConnectionError, redis.exceptions.TimeoutError)):
        stopped.ping()
    assert redis.Redis.from_url(redis_broker_url).ping()


async def test_ephemeral_postgres_dừng_xong_bản_dùng_chung_vẫn_chạy(postgres_url: str) -> None:
    eph = ephemeral_postgres()
    url = eph.get_connection_url()
    assert await _select_one(url) == 1
    eph.stop()
    with pytest.raises(OSError, match=_STOPPED):
        await _select_one(url, connect_timeout_s=_STOPPED_TIMEOUT_S)
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


def test_trần_bắt_tay_theo_trạng_thái_bản_postgres() -> None:
    """NO-042: bản còn chạy chịu trần cổng — chặng `host.docker.internal` có lúc kẹt ~68 s (NO-007).

    Bản đã dừng giữ trần ngắn: lỗi `Errno 101/111` tới ngay, trần chỉ để test không treo.
    """
    assert inspect.signature(_select_one).parameters["connect_timeout_s"].default == GATE_CONNECT_TIMEOUT_S
    assert _STOPPED_TIMEOUT_S < GATE_CONNECT_TIMEOUT_S


def test_container_verify_nối_thẳng_ip_container_dịch_vụ() -> None:
    """NO-007: trong container verify, testcontainers nối **thẳng** IP bridge của container dịch vụ.

    Đường `host.docker.internal` đi qua bộ chuyển tiếp cổng của Docker Desktop trên máy Windows.
    Đo 2026-09-21 (10 lượt, mỗi lượt 20 000 lần nối TCP, 16 song song): lượt bị từ chối hàng loạt và 6 lượt
    kẹt 69,4 tới 69,8 s; đường IP container cùng tải: 0 lỗi, không lượt nào quá 1,1 s. Hai container
    cùng mạng `bridge` mặc định nên tới được nhau. CI chạy ngoài container, không đặt biến này.
    """
    compose = yaml.safe_load((REPO_ROOT / "deploy" / "compose" / "verify.yml").read_text(encoding="utf-8"))
    service = compose["services"]["verify"]
    assert service["network_mode"] == "bridge"
    assert "TESTCONTAINERS_CONNECTION_MODE=bridge_ip" in service["environment"]


@pytest.mark.ci_integration
@pytest.mark.parametrize(
    ("factory", "port"),
    [(lambda: ephemeral_redis("noeviction"), 6379), (ephemeral_postgres, 5432), (ephemeral_minio, 9000)],
    ids=["redis", "postgres", "minio"],
)
def test_ephemeral_dừng_xong_địa_chỉ_không_về_tay_bản_dựng_sau(factory: Callable[[], Any], port: int) -> None:
    """FIX-009: địa chỉ của bản ephemeral đã dừng không trỏ sang container dựng ngay sau nó.

    Bridge mặc định của Docker cấp lại **ngay** IP vừa giải phóng: đi IP bridge thì bản B nhận đúng IP
    của A, URL của A nối được vào B (hay vào container của phiên verify khác — cùng ảnh, cùng mật khẩu
    mặc định), và test C13 thấy dịch vụ đã dừng "vẫn sống".
    """
    first = factory()
    endpoint = (first.get_container_host_ip(), int(first.get_exposed_port(port)))
    first.stop()
    second = factory()
    try:
        assert (second.get_container_host_ip(), int(second.get_exposed_port(port))) != endpoint
        with pytest.raises(OSError, match=_STOPPED):
            socket.create_connection(endpoint, timeout=_STOPPED_TIMEOUT_S)
    finally:
        second.stop()
