"""Riêng `S3Storage`: MinIO thật (K23), URL ký phục vụ được, phụ thuộc hỏng (C13)."""

import asyncio
import errno
import hashlib
import logging
import re
import secrets
import tempfile
from collections.abc import Iterator
from datetime import UTC, datetime
from urllib.parse import urlsplit

import httpx
import pytest
from minio import Minio
from minio.error import S3Error

from packages.core.errors import AppError
from packages.storage import keys
from packages.storage.s3 import S3Storage, http_client
from packages.storage.tests.fault_proxy import Fault, FaultProxy, delete_error_xml, fault_proxy, s3_error_xml
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.services import ephemeral_minio, refused_url

PROJECT = "prj_01ARZ3NDEKTSV4RRFFQ69G5FAV"
FLOOR = "L-ABCDEFGHIJ"
UPLOAD = "upl_01ARZ3NDEKTSV4RRFFQ69G5FBW"
KEY = keys.upload_page(PROJECT, FLOOR, UPLOAD, 0)
PNG = b"\x89PNG\r\n\x1a\n" + b"pixels" * 8
MAX_BYTES = 64 * 1024 * 1024
PUBLIC_HOST = "files.appback.test:9000"
DELETE_BATCH = 1000
"""Trần khoá mỗi lượt `DeleteObjects` của S3 (`minio.remove_objects` gom theo trần này)."""
WRITE_CONCURRENCY = 8
"""Trần lượt ghi song song: dưới `maxsize=10` của pool `http_client`, không nghẽn MinIO dùng chung."""


def client_for(endpoint: str, access_key: str = "x" * 8, secret_key: str = "y" * 8) -> Minio:
    """Client `minio` trỏ `endpoint` (dạng `host:port`), vùng ghim nên ký không ra mạng."""
    return Minio(
        endpoint,
        access_key=access_key,
        secret_key=secret_key,
        secure=False,
        region="us-east-1",
        http_client=http_client(),
    )


def storage_on(client: Minio, bucket: str, clock: FakeClock, public: Minio | None = None) -> S3Storage:
    """Kho trên `bucket` cho trước; `public` khác `client` để kiểm host của URL ký."""
    return S3Storage(client=client, public_client=public or client, bucket=bucket, clock=clock)


async def test_signed_url_serves_the_object(s3_storage: S3Storage, fake_clock: FakeClock) -> None:
    """URL ký tải được thật, kèm `Content-Disposition: attachment` (BE-00 §8)."""
    fake_clock.set(datetime.now(UTC))  # MinIO từ chối URL ký bằng mốc 2026-01-01
    await s3_storage.put(KEY, PNG, content_type="image/png", max_bytes=MAX_BYTES)

    signed = await s3_storage.signed_url(KEY, disposition="attachment", filename="bản vẽ.png")
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(signed.url)

    assert response.status_code == 200
    assert response.content == PNG
    assert response.headers["content-disposition"].startswith("attachment")
    assert "ban ve.png" in response.headers["content-disposition"]


async def test_signed_url_uses_the_public_endpoint_without_network(
    minio_endpoint: tuple[str, str, str], fake_clock: FakeClock
) -> None:
    """Ký là phép tính cục bộ: host lấy từ `S3_PUBLIC_ENDPOINT`, không gọi MinIO."""
    endpoint, access_key, secret_key = minio_endpoint
    storage = storage_on(
        client_for(endpoint, access_key, secret_key),
        "bucket-nao-do",
        fake_clock,
        public=client_for(PUBLIC_HOST, access_key, secret_key),
    )

    signed = await storage.signed_url(KEY, disposition="attachment")

    assert urlsplit(signed.url).netloc == PUBLIC_HOST
    assert "X-Amz-Signature" in signed.url


async def test_multipart_upload_keeps_the_checksum(s3_storage: S3Storage) -> None:
    """Object 17 MiB đi đường multipart; `sha256` trong metadata vẫn đúng (M02)."""
    payload = PNG + b"\x00" * (17 * 1024 * 1024)
    written = await s3_storage.put(KEY, payload, content_type="image/png", max_bytes=MAX_BYTES)

    stored = await s3_storage.stat(KEY)

    assert stored is not None
    assert stored.size == len(payload)
    assert stored.sha256 == hashlib.sha256(payload).hexdigest() == written.sha256
    assert stored.kind == "png"


