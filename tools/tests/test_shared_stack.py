"""PERF-10 — test dùng thẳng Postgres/Redis/MinIO của stack f14 đang chạy, và các rào giữ dữ liệu f14.

Phần chạm dịch vụ thật đã có `tools/tests/test_services.py` (chạy được cả hai chế độ). Ở đây kiểm phần
**quyết định**: đọc biến, URL Postgres luôn về database `postgres`, khối Redis dời qua DB app và bị từ chối
khi sai chính sách/thiếu DB, chặn `CREATE`/`DROP` database không phải tên test. Redis là bản giả có chủ ý:
cái đang kiểm là lựa chọn DB và lượt `FLUSHDB`, không phải Redis (K23).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Self
from unittest.mock import MagicMock, patch

import pytest
import redis
from docker.errors import APIError  # type: ignore[import-untyped]  # không có stub

from packages.messaging.redis import with_db
from packages.testing.fixtures import db as db_fixtures
from packages.testing.fixtures import services
from packages.testing.fixtures.db import (
    SHARED_DB,
    TEMPLATE_DB,
    assert_test_database,
)
from packages.testing.fixtures.services import (
    REDIS_ROLE_DBS,
    SHARED_MINIO_ENV,
    SHARED_NETWORK_ENV,
    SHARED_POSTGRES_ENV,
    SHARED_REDIS_BROKER_ENV,
    XDIST_IDS_PER_WORKER,
    XDIST_WORKER_COUNT_ENV,
    refused_url,
)
from packages.testing.fixtures.storage import drop_own_bucket
from packages.testing.fixtures.worker_id import XDIST_WORKER_ENV

URL = "redis://10.9.0.3:6379/0"


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Không nối mạng Docker thật: cổng chạy ở chế độ dùng chung thì biến mạng có sẵn trong môi trường."""
    monkeypatch.delenv(SHARED_NETWORK_ENV, raising=False)


# --- đọc biến -----------------------------------------------------------------------


