"""Fixture dịch vụ thật dùng chung (Postgres, 2 Redis, MinIO, Mailpit).

BE-00 §12, B0-01 [2]/[6]F. Ảnh ghim tag (K29, không `latest`). Phạm vi
`session`, khởi động **lười**: container chỉ dựng khi fixture được một test
thật sự yêu cầu (pytest-xdist mỗi tiến trình tự dựng bản của mình).

Factory `ephemeral_*` (function, không phải fixture pytest): test tạo một bản
riêng để giả lập C13 (phụ thuộc hỏng) bằng cách gọi `.stop()`. **Chỉ dừng
được, không bật lại** — muốn hồi phục thì trỏ client sang fixture dùng chung
ở trên, không khởi động lại bản đã dừng (K23: không mock chính dịch vụ đang
kiểm — ephemeral vẫn là container thật, chỉ đời sống ngắn hơn).
"""

from __future__ import annotations

import socket
from collections.abc import Iterator

import pytest

# testcontainers 4.13 (bản trong uv.lock) không có py.typed, cũng không có gói stub
from testcontainers.core.config import ConnectionMode  # type: ignore[import-untyped]
from testcontainers.core.container import DockerContainer  # type: ignore[import-untyped]
from testcontainers.core.wait_strategies import HttpWaitStrategy  # type: ignore[import-untyped]
from testcontainers.minio import MinioContainer  # type: ignore[import-untyped]
from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]
from testcontainers.redis import RedisContainer  # type: ignore[import-untyped]

POSTGRES_IMAGE = "postgres:16-alpine"
REDIS_IMAGE = "redis:7-alpine"
# Docker Hub minio/minio không còn phát hành bản cộng đồng; quay.io là nguồn chính thức.
MINIO_IMAGE = "quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z"
MAILPIT_IMAGE = "axllent/mailpit:v1.20.0"


def _redis(policy: str) -> RedisContainer:
    """Redis ảnh ghim với chính sách bộ nhớ `policy`, **chưa** khởi động."""
    container = RedisContainer(REDIS_IMAGE)
    container.with_command(f"redis-server --maxmemory-policy {policy}")
    return container


def _via_mapped_port(container: DockerContainer) -> DockerContainer:
    """Cho bản ephemeral nối qua cổng map của máy chủ Docker, không qua IP bridge (FIX-009).

    Bridge mặc định cấp lại **ngay** IP vừa giải phóng (đo 2026-09-22: dừng A `172.17.0.11`, container
    kế nhận `172.17.0.11`), nên sau `.stop()` URL IP của bản ephemeral trỏ được vào container của phiên
    verify khác — cùng ảnh, cùng mật khẩu mặc định — và test C13 thấy dịch vụ đã dừng "vẫn sống". Cổng
    host thì Docker cấp tiếp chứ không cấp lại ngay. Đường này qua `host.docker.internal` (NO-007) nhưng
    mỗi bản ephemeral chỉ vài kết nối; bản dùng chung vẫn đi IP bridge. Ghi đè `get_connection_mode` trên
    `DockerClient` riêng của container (testcontainers 4.13 dựng một client mỗi container, mọi đường lấy
    host/cổng đều hỏi nó): nâng testcontainers thì chạy lại `tools/tests/test_services.py`.
    """
    container.get_docker_client().get_connection_mode = lambda: ConnectionMode.docker_host
    return container


def _redis_url(container: RedisContainer) -> str:
    host = container.get_container_host_ip()
    port = container.get_exposed_port(6379)
    return f"redis://{host}:{port}/0"


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    with PostgresContainer(POSTGRES_IMAGE, driver="asyncpg") as pg:
        yield pg.get_connection_url()


@pytest.fixture(scope="session")
def redis_broker_url() -> Iterator[str]:
    container = _redis("noeviction").start()
    try:
        yield _redis_url(container)
    finally:
        container.stop()


@pytest.fixture(scope="session")
def redis_cache_url() -> Iterator[str]:
    container = _redis("allkeys-lru").start()
    try:
        yield _redis_url(container)
    finally:
        container.stop()


@pytest.fixture(scope="session")
def minio_endpoint() -> Iterator[tuple[str, str, str]]:
    """Trả (endpoint `host:port`, access_key, secret_key)."""
    with MinioContainer(MINIO_IMAGE) as m:
        cfg = m.get_config()
        yield cfg["endpoint"], cfg["access_key"], cfg["secret_key"]


@pytest.fixture(scope="session")
def mailpit() -> Iterator[tuple[str, int, int]]:
    """Trả (host, cổng SMTP, cổng HTTP API `/api/v1/messages`)."""
    container = (
        DockerContainer(MAILPIT_IMAGE)
        .with_exposed_ports(1025, 8025)
        .waiting_for(HttpWaitStrategy(8025, "/api/v1/info"))
    )
    container.start()
    try:
        host = container.get_container_host_ip()
        yield host, int(container.get_exposed_port(1025)), int(container.get_exposed_port(8025))
    finally:
        container.stop()


def refused_url(scheme: str) -> str:
    """URL tới một cổng localhost đóng (không ai lắng nghe) — dùng cho C13."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    return f"{scheme}://127.0.0.1:{port}"


def ephemeral_postgres() -> PostgresContainer:
    return _via_mapped_port(PostgresContainer(POSTGRES_IMAGE, driver="asyncpg")).start()


def ephemeral_redis(policy: str) -> RedisContainer:
    return _via_mapped_port(_redis(policy)).start()


def ephemeral_minio() -> MinioContainer:
    return _via_mapped_port(MinioContainer(MINIO_IMAGE)).start()
