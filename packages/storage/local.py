"""`LocalDiskStorage` — kho cho máy dev (BE-00 §8).

- Object nằm ở `<root>/<key>`, metadata ở `<root>/<key>.meta.json`; ghi vào file tạm
  cùng thư mục rồi `os.replace` (nguyên tử, không bao giờ để lại object dở).
- URL ký là `GET /api/files/{token}` (B0-06 phục vụ), **không** bao giờ trỏ thẳng
  đường dẫn tệp (K15). Token mang MAC HMAC-SHA256 khoá `file`, so bằng
  `hmac.compare_digest`; token không vào log (BE-00 §8).
- Mọi thao tác đĩa chạy qua `asyncio.to_thread`: không chặn vòng sự kiện.
- **Giới hạn đã biết:** object và file metadata là hai lần `os.replace`, nên giữa
  hai lần đó (hoặc khi hai lượt ghi cùng khoá đan nhau) `stat` có thể trả `sha256`
  của bản trước. Nội dung object luôn nguyên vẹn một bản. Kho thật của staging và
  production là S3/MinIO — nơi `put_object` gắn metadata trong cùng một lượt ghi —
  nên chỗ này chỉ ảnh hưởng máy dev; sửa triệt để thì phải ghi metadata vào chính
  object (đổi khuôn lưu trữ), không đáng cho một bộ điều hợp dev.
"""

import asyncio
import base64
import errno
import hashlib
import hmac
import json
import os
import secrets
import shutil
from collections.abc import AsyncIterable, AsyncIterator, Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO, Final, cast

from packages.core.clock import Clock
from packages.core.error_codes import DEPENDENCY_UNAVAILABLE, NOT_FOUND, PAYLOAD_TOO_LARGE
from packages.core.keys import current_key, verification_keys
from packages.storage.keys import META_SUFFIX, check_key, check_prefix
from packages.storage.port import (
    CHUNK_SIZE,
    RETRY_AFTER_S,
    Disposition,
    FileGrant,
    ObjectInfo,
    SignedUrl,
    expiry,
    iter_chunks,
    resolve_kind,
    safe_filename,
)
from packages.storage.sniff import SNIFF_BYTES, ImageKind, as_kind, sniff

FILES_ROUTE: Final = "/api/files/"
_DISPOSITIONS: Final = frozenset(("attachment", "inline"))
# Đĩa đầy hoặc chỉ đọc là "phụ thuộc hỏng" (C13), không phải lỗi của người gọi.
_UNAVAILABLE_ERRNOS: Final = frozenset((errno.ENOSPC, errno.EROFS, errno.EDQUOT))


def _open_write(path: Path) -> BinaryIO:
    """Mở file để ghi — điểm tiêm lỗi đĩa duy nhất của bộ điều hợp này."""
    return path.open("wb")


@contextmanager
def _disk_errors() -> Iterator[None]:
    """Đĩa đầy hay chỉ đọc → 503 (C13); lỗi hệ thống tệp khác giữ nguyên."""
    try:
        yield
    except OSError as exc:
        if exc.errno in _UNAVAILABLE_ERRNOS:
            raise DEPENDENCY_UNAVAILABLE.error(retry_after=RETRY_AFTER_S) from exc
        raise