async def test_put_on_stopped_minio_returns_503(fake_clock: FakeClock) -> None:
    """C13: container thật bị dừng → 503 `DEPENDENCY_UNAVAILABLE` + `Retry-After`."""
    container = ephemeral_minio()
    config = container.get_config()
    client = client_for(config["endpoint"], config["access_key"], config["secret_key"])
    bucket = "bucket-ephemeral"
    client.make_bucket(bucket)
    storage = storage_on(client, bucket, fake_clock)
    await storage.put(KEY, PNG, content_type="image/png", max_bytes=MAX_BYTES)

    container.stop()

    with pytest.raises(AppError, match="DEPENDENCY_UNAVAILABLE") as raised:
        await storage.put(KEY, PNG, content_type="image/png", max_bytes=MAX_BYTES)
    assert raised.value.code.status == 503
    assert raised.value.retry_after == 5


async def test_refused_endpoint_returns_503(fake_clock: FakeClock) -> None:
    storage = storage_on(client_for(urlsplit(refused_url("http")).netloc), "bucket-nao-do", fake_clock)

    with pytest.raises(AppError, match="DEPENDENCY_UNAVAILABLE"):
        await storage.stat(KEY)


async def test_stat_does_not_turn_a_denied_request_into_a_missing_object(
    minio_endpoint: tuple[str, str, str], fake_clock: FakeClock
) -> None:
    """Sai khoá → `AccessDenied` phải nổi lên; chỉ `NoSuchKey` mới là `None`."""
    endpoint, access_key, _ = minio_endpoint
    storage = storage_on(client_for(endpoint, access_key, "sai-khoa-bi-mat"), "bucket-nao-do", fake_clock)

    with pytest.raises(S3Error, match="AccessDenied"):
        await storage.stat(KEY)


async def test_open_read_on_a_missing_bucket_raises(
    minio_endpoint: tuple[str, str, str], fake_clock: FakeClock
) -> None:
    """`NoSuchBucket` là sự cố cấu hình, không phải 404 của người dùng."""
    endpoint, access_key, secret_key = minio_endpoint
    storage = storage_on(client_for(endpoint, access_key, secret_key), "bucket-chua-tao-bao-gio", fake_clock)

    with pytest.raises(S3Error, match="NoSuchBucket"):
        [chunk async for chunk in storage.open_read(KEY)]


async def test_ensure_bucket_is_idempotent_and_survives_minio_cors(
    minio_endpoint: tuple[str, str, str], fake_clock: FakeClock, caplog: pytest.LogCaptureFixture
) -> None:
    """MinIO trả `NotImplemented` cho `PutBucketCors` → ghi log, không ném lỗi."""
    endpoint, access_key, secret_key = minio_endpoint
    storage = storage_on(client_for(endpoint, access_key, secret_key), "bucket-ensure", fake_clock)

    with caplog.at_level(logging.INFO, logger="packages.storage.s3"):
        await storage.ensure_bucket("https://appback.test")
        await storage.ensure_bucket("https://appback.test")

    assert [record.message for record in caplog.records] == ["cors_managed_by_server"] * 2
    await storage.put(KEY, PNG, content_type="image/png", max_bytes=MAX_BYTES)
    assert await storage.stat(KEY) is not None


@pytest.fixture
def proxied(minio_endpoint: tuple[str, str, str], fake_clock: FakeClock) -> Iterator[tuple[S3Storage, FaultProxy]]:
    """Kho trỏ qua proxy tiêm lỗi (`fault_proxy.py`), bucket riêng trên MinIO thật."""
    endpoint, access_key, secret_key = minio_endpoint
    bucket = f"test-{secrets.token_hex(6)}"
    client_for(endpoint, access_key, secret_key).make_bucket(bucket)
    with fault_proxy(endpoint) as proxy:
        yield storage_on(client_for(proxy.endpoint, access_key, secret_key), bucket, fake_clock), proxy


