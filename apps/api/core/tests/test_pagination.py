"""Cursor ký HMAC và `page_params` (W22, HOP-DONG-MOI §1.2)."""

from typing import Final

import httpx
import pytest

from apps.api.core.auth import Principal
from apps.api.core.pagination import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    CursorPage,
    decode_cursor,
    encode_cursor,
    page_params,
)
from apps.api.core.tests.sample import PAGE_MAX_LIMIT, ItemOut, sample_app, sample_client
from packages.core.errors import AppError
from packages.testing.fixtures.api import auth_headers

__all__ = ["sample_app", "sample_client"]

OP: Final = "sample_list_page"
FILTERS: Final = {"projectId": "prj_1", "state": "open"}
POSITION: Final = {"after": 7}


def test_round_trip(storage_env: None) -> None:
    """Cursor giải ra đúng vị trí đã mã hoá."""
    assert decode_cursor(encode_cursor(OP, FILTERS, POSITION), OP, FILTERS) == POSITION


def test_filters_order_does_not_matter(storage_env: None) -> None:
    """Bộ lọc cùng nội dung khác thứ tự khoá vẫn là cùng bộ lọc."""
    cursor = encode_cursor(OP, {"a": 1, "b": 2}, POSITION)
    assert decode_cursor(cursor, OP, {"b": 2, "a": 1}) == POSITION


@pytest.mark.parametrize(
    "broken",
    ["khong-co-cham", "a.b", ""],
    ids=["thiếu dấu chấm", "base64 rác", "rỗng"],
)
def test_broken_cursor_is_422(storage_env: None, broken: str) -> None:
    """Cursor không giải được → 422, không lộ lý do."""
    with pytest.raises(AppError) as caught:
        decode_cursor(broken, OP, FILTERS)
    assert caught.value.code.code == "CURSOR_INVALID"


def test_tampered_byte_is_422(storage_env: None) -> None:
    """Sửa một byte của phần thân → MAC lệch → 422."""
    cursor = encode_cursor(OP, FILTERS, POSITION)
    head, mac = cursor.split(".")
    flipped = ("A" if head[0] != "A" else "B") + head[1:]
    with pytest.raises(AppError, match="CURSOR_INVALID"):
        decode_cursor(f"{flipped}.{mac}", OP, FILTERS)


def test_cursor_of_other_op_is_422(storage_env: None) -> None:
    """Cursor của thao tác khác không dùng lại được (chống rò dữ liệu bộ lọc cũ)."""
    cursor = encode_cursor(OP, FILTERS, POSITION)
    with pytest.raises(AppError, match="CURSOR_INVALID"):
        decode_cursor(cursor, "khac_op", FILTERS)


def test_cursor_of_other_filters_is_422(storage_env: None) -> None:
    """Đổi bộ lọc giữa hai trang là phải đọc lại từ đầu."""
    cursor = encode_cursor(OP, FILTERS, POSITION)
    with pytest.raises(AppError, match="CURSOR_INVALID"):
        decode_cursor(cursor, OP, {"projectId": "prj_2"})


def test_page_params_rejects_bad_max_limit() -> None:
    """Trần < 1 là khai route sai, hỏng lúc nạp module."""
    with pytest.raises(ValueError, match="max_limit"):
        page_params(0)


def test_page_params_default_never_exceeds_max() -> None:
    """Route khai trần nhỏ hơn 50 thì mặc định cũng phải nhỏ theo."""
    assert MAX_LIMIT >= DEFAULT_LIMIT
    dependency = page_params(PAGE_MAX_LIMIT)
    assert dependency.__defaults__ == (None, PAGE_MAX_LIMIT)


def test_cursor_page_drops_absent_next_cursor() -> None:
    """`nextCursor` là tuỳ chọn: hết trang thì vắng khoá (W2, W22)."""
    page: CursorPage[ItemOut] = CursorPage(items=[ItemOut(name="a")])
    assert page.model_dump(by_alias=True) == {"items": [{"name": "a"}]}


async def test_limit_over_max_is_422(sample_client: httpx.AsyncClient, fake_principal: Principal) -> None:
    """C02: gửi trần + 1 → 422 `VALIDATION` với `field="limit"`."""
    response = await sample_client.get(
        f"/api/sample/page?limit={PAGE_MAX_LIMIT + 1}", headers=auth_headers(fake_principal)
    )
    assert response.status_code == 422
    assert response.json()["field"] == "limit"


async def test_page_returns_next_cursor(sample_client: httpx.AsyncClient, fake_principal: Principal) -> None:
    """C15: danh sách mới trả `{items, nextCursor}` với `limit` nhỏ."""
    response = await sample_client.get("/api/sample/page?limit=1", headers=auth_headers(fake_principal))
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == [{"name": "item-0"}]
    assert decode_cursor(body["nextCursor"], OP, {}) == {"after": 1}