class LocalDiskStorage:
    def __init__(
        self,
        root: Path,
        clock: Clock,
        public_base_url: str,
        *,
        _open: Callable[[Path], BinaryIO] = _open_write,
    ) -> None:
        """`_open` chỉ để test tiêm lỗi ghi (`OSError(ENOSPC)`); mã nghiệp vụ không truyền."""
        self._root = root
        self._clock = clock
        self._public_base_url = public_base_url
        self._open = _open

    async def put(
        self,
        key: str,
        data: bytes | AsyncIterable[bytes],
        *,
        content_type: str,
        max_bytes: int,
    ) -> ObjectInfo:
        """Ghi qua file tạm rồi `os.replace`: người đọc chỉ thấy object hoàn chỉnh hoặc không thấy gì."""
        check_key(key)
        path = self._path(key)
        temporary = path.parent / f".tmp-{secrets.token_hex(8)}"
        digest = hashlib.sha256()
        size = 0
        head = b""
        try:
            with _disk_errors():
                await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
                handle = await asyncio.to_thread(self._open, temporary)
                try:
                    async for chunk in iter_chunks(data):
                        size += len(chunk)
                        if size > max_bytes:
                            raise PAYLOAD_TOO_LARGE.error()
                        digest.update(chunk)
                        head += chunk[: SNIFF_BYTES - len(head)]
                        await asyncio.to_thread(handle.write, chunk)
                finally:
                    await asyncio.to_thread(handle.close)
                info = ObjectInfo(
                    key=key,
                    size=size,
                    sha256=digest.hexdigest(),
                    content_type=content_type,
                    kind=sniff(head),
                    last_modified=self._clock.now(),
                )
                await asyncio.to_thread(self._commit, temporary, path, info)
        finally:
            await asyncio.to_thread(_remove, temporary)
            await asyncio.to_thread(_remove, _meta_path(temporary))
        return info

    async def stat(self, key: str) -> ObjectInfo | None:
        """Đọc `<key>.meta.json` cộng `st_mtime`; thiếu một trong hai → `None`."""
        check_key(key)
        return await asyncio.to_thread(self._stat, key)

    async def open_read(self, key: str, *, chunk_size: int = CHUNK_SIZE) -> AsyncIterator[bytes]:
        """Đọc theo khúc; khoá không có → 404 ngay khúc đầu."""
        check_key(key)
        try:
            handle = await asyncio.to_thread(self._path(key).open, "rb")
        except FileNotFoundError as exc:
            raise NOT_FOUND.error() from exc
        try:
            while chunk := await asyncio.to_thread(handle.read, chunk_size):
                yield chunk
        finally:
            await asyncio.to_thread(handle.close)

    async def delete(self, key: str) -> None:
        """Xoá object và file metadata kèm theo; không có thì im lặng."""
        check_key(key)
        path = self._path(key)
        with _disk_errors():
            await asyncio.to_thread(_remove, path)
            await asyncio.to_thread(_remove, _meta_path(path))

    async def delete_prefix(self, prefix: str) -> None:
        """Xoá cả cây thư mục của tiền tố; mục đã không còn thì bỏ qua, lỗi khác nổi lên (NO-012)."""
        check_prefix(prefix)
        with _disk_errors():
            await asyncio.to_thread(shutil.rmtree, self._root / prefix, onexc=_ignore_missing)

    async def list_prefix(self, prefix: str, *, older_than: datetime | None = None) -> AsyncIterator[ObjectInfo]:
        """Duyệt object dưới tiền tố theo thứ tự khoá, bỏ file metadata."""
        check_prefix(prefix)
        for key in await asyncio.to_thread(self._keys_under, prefix):
            info = await asyncio.to_thread(self._stat, key)
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
        """Dựng token `{k,e,d,n}` + MAC cho `GET /api/files/{token}` (BE-00 §8)."""
        check_key(key)
        await resolve_kind(self, key, disposition, kind)
        _, expires_at = expiry(self._clock)
        name = safe_filename(filename) if filename is not None else ""
        body: dict[str, object] = {"k": key, "e": int(expires_at.timestamp()), "d": disposition, "n": name}
        raw = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
        mac = hmac.new(current_key("file"), _message(body), hashlib.sha256).digest()
        token = f"{_b64(raw)}.{_b64(mac)}"
        return SignedUrl(url=f"{self._public_base_url}{FILES_ROUTE}{token}", expires_at=expires_at)

    def verify_token(self, token: str) -> FileGrant:
        """Token hỏng, giả mạo hay hết hạn → 404 `NOT_FOUND` (không lộ lý do)."""
        try:
            raw, mac = token.split(".")
            body = json.loads(_unb64(raw))
            key = check_key(_text(body["k"]))
            expires_at = body["e"]
            disposition = _text(body["d"])
            name = _text(body["n"])
            if not isinstance(expires_at, int) or isinstance(expires_at, bool) or disposition not in _DISPOSITIONS:
                raise ValueError("thân token sai kiểu")
            given = _unb64(mac)
            expected = (hmac.new(key_, _message(body), hashlib.sha256).digest() for key_ in verification_keys("file"))
            if not any(hmac.compare_digest(given, candidate) for candidate in expected):
                raise ValueError("MAC không khớp")
            if expires_at <= self._clock.now().timestamp():
                raise ValueError("token hết hạn")
        except (ValueError, TypeError, KeyError, UnicodeDecodeError) as exc:
            raise NOT_FOUND.error() from exc
        return FileGrant(key=key, disposition=cast("Disposition", disposition), filename=name or None)

    def _path(self, key: str) -> Path:
        """Đường dẫn thật của khoá (khoá đã qua `check_key` nên không ra ngoài `root`)."""
        return self._root / key

    def _commit(self, temporary: Path, path: Path, info: ObjectInfo) -> None:
        """Ghi metadata rồi đổi tên nguyên tử cả hai file."""
        meta = _meta_path(temporary)
        with self._open(meta) as handle:
            handle.write(
                json.dumps(
                    {"content_type": info.content_type, "sha256": info.sha256, "size": info.size, "kind": info.kind}
                ).encode("utf-8")
            )
        os.replace(temporary, path)
        os.replace(meta, _meta_path(path))

    def _stat(self, key: str) -> ObjectInfo | None:
        """Phần đồng bộ của `stat`, chạy trong luồng riêng."""
        path = self._path(key)
        try:
            stat = path.stat()
            meta = json.loads(_meta_path(path).read_bytes())
        except FileNotFoundError:
            return None
        return ObjectInfo(
            key=key,
            size=stat.st_size,
            sha256=str(meta["sha256"]),
            content_type=str(meta["content_type"]),
            kind=as_kind(str(meta["kind"])),
            last_modified=datetime.fromtimestamp(stat.st_mtime, UTC),
        )

    def _keys_under(self, prefix: str) -> list[str]:
        """Khoá của mọi object dưới tiền tố, đã sắp, không gồm file metadata."""
        base = self._root / prefix
        paths = (path for path in base.rglob("*") if path.is_file() and not path.name.endswith(META_SUFFIX))
        return sorted(path.relative_to(self._root).as_posix() for path in paths)