@pytest.mark.parametrize("value", [None, "", "   "])
def test_external_service__unset_or_blank_means_containers(monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    """Không đặt / rỗng → `None`: fixture dựng container như trước (CI không đổi)."""
    if value is None:
        monkeypatch.delenv(SHARED_POSTGRES_ENV, raising=False)
    else:
        monkeypatch.setenv(SHARED_POSTGRES_ENV, value)
    assert services.external_service(SHARED_POSTGRES_ENV) is None
    assert services.external_postgres_url() is None


def test_external_service__joins_the_stack_network_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """Có biến mạng → nối container verify vào mạng đó trước khi trả địa chỉ (IP trên mạng stack)."""
    monkeypatch.setenv(SHARED_NETWORK_ENV, "f14_appback")
    monkeypatch.setenv(SHARED_REDIS_BROKER_ENV, URL)
    with patch.object(services, "_join_network") as join:
        assert services.external_service(SHARED_REDIS_BROKER_ENV) == URL
    join.assert_called_once_with("f14_appback")


@pytest.mark.parametrize("database", ["appback", "postgres", "", "appback?sslmode=disable"])
def test_external_postgres_url__always_the_admin_database(monkeypatch: pytest.MonkeyPatch, database: str) -> None:
    """URL nào cũng về database `postgres`: `postgres_url` không bao giờ trỏ database của app."""
    monkeypatch.setenv(SHARED_POSTGRES_ENV, f"postgresql+asyncpg://app:p%40ss@10.9.0.2:5432/{database}")
    assert services.external_postgres_url() == "postgresql+asyncpg://app:p%40ss@10.9.0.2:5432/postgres"


def test_external_minio__secret_may_contain_commas(monkeypatch: pytest.MonkeyPatch) -> None:
    """`endpoint,access_key,secret_key`: tách hai dấu phẩy đầu, phần còn lại là khoá bí mật."""
    monkeypatch.setenv(SHARED_MINIO_ENV, "10.9.0.5:9000,root,se,cret")
    assert services.external_minio() == ("10.9.0.5:9000", "root", "se,cret")


# --- Redis ------------------------------------------------------------------------------


@pytest.mark.parametrize(("worker", "base"), [("", 1), ("gw0", 1), ("gw5", 6)])
def test_redis_db_base__skips_the_app_block(monkeypatch: pytest.MonkeyPatch, worker: str, base: int) -> None:
    """Redis ngoài: khối 0 (DB app dùng qua URL `/0` + vai) để lại, `gwN` dùng khối N + 1."""
    monkeypatch.setenv(XDIST_WORKER_ENV, worker)
    assert services.redis_db_base(services.REDIS_APP_BLOCKS) == base * REDIS_ROLE_DBS


@pytest.mark.parametrize(
    ("config", "problem"),
    [
        ({"maxmemory-policy": "noeviction", "databases": "128"}, None),
        ({"maxmemory-policy": "allkeys-lru", "databases": "128"}, "maxmemory-policy allkeys-lru ≠ noeviction"),
        ({"maxmemory-policy": "noeviction", "databases": "16"}, "databases 16 < 93"),
    ],
    ids=["ok", "policy", "databases"],
)
def test_external_redis_problem(monkeypatch: pytest.MonkeyPatch, config: dict[str, str], problem: str | None) -> None:
    """Sai chính sách hoặc thiếu DB cho khối app + mọi mã `gwN` của 6 tiến trình → không dùng."""
    monkeypatch.setenv(XDIST_WORKER_COUNT_ENV, "6")
    found = services.external_redis_problem(config, "noeviction")
    if problem is None:
        assert found is None
    else:
        assert found is not None
        assert found.startswith(problem)


def test_external_redis_problem__need_counts_app_block_and_every_worker_id() -> None:
    """Số 93 ở case `databases`: khối app + 6 tiến trình nhân `XDIST_IDS_PER_WORKER` mã, mỗi khối `REDIS_ROLE_DBS`."""
    assert (1 + 6 * XDIST_IDS_PER_WORKER) * REDIS_ROLE_DBS == 93


def test_external_redis__good_config_is_used(monkeypatch: pytest.MonkeyPatch) -> None:
    """Đúng chính sách, đủ DB → dùng URL của stack, không cảnh báo."""
    monkeypatch.setenv(XDIST_WORKER_COUNT_ENV, "6")
    monkeypatch.setenv(SHARED_REDIS_BROKER_ENV, URL)
    client = MagicMock()
    client.__enter__.return_value = client
    config = {"maxmemory-policy": "noeviction", "databases": "128"}
    client.config_get.side_effect = lambda name: {name: config[name]}
    with patch.object(redis.Redis, "from_url", return_value=client):
        assert services._external_redis(SHARED_REDIS_BROKER_ENV, "noeviction") == URL


def _docker_client(networks: list[dict[str, object]], connect_error: Exception | None = None) -> MagicMock:
    """Client Docker giả: `inspect_container` lần lượt trả các bộ mạng `networks`, `connect` ném `connect_error`."""
    client = MagicMock()
    client.api.inspect_container.side_effect = [{"NetworkSettings": {"Networks": n}} for n in networks]
    client.networks.get.return_value.connect.side_effect = connect_error
    return client


@pytest.mark.parametrize(
    ("networks", "error", "connects"),
    [
        ([{"bridge": {}, "f14_appback": {}}], None, 0),  # đã nối: không làm gì
        ([{"bridge": {}}], None, 1),  # chưa nối: nối
        ([{"bridge": {}}, {"bridge": {}, "f14_appback": {}}], APIError("đã có"), 1),  # tiến trình khác vừa nối
    ],
    ids=["đã-nối", "nối", "thua-đua"],
)
def test_join_network(networks: list[dict[str, object]], error: Exception | None, connects: int) -> None:
    """Sáu tiến trình xdist cùng nối container verify vào mạng stack: chỉ lỗi khi rốt cuộc vẫn chưa nối."""
    client = _docker_client(networks, error)
    with patch.object(services, "DockerClient") as docker:
        docker.return_value.client = client
        services._join_network.__wrapped__("f14_appback")
    assert client.networks.get.return_value.connect.call_count == connects


def test_join_network__real_failure_is_raised() -> None:
    """`connect` hỏng mà container vẫn ngoài mạng: nổi lỗi, không âm thầm nối IP không tới được."""
    client = _docker_client([{"bridge": {}}, {"bridge": {}}], APIError("mạng không có"))
    with patch.object(services, "DockerClient") as docker:
        docker.return_value.client = client
        with pytest.raises(APIError):
            services._join_network.__wrapped__("f14_appback")


def test_external_redis__unreachable_falls_back_to_a_container(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stack tắt giữa chừng: cảnh báo rồi về container riêng, không đỏ cả lượt."""
    monkeypatch.setenv(SHARED_REDIS_BROKER_ENV, f"{refused_url('redis')}/0")
    with pytest.warns(UserWarning, match="dùng container Redis riêng"):
        assert services._external_redis(SHARED_REDIS_BROKER_ENV, "noeviction") is None


@dataclass
class _FakeRedis:
    """Redis giả: ghi lại URL đã mở và DB đã `FLUSHDB`."""

    url: str
    flushed: list[str] = field(default_factory=list)

    def __enter__(self) -> Self:
        """Dùng được trong `with` như client thật."""
        return self

    def __exit__(self, *_: object) -> None:
        """Không có gì để đóng."""

    def flushdb(self) -> None:
        """Ghi lại lượt xoá DB của URL này."""
        self.flushed.append(self.url)


def test_shared_redis__external_flushes_and_uses_only_its_own_block(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`gw2` trên Redis ngoài: `FLUSHDB` đúng các DB của khối 3 rồi trả URL đầu khối; không dựng container nào."""
    monkeypatch.setenv(XDIST_WORKER_ENV, "gw2")
    flushed: list[str] = []

    def fake_from_url(url: str) -> _FakeRedis:
        """Thay `redis.Redis.from_url`: mỗi URL một client giả chung sổ ghi."""
        return _FakeRedis(url, flushed)

    with (
        patch.object(redis.Redis, "from_url", fake_from_url),
        patch.object(services, "_start") as start,
        services._shared_redis("noeviction", tmp_path_factory, URL) as url,
    ):
        assert url == with_db(URL, 3 * REDIS_ROLE_DBS)
    assert flushed == [with_db(URL, 3 * REDIS_ROLE_DBS + role) for role in range(REDIS_ROLE_DBS)]
    start.assert_not_called()
    assert min(int(u.rsplit("/", 1)[1]) for u in flushed) >= REDIS_ROLE_DBS  # không chạm khối app


# --- Postgres --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [TEMPLATE_DB, f"{TEMPLATE_DB}_gw0", SHARED_DB, f"{SHARED_DB}_gw11", "b_0123456789abcdef", "tpl_ab12", "t_ffff"],
)
def test_assert_test_database__test_names_pass(name: str) -> None:
    """Mọi tên `db.py` và `test_fixture_timings.py` tạo/xoá đều qua."""
    assert_test_database(name)


@pytest.mark.parametrize(
    "name",
    ["appback", "postgres", "template0", "template1", "appback_test_x", "b_", "b_XYZ", 'b_00" ; DROP DATABASE appback'],
)
def test_assert_test_database__refuses_anything_else(name: str) -> None:
    """Database của app, database hệ thống, tên lạc hay tiêm SQL: từ chối trước khi có kết nối nào."""
    with pytest.raises(RuntimeError, match="không phải tên test"):
        assert_test_database(name)


def test_create_and_drop_go_through_the_guard() -> None:
    """`_create_database`/`_drop_database` chặn trước khi mở kết nối (URL dưới không tới đâu cả)."""
    url = f"{refused_url('postgresql+asyncpg')}/postgres"
    with pytest.raises(RuntimeError, match="không phải tên test"):
        db_fixtures._create_database(url, "appback")
    with pytest.raises(RuntimeError, match="không phải tên test"):
        db_fixtures._drop_database(url, "appback")


# --- hai đường của từng fixture, độc lập với chế độ của lượt đang chạy ---------------------
# Cổng chạy ở chế độ dùng chung thì đường container không chạy, ở chế độ container thì đường ngoài không
# chạy: test dưới đây đặt/xoá biến tự mình để độ phủ không đổi theo việc stack f14 có bật hay không.


@contextmanager
def _fake_shared(_key: str, _factory: object, start: Callable[[], tuple[object, object]]) -> Iterator[object]:
    """`_shared_container` giả: gọi `start` như tiến trình tới trước, không file khoá, không Docker."""
    _container, value = start()
    yield value


def test_shared_postgres__external_skips_the_container(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> None:
    monkeypatch.setenv(SHARED_POSTGRES_ENV, "postgresql+asyncpg://u:p@10.9.0.2:5432/appback")
    with patch.object(services, "_shared_container") as shared, services.shared_postgres(tmp_path_factory) as url:
        assert url == services.external_postgres_url()
    shared.assert_not_called()


def test_shared_postgres__unset_starts_the_shared_container(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> None:
    monkeypatch.delenv(SHARED_POSTGRES_ENV, raising=False)
    pg = MagicMock()
    pg.get_connection_url.return_value = "postgresql+asyncpg://t:t@10.9.0.9:5432/test"
    with (
        patch.object(services, "_start", return_value=pg),
        patch.object(services, "PostgresContainer"),
        patch.object(services, "_shared_container", _fake_shared),
        services.shared_postgres(tmp_path_factory) as url,
    ):
        assert url == "postgresql+asyncpg://t:t@10.9.0.9:5432/test"


def test_shared_minio__external_skips_the_container(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> None:
    monkeypatch.setenv(SHARED_MINIO_ENV, "10.9.0.4:9000,key,se,cret")
    with patch.object(services, "_shared_container") as shared, services.shared_minio(tmp_path_factory) as cfg:
        assert cfg == ("10.9.0.4:9000", "key", "se,cret")
    shared.assert_not_called()


def test_shared_minio__unset_starts_the_shared_container(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> None:
    monkeypatch.delenv(SHARED_MINIO_ENV, raising=False)
    minio = MagicMock()
    minio.get_config.return_value = {"endpoint": "10.9.0.8:9000", "access_key": "a", "secret_key": "s"}
    with (
        patch.object(services, "_start", return_value=minio),
        patch.object(services, "MinioContainer"),
        patch.object(services, "_shared_container", _fake_shared),
        services.shared_minio(tmp_path_factory) as cfg,
    ):
        assert cfg == ("10.9.0.8:9000", "a", "s")


def test_external_minio_and_redis__unset_means_containers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(SHARED_MINIO_ENV, raising=False)
    monkeypatch.delenv(SHARED_REDIS_BROKER_ENV, raising=False)
    assert services.external_minio() is None
    assert services._external_redis(SHARED_REDIS_BROKER_ENV, "noeviction") is None


def test_drop_own_bucket__only_on_a_shared_minio(monkeypatch: pytest.MonkeyPatch) -> None:
    """MinIO riêng bị xoá cả khối nên không dọn; MinIO dùng chung thì xoá object rồi bucket của chính test."""
    client = MagicMock()
    client.list_objects.return_value = [MagicMock(object_name="k.txt")]
    monkeypatch.delenv(SHARED_MINIO_ENV, raising=False)
    drop_own_bucket(client, "test-0a")
    client.remove_bucket.assert_not_called()
    monkeypatch.setenv(SHARED_MINIO_ENV, "10.9.0.4:9000,key,secret")
    drop_own_bucket(client, "test-0a")
    client.remove_object.assert_called_once_with("test-0a", "k.txt")
    client.remove_bucket.assert_called_once_with("test-0a")
