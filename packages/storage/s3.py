"""`S3Storage` — MinIO ở dev/CI, S3 ở production (BE-00 §8).

- Client `minio` là **đồng bộ**: mọi lời gọi mạng đi qua `asyncio.to_thread`.
- Ký URL dùng client trỏ `S3_PUBLIC_ENDPOINT` với `request_date` là đầu giờ, hạn 2
  giờ (W23). Ký là phép tính cục bộ — `S3_REGION` bắt buộc nên không có lượt
  `GetBucketLocation` nào ra mạng.
- `sha256` và `kind` đi trong `x-amz-meta-*`; `put` biết cả hai **trước** khi gửi
  (luồng vào được đệm), nên không cần `CopyObject` sửa metadata sau multipart.
"""

import asyncio
import hashlib
import logging
import tempfile
from collections.abc import AsyncIterable, AsyncIterator, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from html import escape
from typing import BinaryIO, Final, cast

import urllib3
from minio import Minio
from minio.datatypes import Object
from minio.deleteobjects import DeleteObject
from minio.error import S3Error, ServerError
from minio.helpers import md5sum_hash

from packages.core.clock import Clock
from packages.core.error_codes import DEPENDENCY_UNAVAILABLE, NOT_FOUND, PAYLOAD_TOO_LARGE
from packages.storage.keys import check_key, check_prefix
from packages.storage.port import (
    CHUNK_SIZE,
    RETRY_AFTER_S,
    SIGNED_URL_TTL,
    Disposition,
    ObjectInfo,
    SignedUrl,
    content_disposition,
    content_type_of,
    disk_errors,
    expiry,
    iter_chunks,
    next_batch,
    resolve_kind,
)
from packages.storage.sniff import SNIFF_BYTES, ImageKind, as_kind, sniff

SHA256_META: Final = "x-amz-meta-sha256"
KIND_META: Final = "x-amz-meta-kind"
MULTIPART_PART_SIZE: Final = 16 * 1024 * 1024
"""Object lớn hơn ngần này được `minio` ghi bằng multipart (và tự huỷ khi lỗi giữa chừng)."""

CONNECT_TIMEOUT_S: Final = 3.0
READ_TIMEOUT_S: Final = 15.0
"""Mặc định của `minio` là 300 s — quá dài so với trần 15 s của endpoint (W11, RES-01)."""

SERVER_ERROR_STATUS: Final = 500
CORS_UNSUPPORTED: Final = "NotImplemented"
"""Mã MinIO trả cho `PutBucketCors`: CORS của MinIO đặt bằng biến môi trường, không bằng API."""
DELETE_ERRORS_SHOWN: Final = 5
"""Số object hỏng in trong thông điệp lỗi của `delete_prefix`; tổng số vẫn in đủ."""
_MISSING_CODES: Final = frozenset(("NoSuchKey", "NoSuchObject", "NotFound"))
_log: Final = logging.getLogger(__name__)


def http_client() -> urllib3.PoolManager:
    """Client HTTP có timeout tường minh; chỉ thử lại phương thức idempotent (mặc định của urllib3)."""
    return urllib3.PoolManager(
        timeout=urllib3.Timeout(connect=CONNECT_TIMEOUT_S, read=READ_TIMEOUT_S),
        retries=urllib3.Retry(total=2, backoff_factor=0.2),
        maxsize=10,
    )


@contextmanager
def _s3_errors() -> Iterator[None]:
    """Lỗi kết nối, timeout hay 5xx → 503 (C13); lỗi khác của thư viện không bị nuốt.

    `minio` chỉ dựng `ServerError` cho 5xx **không** thân; S3/MinIO quá tải trả 5xx kèm thân
    XML (`SlowDown`, `InternalError`) thành `S3Error` — cũng là phụ thuộc hỏng (NO-009).
    `S3Error` 4xx (`AccessDenied`, `NoSuchBucket`) là sự cố cấu hình, nổi lên nguyên vẹn.
    """
    try:
        yield
    except (urllib3.exceptions.HTTPError, ServerError) as exc:
        raise DEPENDENCY_UNAVAILABLE.error(retry_after=RETRY_AFTER_S) from exc
    except S3Error as exc:
        if exc.response.status >= SERVER_ERROR_STATUS:
            raise DEPENDENCY_UNAVAILABLE.error(retry_after=RETRY_AFTER_S) from exc
        raise