def _meta_path(path: Path) -> Path:
    """Đường dẫn file metadata đi kèm một object."""
    return path.with_name(path.name + META_SUFFIX)


def _remove(path: Path) -> None:
    """Xoá file nếu còn; không có thì thôi."""
    path.unlink(missing_ok=True)


def _ignore_missing(function: Callable[..., object], path: str, error: BaseException) -> None:
    """`onexc` của `rmtree`: tiền tố hay mục con đã không còn (xoá đồng thời) là xong; lỗi khác ném lại."""
    if not isinstance(error, FileNotFoundError):
        raise error


def _message(body: dict[str, object]) -> bytes:
    """Bản tin ký: `object_key | exp | disposition | filename` (BE-00 §8).

    Không giá trị nào chứa `|`: khoá qua `check_key`, tên tệp qua `safe_filename`.
    """
    return "|".join(str(body[field]) for field in ("k", "e", "d", "n")).encode("utf-8")


def _text(value: object) -> str:
    """Ép trường token về `str`; kiểu khác là token giả mạo."""
    if not isinstance(value, str):
        raise TypeError("trường token phải là chuỗi")
    return value


def _b64(raw: bytes) -> str:
    """base64url không dấu `=` (token đi trong đường dẫn URL)."""
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    """Giải base64url, tự bù dấu `=` đã cắt."""
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
