"""Hai cookie của phiên: refresh và luồng (BE-00 §5 bảng cookie).

Cả hai `HttpOnly; Secure; SameSite=Strict` và có `Path` hẹp: cookie refresh chỉ đi tới
`/api/auth`, cookie luồng chỉ tới `/api/streams` — trình duyệt không gửi token refresh
kèm mọi request API. Xoá = cùng tên, cùng `Path`, `Max-Age=0`.
"""

from typing import Final

from starlette.requests import Request
from starlette.responses import Response

REFRESH_COOKIE: Final = "appback_refresh"
REFRESH_PATH: Final = "/api/auth"
STREAM_COOKIE: Final = "appback_stream"
STREAM_PATH: Final = "/api/streams"


def _set(response: Response, name: str, value: str, *, path: str, max_age: int | None) -> None:
    """Một cookie đúng bộ thuộc tính chung của hiến chương."""
    response.set_cookie(name, value, max_age=max_age, path=path, secure=True, httponly=True, samesite="strict")


def set_refresh_cookie(response: Response, value: str, *, max_age: int | None) -> None:
    """Cookie refresh; `max_age=None` (không ghi nhớ) là cookie phiên của trình duyệt."""
    _set(response, REFRESH_COOKIE, value, path=REFRESH_PATH, max_age=max_age)


def set_stream_cookie(response: Response, token: str, *, max_age: int) -> None:
    """Cookie luồng mang JWT `aud="stream"`; cấp mỗi lần đăng nhập và refresh."""
    _set(response, STREAM_COOKIE, token, path=STREAM_PATH, max_age=max_age)


def clear_auth_cookies(response: Response) -> None:
    """Lệnh xoá cả hai cookie (cùng tên, cùng `Path`, `Max-Age=0`)."""
    for name, path in ((REFRESH_COOKIE, REFRESH_PATH), (STREAM_COOKIE, STREAM_PATH)):
        response.delete_cookie(name, path=path, secure=True, httponly=True, samesite="strict")


def refresh_cookie_of(request: Request) -> str | None:
    """Giá trị cookie refresh của request, chưa kiểm mẫu."""
    return request.cookies.get(REFRESH_COOKIE)