@pytest.mark.parametrize(("status", "code"), [(500, "InternalError"), (503, "SlowDown")])
async def test_server_error_with_xml_body_returns_503(
    proxied: tuple[S3Storage, FaultProxy], status: int, code: str
) -> None:
    """NO-009: 5xx **có thân XML** (S3 quá tải) → 503 + `Retry-After`, không lọt `S3Error` thô (C13)."""
    storage, proxy = proxied
    await storage.put(KEY, PNG, content_type="image/png", max_bytes=MAX_BYTES)
    proxy.faults.append(Fault("GET", status, s3_error_xml(code)))

    with pytest.raises(AppError, match="DEPENDENCY_UNAVAILABLE") as raised:
        [chunk async for chunk in storage.open_read(KEY)]

    assert raised.value.retry_after == 5
    assert b"".join([chunk async for chunk in storage.open_read(KEY)]) == PNG


async def test_delete_prefix_deletes_in_batches(proxied: tuple[S3Storage, FaultProxy]) -> None:
    """NO-010, NO-072: 1001 object → đúng 2 lượt `DeleteObjects` (≤ 1000 khoá/lượt), không một `DELETE` nào."""
    storage, proxy = proxied
    gate = asyncio.Semaphore(WRITE_CONCURRENCY)

    async def put_page(index: int) -> None:
        """Ghi một ảnh trang, giữ trần đồng thời."""
        async with gate:
            page = keys.upload_page(PROJECT, FLOOR, UPLOAD, index)
            await storage.put(page, PNG, content_type="image/png", max_bytes=MAX_BYTES)

    async with asyncio.TaskGroup() as group:
        for index in range(DELETE_BATCH + 1):
            group.create_task(put_page(index))
    proxy.requests.clear()

    await storage.delete_prefix(keys.project_prefix(PROJECT))

    assert [method for method, _ in proxy.requests].count("DELETE") == 0
    assert len([path for method, path in proxy.requests if method == "POST" and "delete" in path]) == 2
    assert len([method for method, path in proxy.requests if method == "POST"]) == 2
    assert [info async for info in storage.list_prefix(keys.project_prefix(PROJECT))] == []


async def test_delete_prefix_reports_objects_it_could_not_delete(proxied: tuple[S3Storage, FaultProxy]) -> None:
    """Lỗi từng object trong `DeleteResult` (200) không bị nuốt: dọn rác phải biết mình dọn sót."""
    storage, proxy = proxied
    await storage.put(KEY, PNG, content_type="image/png", max_bytes=MAX_BYTES)
    proxy.faults.append(Fault("POST", 200, delete_error_xml(KEY, "AccessDenied"), query="delete"))

    with pytest.raises(RuntimeError, match=rf"1 object .*{re.escape(KEY)}: AccessDenied"):
        await storage.delete_prefix(keys.project_prefix(PROJECT))


class _FullDiskSpool:
    """Bộ đệm mà mọi lần ghi đều gặp đĩa đầy — tiêm lỗi cho nhánh đệm xuống đĩa của `put`."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Nhận mọi tham số của `SpooledTemporaryFile` và bỏ qua."""

    def __enter__(self) -> "_FullDiskSpool":
        return self

    def __exit__(self, *args: object) -> None:
        """Không giữ tài nguyên nào."""

    def write(self, data: bytes) -> int:
        raise OSError(errno.ENOSPC, "tiêm lỗi đĩa đầy")

    def seek(self, offset: int) -> int:
        return offset


async def test_put_on_a_full_spool_disk_returns_503(s3_storage: S3Storage, monkeypatch: pytest.MonkeyPatch) -> None:
    """NO-014: đĩa đầy khi đệm luồng vào → 503 như bản local (C13), không `OSError` thô ra 500."""
    monkeypatch.setattr(tempfile, "SpooledTemporaryFile", _FullDiskSpool)

    with pytest.raises(AppError, match="DEPENDENCY_UNAVAILABLE") as raised:
        await s3_storage.put(KEY, PNG, content_type="image/png", max_bytes=MAX_BYTES)

    assert raised.value.retry_after == 5
    monkeypatch.undo()
    assert await s3_storage.stat(KEY) is None


async def test_ensure_bucket_raises_when_cors_is_refused(proxied: tuple[S3Storage, FaultProxy]) -> None:
    """NO-015: chỉ `NotImplemented` (CORS do MinIO tự đặt) được bỏ qua; S3 từ chối CORS phải nổi lên."""
    storage, proxy = proxied
    proxy.faults.append(Fault("PUT", 403, s3_error_xml("AccessDenied"), query="cors"))

    with pytest.raises(S3Error, match="AccessDenied"):
        await storage.ensure_bucket("https://appback.test")
