"""Fixture dịch vụ thật dùng chung (Postgres, 2 Redis, MinIO, Mailpit).

BE-00 §12, B0-01 [2]/[6]F. Ảnh ghim tag (K29, không `latest`). Phạm vi
`session`, khởi động **lười**: container chỉ dựng khi fixture được một test
thật sự yêu cầu.

FIX-114: Postgres và MinIO — hai thứ nặng nhất — dựng **một bản cho cả lượt
`pytest -n`**, không phải một bản mỗi tiến trình (`_shared_container`). NO-270: hai
Redis cũng vậy, mỗi tiến trình một khối DB (`redis_db_base`). Mailpit vẫn một bản mỗi
tiến trình: lý do ở docstring `_shared_container`.

Factory `ephemeral_*` (function, không phải fixture pytest): test tạo một bản
riêng để giả lập C13 (phụ thuộc hỏng) bằng cách gọi `.stop()`. **Chỉ dừng
được, không bật lại** — muốn hồi phục thì trỏ client sang fixture dùng chung
ở trên, không khởi động lại bản đã dừng (K23: không mock chính dịch vụ đang
kiểm — ephemeral vẫn là container thật, chỉ đời sống ngắn hơn).
"""

from __future__ import annotations

import json
import os
import re
import socket
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from functools import cache
from typing import Any, cast

import pytest
from docker.errors import NotFound  # type: ignore[import-untyped]  # không có stub
from filelock import FileLock

# testcontainers 4.13 (bản trong uv.lock) không có py.typed, cũng không có gói stub
from testcontainers.core.config import (  # type: ignore[import-untyped]  # không có stub
    ConnectionMode,
    testcontainers_config,
)
from testcontainers.core.container import DockerContainer  # type: ignore[import-untyped]  # không có stub
from testcontainers.core.docker_client import DockerClient  # type: ignore[import-untyped]  # không có stub
from testcontainers.core.wait_strategies import HttpWaitStrategy  # type: ignore[import-untyped]  # không có stub
from testcontainers.minio import MinioContainer  # type: ignore[import-untyped]  # không có stub
from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]  # không có stub
from testcontainers.redis import RedisContainer  # type: ignore[import-untyped]  # không có stub

from packages.core.pinned_images import MINIO_IMAGE as MINIO_IMAGE
from packages.core.pinned_images import POSTGRES_IMAGE as POSTGRES_IMAGE
from packages.core.pinned_images import REDIS_IMAGE as REDIS_IMAGE
from packages.messaging.redis import BROKER_DB, CACHE_DB, SAFE_DB, STREAM_DB, with_db
from packages.testing.fixtures.worker_id import xdist_worker_id

MAILPIT_IMAGE = "axllent/mailpit:v1.20.0"

REDIS_ROLE_DBS = max(BROKER_DB, STREAM_DB, SAFE_DB, CACHE_DB) + 1
"""Số DB một tiến trình chiếm trên Redis dùng chung: đủ cho mọi vai của `packages/messaging/redis.py`."""
REDIS_DEFAULT_DATABASES = 16
"""`databases` mặc định của `redis-server`; Redis dùng chung nâng lên khối nhân số tiến trình khi cần."""
XDIST_WORKER_COUNT_ENV = "PYTEST_XDIST_WORKER_COUNT"
XDIST_IDS_PER_WORKER = 5
"""Số mã `gwN` một chỗ xdist có thể tiêu: bản đầu + 4 lượt thay tiến trình chết (`--max-worker-restart`
mặc định = 4 lần số tiến trình). execnet cấp mã tăng dần, không dùng lại, nên tiến trình thay thế mang
`gwN` với N ≥ số tiến trình — khối DB của nó vẫn phải có trên Redis dùng chung."""

SHARED_STATE_PREFIX = "shared-service-"

# Ryuk (bộ dọn của testcontainers) chạy **một bản mỗi tiến trình** và xoá mọi container mang nhãn
# phiên của tiến trình đó ngay khi tiến trình thoát. Dịch vụ dùng chung ở dưới sống lâu hơn tiến
# trình đã dựng nó, nên để Ryuk bật là nó giật mất dịch vụ khỏi những tiến trình còn đang chạy.
# Tắt Ryuk, dọn bằng bộ đếm người dùng của `_shared_container`; tắt luôn cũng bỏ được 6 container
# Ryuk. Phiên bị giết cứng (SIGKILL, OOM) để lại container dịch vụ: mỗi container mang nhãn chủ
# (`OWNER_LABEL`) và phiên kế dọn container có chủ đã chết (`sweep_orphans`, NO-281).
testcontainers_config.ryuk_disabled = True

