"""Giới hạn tốc độ: cửa sổ cố định, `Retry-After` kẹp 10 s, Redis hỏng (BE-00 §11, C11)."""

from typing import Final

import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis

from apps.api.core.auth import Principal
from apps.api.core.ratelimit import MAX_RETRY_AFTER_S, install, ip_bucket, key_ip, rate_limit, retry_after
from apps.api.core.tests.sample import LIMITED_QUOTA, sample_app, sample_client
from packages.core.ids import new_id
from packages.testing.fixtures.api import auth_headers
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.services import refused_url

__all__ = ["sample_app", "sample_client"]

IPV6_A: Final = "2001:db8:1:2::1"
IPV6_B: Final = "2001:db8:1:2::ffff"
IPV6_OTHER: Final = "2001:db8:1:3::1"


def test_ipv4_bucket_is_the_address() -> None:
    """IPv4 đếm theo đúng địa chỉ."""
    assert ip_bucket("10.1.2.3") == "10.1.2.3"


def test_ipv6_is_grouped_by_64() -> None:
    """Một khách IPv6 thường được cấp cả /64 nên phải đếm chung."""
    assert ip_bucket(IPV6_A) == ip_bucket(IPV6_B)
    assert ip_bucket(IPV6_A) != ip_bucket(IPV6_OTHER)


def test_non_ip_string_is_kept() -> None:
    """`request.client.host` không phải IP (socket unix) vẫn cho một khoá dùng được."""
    assert ip_bucket("khong-phai-ip") == "khong-phai-ip"


@pytest.mark.parametrize(("ttl", "expected"), [(-1, 1), (0, 1), (3, 3), (60, MAX_RETRY_AFTER_S)])
def test_retry_after_is_clamped(ttl: int, expected: int) -> None:
    """W9: FE tự thử lại trong 15 s nên `Retry-After` luôn bị kẹp dưới 10 s."""
    assert retry_after(ttl) == expected


def test_rate_limit_rejects_bad_quota() -> None:
    """Hạn mức 0 là khai route sai, hỏng lúc nạp module."""
    with pytest.raises(ValueError, match="phải"):
        rate_limit("x", limit=0, window_s=60, key=key_ip, store="cache", on_error="closed")


async def test_quota_then_429(sample_client: httpx.AsyncClient, fake_principal: Principal) -> None:
    """C11: đúng `limit` lượt qua, lượt kế tiếp 429 kèm `Retry-After` hợp lệ."""
    headers = auth_headers(fake_principal)
    for _ in range(LIMITED_QUOTA):
        assert (await sample_client.get("/api/sample/limited", headers=headers)).status_code == 200
    blocked = await sample_client.get("/api/sample/limited", headers=headers)
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "RATE_LIMITED"
    assert 1 <= int(blocked.headers["Retry-After"]) <= MAX_RETRY_AFTER_S


async def test_user_key_separates_buckets(
    sample_client: httpx.AsyncClient, fake_principal: Principal, fake_clock: FakeClock
) -> None:
    """`key_user` đếm theo người dùng: người thứ hai không bị người thứ nhất làm khoá."""
    other = Principal(user_id=new_id("usr", fake_clock), session_id="sid-khac", role="viewer")
    for _ in range(LIMITED_QUOTA + 1):
        await sample_client.get("/api/sample/limited-open", headers=auth_headers(fake_principal))
    assert (await sample_client.get("/api/sample/limited-open", headers=auth_headers(other))).status_code == 200


async def test_redis_down_is_503_when_closed_and_passes_when_open(
    sample_app: FastAPI, sample_client: httpx.AsyncClient, fake_principal: Principal
) -> None:
    """Redis chết **sau** khi app đã lên: `closed` chuyển 503, `open` cho qua và chỉ log.

    Hỏng hóc được dựng bằng client thật trỏ vào một cổng không ai nghe (`refused_url`),
    chứ không phải bằng mock (K23): đường đi vẫn là `redis-py` thật.
    """
    dead = refused_url("redis")
    install(
        sample_app,
        cache=Redis.from_url(dead, socket_connect_timeout=1),
        safe=Redis.from_url(dead, socket_connect_timeout=1),
    )
    headers = auth_headers(fake_principal)

    closed = await sample_client.get("/api/sample/limited", headers=headers)
    opened = await sample_client.get("/api/sample/limited-open", headers=headers)

    assert closed.status_code == 503
    assert closed.json()["code"] == "DEPENDENCY_UNAVAILABLE"
    assert opened.status_code == 200