class S3Storage:
    def __init__(self, client: Minio, public_client: Minio, bucket: str, clock: Clock) -> None:
        self._client = client
        self._public_client = public_client
        self._bucket = bucket
        self._clock = clock

    async def ensure_bucket(self, cors_origin: str) -> None:
        """Tạo bucket nếu chưa có, rồi cho `GET`/`HEAD` từ `cors_origin`."""
        with _s3_errors():
            if not await asyncio.to_thread(self._client.bucket_exists, self._bucket):
                await asyncio.to_thread(self._client.make_bucket, self._bucket)
            try:
                await asyncio.to_thread(self._put_cors, cors_origin)
            except S3Error as exc:
                # MinIO trả `NotImplemented`: CORS đặt bằng `MINIO_API_CORS_ALLOW_ORIGIN`
                # trong compose của B0-08, không phải bằng API bucket. Mã khác (`AccessDenied`,
                # `NoSuchBucket`) là bucket production chạy với CORS sai: phải nổi lên (NO-015).
                if exc.code != CORS_UNSUPPORTED:
                    raise
                _log.info("cors_managed_by_server", extra={"bucket": self._bucket, "code": exc.code})

    async def put(
        self,
        key: str,
        data: bytes | AsyncIterable[bytes],
        *,
        content_type: str,
        max_bytes: int,
    ) -> ObjectInfo:
        """Đệm luồng vào để biết độ dài, `sha256`, `kind` trước khi gửi một lượt duy nhất."""
        check_key(key)
        digest = hashlib.sha256()
        size = 0
        head = b""
        # Đệm để biết `sha256`, `kind` và độ dài trước khi gửi: vượt `max_bytes` là
        # không có lượt ghi nào, nên không bao giờ còn object dở trên bucket (C12).
        with tempfile.SpooledTemporaryFile(max_size=MULTIPART_PART_SIZE) as buffer:
            # Quá `MULTIPART_PART_SIZE` bộ đệm tràn xuống đĩa: đĩa đầy là 503 như kho local (NO-014).
            with disk_errors():
                async for chunk in iter_chunks(data):
                    size += len(chunk)
                    if size > max_bytes:
                        raise PAYLOAD_TOO_LARGE.error()
                    digest.update(chunk)
                    head += chunk[: SNIFF_BYTES - len(head)]
                    await asyncio.to_thread(buffer.write, chunk)
            buffer.seek(0)
            kind = sniff(head)
            with _s3_errors():
                await asyncio.to_thread(
                    self._client.put_object,
                    self._bucket,
                    key,
                    # minio khai `BinaryIO` nhưng chỉ gọi `.read(n)`; SpooledTemporaryFile đủ.
                    cast("BinaryIO", buffer),
                    length=size,
                    content_type=content_type,
                    metadata={SHA256_META: digest.hexdigest(), KIND_META: kind},
                    part_size=MULTIPART_PART_SIZE,
                )
        return ObjectInfo(
            key=key,
            size=size,
            sha256=digest.hexdigest(),
            content_type=content_type,
            kind=kind,
            last_modified=self._clock.now(),
        )

    async def stat(self, key: str) -> ObjectInfo | None:
        """`HEAD` object; `NoSuchKey` → `None`, lỗi khác giữ nguyên để không giấu sự cố.

        `HEAD` không có thân nên bucket vắng cũng hiện ra là `NoSuchKey`: chỉ
        `ensure_bucket` mới phát hiện được cấu hình sai bucket.
        """
        check_key(key)
        try:
            with _s3_errors():
                obj = await asyncio.to_thread(self._client.stat_object, self._bucket, key)
        except S3Error as exc:
            if exc.code in _MISSING_CODES:
                return None
            raise
        return _info(key, obj)

    async def open_read(self, key: str, *, chunk_size: int = CHUNK_SIZE) -> AsyncIterator[bytes]:
        """Đọc theo khúc và luôn trả kết nối về pool."""
        check_key(key)
        try:
            with _s3_errors():
                response = await asyncio.to_thread(self._client.get_object, self._bucket, key)
        except S3Error as exc:
            if exc.code in _MISSING_CODES:
                raise NOT_FOUND.error() from exc
            raise
        try:
            while chunk := await asyncio.to_thread(response.read, chunk_size):
                yield chunk
        finally:
            await asyncio.to_thread(_close, response)

    async def delete(self, key: str) -> None:
        """Xoá object; S3 coi xoá khoá không có là thành công."""
        check_key(key)
        with _s3_errors():
            await asyncio.to_thread(self._client.remove_object, self._bucket, key)

    async def delete_prefix(self, prefix: str) -> None:
        """Xoá mọi object dưới tiền tố theo lô (chỉ lịch dọn rác gọi)."""
        check_prefix(prefix)
        with _s3_errors():
            await asyncio.to_thread(self._delete_under, prefix)

    async def list_prefix(self, prefix: str, *, older_than: datetime | None = None) -> AsyncIterator[ObjectInfo]:
        """Duyệt object dưới tiền tố, lọc theo `older_than` nếu có."""
        check_prefix(prefix)
        # Bộ duyệt của `minio` lười: mỗi lô chỉ kéo trang `ListObjectsV2` cần tới (NO-013).
        listed = self._client.list_objects(self._bucket, prefix=prefix, recursive=True)
        while True:
            with _s3_errors():
                batch = await next_batch(listed)
            if not batch:
                return
            for obj in batch:
                # `ListObjectsV2` của S3 không trả `x-amz-meta-*`, nên metadata phải lấy
                # bằng `stat` từng object. Chỉ lịch dọn rác gọi hàm này (BE-00 §7).
                info = await self.stat(str(obj.object_name))
                if info is not None and (older_than is None or info.last_modified < older_than):
                    yield info

    async def signed_url(
        self,
        key: str,
        *,
        disposition: Disposition,
        filename: str | None = None,
        kind: ImageKind | None = None,
    ) -> SignedUrl:
        """URL ký sẵn trỏ `S3_PUBLIC_ENDPOINT`, cố định `disposition` và `content-type` lúc ký."""
        check_key(key)
        resolved = await resolve_kind(self, key, disposition, kind)
        signed_at, expires_at = expiry(self._clock)
        url = self._public_client.presigned_get_object(
            self._bucket,
            key,
            expires=SIGNED_URL_TTL,
            response_headers={
                "response-content-disposition": content_disposition(disposition, filename),
                "response-content-type": content_type_of(resolved),
            },
            request_date=signed_at,
        )
        return SignedUrl(url=url, expires_at=expires_at)

    def _put_cors(self, cors_origin: str) -> None:
        """Gửi `PutBucketCors` chỉ cho `GET`/`HEAD` từ origin của app."""
        rule = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<CORSConfiguration xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
            f"<CORSRule><AllowedOrigin>{escape(cors_origin)}</AllowedOrigin>"
            "<AllowedMethod>GET</AllowedMethod><AllowedMethod>HEAD</AllowedMethod>"
            "<MaxAgeSeconds>3600</MaxAgeSeconds></CORSRule></CORSConfiguration>"
        ).encode()
        # minio 7.2.20 chưa có API CORS công khai; `_execute` là đường đi của
        # `set_bucket_policy` cùng thư viện.
        self._client._execute(
            "PUT",
            self._bucket,
            body=rule,
            headers={"Content-MD5": str(md5sum_hash(rule))},
            query_params={"cors": ""},
        )

    def _delete_under(self, prefix: str) -> None:
        """Xoá mọi object dưới tiền tố bằng `DeleteObjects` (đồng bộ, NO-010).

        `remove_objects` gom tối đa 1000 khoá mỗi lượt và kéo danh sách lười, nên 10k object là
        10 lượt đi-về, không 10k. Lỗi từng object nằm trong thân 200 của `DeleteResult`: gom lại
        và ném, để lịch dọn rác biết mình còn sót (không nuốt, R-16).
        """
        listed = self._client.list_objects(self._bucket, prefix=prefix, recursive=True)
        names = (DeleteObject(str(obj.object_name)) for obj in listed)
        errors = list(self._client.remove_objects(self._bucket, names))
        if errors:
            shown = ", ".join(f"{error.name}: {error.code}" for error in errors[:DELETE_ERRORS_SHOWN])
            raise RuntimeError(f"không xoá được {len(errors)} object dưới {prefix}: {shown}")


def _close(response: urllib3.BaseHTTPResponse) -> None:
    """Đóng response và trả kết nối về pool."""
    response.close()
    response.release_conn()


def _info(key: str, obj: Object) -> ObjectInfo:
    """Đổi `Object` của minio sang `ObjectInfo`, đọc `sha256`/`kind` từ `x-amz-meta-*`."""
    metadata = {name.lower(): value for name, value in (obj.metadata or {}).items()}
    return ObjectInfo(
        key=key,
        size=obj.size or 0,
        sha256=metadata.get(SHA256_META, ""),
        content_type=obj.content_type or "",
        kind=as_kind(metadata.get(KIND_META, "")),
        last_modified=obj.last_modified or datetime.fromtimestamp(0, UTC),
    )