OWNER_LABEL = "appback.test-owner"
"""Nhãn `<hostname>:<pid tiến trình điều khiển pytest>` trên mọi container dịch vụ của test."""

# Hostname mặc định của một container Docker là 12 ký tự hex đầu của id nó (container verify-run).
_CONTAINER_HOSTNAME = re.compile(r"[0-9a-f]{12}")


def session_owner() -> str:
    """Chủ của container dịch vụ: máy + tiến trình **điều khiển** của lượt pytest.

    Trong tiến trình xdist chủ là tiến trình cha (bộ điều khiển `pytest -n`) chứ không phải chính
    tiến trình con: container dùng chung sống lâu hơn tiến trình con đã dựng nó (`_shared_container`),
    nhưng không bao giờ lâu hơn bộ điều khiển.
    """
    pid = os.getppid() if xdist_worker_id() else os.getpid()
    return f"{socket.gethostname()}:{pid}"


def _owner_alive(owner: str, client: Any) -> bool:
    """Chủ còn sống không. Không chắc thì coi là sống — xoá nhầm là cắt dịch vụ của phiên khác.

    Cùng máy: hỏi pid (`os.kill(pid, 0)`; `PermissionError` = tiến trình có thật của người khác).
    Máy khác mà tên là hostname mặc định của container: chủ chết khi container đó không còn chạy
    (container verify-run đã thoát). Tên khác: không có cách hỏi → giữ. Ngưỡng đã biết: hai máy
    **cùng hostname** dùng chung một daemon Docker sẽ thấy pid của nhau là "chết" — verify-run (hostname
    = id container), CI (mỗi job một máy) và `run.sh shell` không rơi vào đó.
    """
    host, _, pid = owner.rpartition(":")
    if sys.platform == "win32":
        # `os.kill(pid, 0)` trên Windows là `TerminateProcess`, không phải phép hỏi; test chỉ chạy trên Linux
        return True
    if host == socket.gethostname():
        try:
            # Nhãn hỏng (pid không phải số) → không biết chủ → giữ, như mọi trường hợp không chắc
            with suppress(PermissionError, ValueError):
                os.kill(int(pid), 0)
        except ProcessLookupError:
            return False
        return True
    if _CONTAINER_HOSTNAME.fullmatch(host):
        return bool(client.containers.list(filters={"id": host}))
    return True


def sweep_orphans() -> list[str]:
    """Xoá container dịch vụ mà phiên pytest chủ của nó đã chết; trả id đã xoá (NO-281)."""
    client = DockerClient().client
    removed: list[str] = []
    for container in client.containers.list(all=True, filters={"label": OWNER_LABEL}):
        if not _owner_alive(container.labels[OWNER_LABEL], client):
            _remove_container(container.id)
            removed.append(container.id)
    return removed


@cache
def _sweep_once() -> None:
    """`sweep_orphans` một lần mỗi tiến trình, ngay trước container đầu tiên nó dựng."""
    sweep_orphans()


def _start[ContainerT: DockerContainer](container: ContainerT) -> ContainerT:
    """Gắn nhãn chủ rồi khởi động — mọi container dịch vụ của test đi qua đây.

    `with_kwargs` của testcontainers **thay** cả bộ kwargs, nên gộp với cái đã có; testcontainers tự
    thêm nhãn phiên của nó vào `labels` lúc chạy. Chạm `_kwargs` riêng của testcontainers 4.13 (như
    `_via_mapped_port`): nâng testcontainers thì chạy lại `tools/tests/test_orphan_sweep.py`.
    """
    _sweep_once()
    container.with_kwargs(**{**container._kwargs, "labels": {OWNER_LABEL: session_owner()}})
    return cast(ContainerT, container.start())


def _redis(policy: str, databases: int = REDIS_DEFAULT_DATABASES) -> RedisContainer:
    """Redis ảnh ghim với chính sách bộ nhớ `policy` và `databases` DB, **chưa** khởi động."""
    container = RedisContainer(REDIS_IMAGE)
    container.with_command(f"redis-server --maxmemory-policy {policy} --databases {databases}")
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
    """URL `redis://host:port/0` của container Redis đã chạy."""
    host = container.get_container_host_ip()
    port = container.get_exposed_port(6379)
    return f"redis://{host}:{port}/0"


