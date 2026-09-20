"""Danh sách mới: `CursorPage`, `page_params`, cursor ký HMAC (W22, HOP-DONG-MOI §1.2).

Cursor **không** phải offset: nó mang vị trí đọc tiếp cộng dấu vết của thao tác và
bộ lọc đã dùng, tất cả được ký bằng khoá con `cursor` (BE-00 §5). Nhờ vậy client
không tự chế được vị trí, và cursor của danh sách này không dùng được cho danh
sách khác — thứ sẽ trả về dữ liệu của bộ lọc cũ mà không ai biết.

Cursor sai, sửa, hết hiệu lực, hay dùng cho `op`/bộ lọc khác đều là **một** câu trả
lời: 422 `CURSOR_INVALID` (không nói lý do, để không thành máy dò).
"""

import base64
import hashlib
import hmac
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Annotated, Any, Final

from fastapi import Query

from apps.api.core.wire import WireModel
from packages.core.error_codes import CURSOR_INVALID
from packages.core.keys import current_key, verification_keys

DEFAULT_LIMIT: Final = 50
MAX_LIMIT: Final = 200
"""Trần chung của HOP-DONG-MOI §0; route nào rộng hơn (N1 = 500) tự khai `max_limit`."""


class CursorPage[ItemT](WireModel):
    """`{items, nextCursor?}` — khuôn danh sách mới duy nhất (W22)."""

    items: list[ItemT]
    next_cursor: str | None = None


@dataclass(frozen=True, slots=True)
class PageParams:
    """Tham số phân trang đã kiểm; `limit` luôn nằm trong trần khai lúc dựng route."""

    cursor: str | None
    limit: int


def page_params(max_limit: int = MAX_LIMIT) -> Callable[..., PageParams]:
    """Dependency đọc `cursor`, `limit`; trần **cố định lúc khai route** nên vào OpenAPI.

    Mặc định là 50 (W22) nhưng không bao giờ vượt trần của chính route: một route
    khai `max_limit` nhỏ hơn 50 mà vẫn mặc định 50 thì lượt gọi không truyền `limit`
    sẽ tự vi phạm ràng buộc của mình.
    """
    if max_limit < 1:
        raise ValueError(f"max_limit phải ≥ 1, nhận {max_limit}")

    def dependency(
        cursor: Annotated[str | None, Query()] = None,
        limit: Annotated[int, Query(ge=1, le=max_limit)] = min(DEFAULT_LIMIT, max_limit),
    ) -> PageParams:
        return PageParams(cursor=cursor, limit=limit)

    return dependency


def _b64(raw: bytes) -> str:
    """base64url không dấu `=` (cursor đi trong query string)."""
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    """Giải base64url, tự bù dấu `=` đã cắt."""
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _canonical(value: Mapping[str, object]) -> bytes:
    """JSON tất định (khoá đã sắp) — hai dict cùng nội dung phải ra cùng chuỗi byte."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _filters_digest(filters: Mapping[str, object]) -> str:
    """Dấu vết bộ lọc; băm chứ không nhúng, để cursor không rò giá trị lọc ra ngoài."""
    return hashlib.sha256(_canonical(filters)).hexdigest()


def encode_cursor(op: str, filters: Mapping[str, object], pos: Mapping[str, object]) -> str:
    """Cursor cho lượt đọc tiếp của `op` với đúng bộ lọc `filters`."""
    raw = _canonical({"o": op, "f": _filters_digest(filters), "p": dict(pos)})
    mac = hmac.new(current_key("cursor"), raw, hashlib.sha256).digest()
    return f"{_b64(raw)}.{_b64(mac)}"


def decode_cursor(cursor: str, op: str, filters: Mapping[str, object]) -> dict[str, Any]:
    """Vị trí đọc tiếp; mọi sai lệch → 422 `CURSOR_INVALID`."""
    try:
        head, mac = cursor.split(".")
        raw = _unb64(head)
        given = _unb64(mac)
        expected = (hmac.new(key, raw, hashlib.sha256).digest() for key in verification_keys("cursor"))
        if not any(hmac.compare_digest(given, candidate) for candidate in expected):
            raise ValueError("MAC không khớp")
        body = json.loads(raw)
        if body["o"] != op or body["f"] != _filters_digest(filters):
            raise ValueError("cursor của thao tác hoặc bộ lọc khác")
        position = body["p"]
        if not isinstance(position, dict):
            raise TypeError("vị trí trong cursor phải là object")
    except (ValueError, TypeError, KeyError, UnicodeDecodeError) as exc:
        raise CURSOR_INVALID.error() from exc
    return position
