"""Cổng `ObjectStorage` và luật dùng chung cho cả hai bộ điều hợp (BE-00 §8, W23).

Gói này **không** kiểm quyền người dùng: người gọi phải kiểm quyền dự án trước khi
dựng khoá hay ký URL.
"""

import unicodedata
from collections.abc import AsyncIterable, AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final, Literal, Protocol
from urllib.parse import quote

from packages.core.clock import Clock
from packages.core.error_codes import NOT_FOUND
from packages.core.instants import floor_to_hour
from packages.storage.keys import avatar_kind
from packages.storage.sniff import IMAGE_KINDS, ImageKind, Kind

CHUNK_SIZE: Final = 1024 * 1024
RETRY_AFTER_S: Final = 5
"""`Retry-After` của `DEPENDENCY_UNAVAILABLE` khi kho hỏng (C13)."""

SIGNED_URL_TTL: Final = timedelta(hours=2)
"""Ký từ đầu giờ nên URL sống 60-120 phút và **giống hệt nhau** trong cùng một giờ (W23, K16)."""

MAX_FILENAME_LEN: Final = 100
FALLBACK_FILENAME: Final = "file"
DEFAULT_CONTENT_TYPE: Final = "application/octet-stream"
_KIND_CONTENT_TYPE: Final[dict[str, str]] = {"png": "image/png", "jpeg": "image/jpeg"}
_SAFE_FILENAME_CHARS: Final = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ._-()")

Disposition = Literal["attachment", "inline"]


@dataclass(frozen=True, slots=True)
class ObjectInfo:
    key: str
    size: int
    sha256: str
    content_type: str
    """Chuỗi người gọi khai lúc `put` — chỉ để lưu; loại thật nằm ở `kind`."""
    kind: Kind
    """Suy từ magic bytes lúc `put` (K14)."""
    last_modified: datetime


@dataclass(frozen=True, slots=True)
class SignedUrl:
    url: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class FileGrant:
    """Kết quả mở token của `LocalDiskStorage`; `GET /api/files/{token}` (B0-06) dùng."""

    key: str
    disposition: Disposition
    filename: str | None


class ObjectStorage(Protocol):
    """`last_modified` do `put` trả lấy từ `clock`; của `stat`/`list_prefix` lấy từ kho."""

    async def put(
        self,
        key: str,
        data: bytes | AsyncIterable[bytes],
        *,
        content_type: str,
        max_bytes: int,
    ) -> ObjectInfo:
        """Vượt `max_bytes` → 413 `PAYLOAD_TOO_LARGE`, không để lại object dở (C12)."""
        ...

    async def stat(self, key: str) -> ObjectInfo | None:
        """Metadata của object, hoặc `None` nếu không có."""
        ...

    def open_read(self, key: str, *, chunk_size: int = CHUNK_SIZE) -> AsyncIterator[bytes]:
        """Khoá không có → 404 `NOT_FOUND` ở lượt đọc đầu tiên."""
        ...

    async def delete(self, key: str) -> None:
        """Không có thì im lặng."""
        ...

    async def delete_prefix(self, prefix: str) -> None:
        """Xoá mọi object dưới tiền tố (dọn rác của module chủ)."""
        ...

    def list_prefix(self, prefix: str, *, older_than: datetime | None = None) -> AsyncIterator[ObjectInfo]:
        """Duyệt object dưới tiền tố, lọc theo `older_than` nếu có."""
        ...

    async def signed_url(
        self,
        key: str,
        *,
        disposition: Disposition,
        filename: str | None = None,
        kind: ImageKind | None = None,
    ) -> SignedUrl:
        """URL tuyệt đối, ổn định trong một giờ, sống 60-120 phút (W23)."""
        ...


async def iter_chunks(data: bytes | AsyncIterable[bytes]) -> AsyncIterator[bytes]:
    """Đưa `bytes` và `AsyncIterable[bytes]` về cùng một luồng khúc để `put` chỉ có một đường đi."""
    if isinstance(data, bytes):
        yield data
    else:
        async for chunk in data:
            yield chunk


def expiry(clock: Clock) -> tuple[datetime, datetime]:
    """(mốc ký, hạn) — làm tròn xuống đầu giờ để URL ổn định giữa các lần đọc (W23)."""
    signed_at = floor_to_hour(clock.now())
    return signed_at, signed_at + SIGNED_URL_TTL


async def resolve_kind(
    storage: ObjectStorage,
    key: str,
    disposition: Disposition,
    kind: ImageKind | None,
) -> Kind | None:
    """Luật K15 cho `signed_url`; trả `kind` dùng cho `response-content-type`.

    `kind` truyền sẵn tránh một lượt `stat`, nhưng chỉ hợp lệ cho khoá có đuôi **do
    server chọn sau khi đã kiểm magic bytes** (hiện chỉ ảnh đại diện). Khoá khác —
    kể cả `original.<đuôi>` của lượt tải lên — phải để gói tự đọc metadata.
    """
    if kind is not None:
        if avatar_kind(key) != kind:
            raise ValueError(f"kind={kind!r} chỉ hợp lệ cho khoá ảnh đại diện đúng đuôi: {key!r}")
        return kind
    if disposition == "inline":
        info = await storage.stat(key)
        if info is None:
            raise NOT_FOUND.error()
        if info.kind not in IMAGE_KINDS:
            raise ValueError(f"inline chỉ dành cho PNG/JPEG đã kiểm magic bytes, không cho {info.kind}")
        return info.kind
    return None


def content_type_of(kind: Kind | None) -> str:
    """`Content-Type` cố định theo `kind`; không biết loại thì buộc tải về."""
    return _KIND_CONTENT_TYPE.get(kind or "", DEFAULT_CONTENT_TYPE)


def safe_filename(filename: str) -> str:
    """Lọc về ASCII an toàn cho `Content-Disposition` (giá trị UTF-8 đi ở `filename*`)."""
    folded = unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode("ascii")
    cleaned = "".join(char for char in folded if char in _SAFE_FILENAME_CHARS).strip(" .")
    return cleaned[:MAX_FILENAME_LEN] or FALLBACK_FILENAME


def content_disposition(disposition: Disposition, filename: str | None) -> str:
    """Header `Content-Disposition` theo RFC 6266: phần ASCII an toàn cộng `filename*` UTF-8."""
    if filename is None:
        return disposition
    return f"{disposition}; filename=\"{safe_filename(filename)}\"; filename*=UTF-8''{quote(filename, safe='')}"