def _remove_container(container_id: str) -> None:
    """Xoá cứng một container theo id — người gọi là người dùng **cuối**, không hẳn người đã dựng.

    `NotFound` là đích đã đạt chứ không phải lỗi: container có thể đã biến mất (Docker khởi động
    lại, ai đó dọn tay). Để nó nổi lên là một lượt chạy sạch hoá thành lỗi teardown của fixture
    phiên, ngay lúc đang giữ `FileLock` (review F-2). Mọi lỗi Docker khác vẫn nổi lên (R-16).
    """
    with suppress(NotFound):
        DockerClient().client.containers.get(container_id).remove(force=True)


@contextmanager
def _shared_container[ValueT](
    key: str,
    tmp_path_factory: pytest.TempPathFactory,
    start: Callable[[], tuple[DockerContainer, ValueT]],
) -> Iterator[ValueT]:
    """Một container dịch vụ cho **cả** lượt `pytest -n`, thay vì một bản mỗi tiến trình (FIX-114).

    Tiến trình tới trước dựng container rồi ghi địa chỉ của nó ra `<gốc>/shared-service-<key>.json`;
    tiến trình sau đọc lại. Gốc là **thư mục cha** của basetemp: xdist cho mỗi tiến trình một
    basetemp con (`popen-gw0`…) dưới đúng một gốc mỗi lượt chạy, nên file không rò sang lượt khác.
    `FileLock` bọc cả đọc-sửa-ghi vì sáu tiến trình khởi động gần như cùng lúc.

    Dọn theo **bộ đếm người dùng**, không theo "ai dựng thì người đó xoá": tiến trình dựng có thể
    xong trước những tiến trình khác, và xoá lúc đó là cắt dịch vụ ngay giữa lượt chạy của họ.
    Người rời cuối cùng (đếm về 0) xoá container theo id đã ghi trong file.

    Chỉ dùng được cho dịch vụ đã **tự cô lập theo tiến trình hay theo test**: Postgres (một
    database mỗi tiến trình, `db.py`), MinIO (một bucket mỗi test, `storage.py`) và Redis (một
    khối DB mỗi tiến trình, `redis_db_base`; vai là độ lệch trên DB của URL, `with_db`). Mailpit
    thì không, vì `mailpit_inbox` dọn **cả** hộp thư — nó giữ một bản mỗi tiến trình.

    Ngoài xdist (chạy tay, `-p no:xdist`) không có gì để chia: dựng thẳng rồi dừng như trước.
    """
    if not xdist_worker_id():
        container, value = start()
        try:
            yield value
        finally:
            container.stop()
        return

    state = tmp_path_factory.getbasetemp().parent / f"{SHARED_STATE_PREFIX}{key}.json"
    lock = FileLock(f"{state}.lock")
    data: dict[str, Any]
    with lock:
        if state.exists():
            data = json.loads(state.read_text(encoding="utf-8"))
            data["users"] += 1
        else:
            container, value = start()
            data = {"users": 1, "value": value, "id": container.get_wrapped_container().id}
        state.write_text(json.dumps(data), encoding="utf-8")
    try:
        yield cast(ValueT, data["value"])
    finally:
        with lock:
            data = json.loads(state.read_text(encoding="utf-8"))
            data["users"] -= 1
            if data["users"] == 0:
                # Xoá file **cùng lúc** xoá container, trong cùng lượt giữ khoá: để lại file với
                # `users: 0` là tiến trình nhận fixture lần đầu muộn hơn (xdist tắt tiến trình đã
                # hết việc trước khi cả phiên xong) sẽ đi nhánh `state.exists()` và dùng endpoint
                # của container đã bị xoá — "connection refused" không nói vì sao (review F-1).
                # Không có file thì nó dựng container mới, đúng như tiến trình đầu tiên.
                state.unlink(missing_ok=True)
                _remove_container(data["id"])
            else:
                state.write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture(scope="session")
def postgres_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """Một Postgres cho cả lượt chạy; mỗi tiến trình xdist đã có database riêng (`db.py`)."""

    def start() -> tuple[DockerContainer, str]:
        """Dựng container Postgres dùng chung và trả (container, URL)."""
        pg = _start(PostgresContainer(POSTGRES_IMAGE, driver="asyncpg"))
        return pg, str(pg.get_connection_url())

    with _shared_container("postgres", tmp_path_factory, start) as url:
        yield url


def redis_db_base() -> int:
    """DB gốc của tiến trình này trên Redis dùng chung: `gwN` → khối thứ N; ngoài xdist → 0 (NO-270).

    Mỗi khối rộng `REDIS_ROLE_DBS` nên mọi vai `with_db` dời lên (kể cả test lấy URL cache làm URL
    broker) vẫn nằm trong khối của chính tiến trình.
    """
    worker = xdist_worker_id()
    return int(worker.removeprefix("gw")) * REDIS_ROLE_DBS if worker else 0


@contextmanager
def _shared_redis(policy: str, tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """Một Redis chính sách `policy` cho cả lượt `pytest -n`; URL trỏ vào khối DB của tiến trình này."""

    def start() -> tuple[DockerContainer, str]:
        """Dựng container Redis dùng chung, đủ một khối DB cho mỗi tiến trình xdist; trả (container, URL `/0`)."""
        ids = int(os.environ.get(XDIST_WORKER_COUNT_ENV, "1")) * XDIST_IDS_PER_WORKER
        container = _start(_redis(policy, max(REDIS_DEFAULT_DATABASES, REDIS_ROLE_DBS * ids)))
        return container, _redis_url(container)

    with _shared_container(f"redis-{policy}", tmp_path_factory, start) as url:
        yield with_db(url, redis_db_base())


@pytest.fixture(scope="session")
def redis_broker_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """URL Redis (chính sách `noeviction`) cho broker Celery, dùng chung cả lượt chạy."""
    with _shared_redis("noeviction", tmp_path_factory) as url:
        yield url


@pytest.fixture(scope="session")
def redis_cache_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """URL Redis (chính sách `allkeys-lru`) cho cache, dùng chung cả lượt chạy."""
    with _shared_redis("allkeys-lru", tmp_path_factory) as url:
        yield url


@pytest.fixture(scope="session")
def minio_endpoint(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[str, str, str]]:
    """Trả (endpoint `host:port`, access_key, secret_key) — một MinIO cho cả lượt chạy.

    Dùng chung được vì `s3_storage` tạo **một bucket mỗi test** với tên ngẫu nhiên, nên hai tiến
    trình xdist không bao giờ chạm cùng bucket.
    """

    def start() -> tuple[DockerContainer, list[str]]:
        """Dựng container MinIO dùng chung và trả (container, cấu hình S3)."""
        minio = _start(MinioContainer(MINIO_IMAGE))
        cfg = minio.get_config()
        # list chứ không tuple: giá trị đi qua JSON của `_shared_container`, mà JSON không có tuple
        return minio, [cfg["endpoint"], cfg["access_key"], cfg["secret_key"]]

    with _shared_container("minio", tmp_path_factory, start) as cfg:
        endpoint, access_key, secret_key = cfg
        yield endpoint, access_key, secret_key


@pytest.fixture(scope="session")
def mailpit() -> Iterator[tuple[str, int, int]]:
    """Trả (host, cổng SMTP, cổng HTTP API `/api/v1/messages`).

    Tắt rDNS (`MP_SMTP_DISABLE_RDNS`): mặc định Mailpit tra PTR của client trước khi
    nhận thư; DNS chậm của máy chạy test (~11 s) làm quá `SMTP_TIMEOUT_S`. Bỏ tra
    cứu để test không phụ thuộc DNS của máy.
    """
    container = (
        DockerContainer(MAILPIT_IMAGE)
        .with_env("MP_SMTP_DISABLE_RDNS", "true")
        .with_exposed_ports(1025, 8025)
        .waiting_for(HttpWaitStrategy(8025, "/api/v1/info"))
    )
    _start(container)
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
    """Postgres tạm cho một test, đi qua cổng đã ánh xạ."""
    return _start(_via_mapped_port(PostgresContainer(POSTGRES_IMAGE, driver="asyncpg")))


def ephemeral_redis(policy: str) -> RedisContainer:
    """Redis tạm cho một test với chính sách `policy`, đi qua cổng đã ánh xạ."""
    return _start(_via_mapped_port(_redis(policy)))


def ephemeral_minio() -> MinioContainer:
    """MinIO tạm cho một test, đi qua cổng đã ánh xạ."""
    return _start(_via_mapped_port(MinioContainer(MINIO_IMAGE)))
