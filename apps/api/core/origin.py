"""Kiểm header `Origin` (BE-00 §5, K31).

Hai luật khác nhau, đừng lẫn:

- `require_origin` cho phương thức **ghi dùng cookie** (`/api/auth/*`): thiếu hay
  lệch đều 403 `ORIGIN_MISMATCH` (C24);
- `reject_foreign_origin` cho **GET luồng**: trình duyệt không gửi `Origin` cho GET
  cùng origin, nên thiếu là bình thường; chỉ lệch mới chặn (K31, S09).

Không bật CORS cho API (W19): FE và API cùng origin sau nginx.
"""

from typing import Final
from urllib.parse import urlsplit

from starlette.requests import Request

from packages.core.error_codes import ORIGIN_MISMATCH
from packages.core.settings import CoreSettings

ORIGIN_HEADER: Final = "origin"


def _origin_of(url: str) -> tuple[str, str] | None:
    """(scheme, host:port) — đơn vị để so origin, bỏ đường dẫn; chuỗi không phân tích được → `None`.

    `Origin` là header **client** gửi: `urlsplit("http://[")` ném `ValueError`, và để lỗi đó
    lọt ra là biến một request sai dạng thành 500 `INTERNAL` thay vì 403 (SEC-05, R-17).
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    return parts.scheme, parts.netloc


def _settings(request: Request) -> CoreSettings:
    """Cấu hình của app đang chạy — nguồn của `PUBLIC_BASE_URL`."""
    settings = request.app.state.settings
    assert isinstance(settings, CoreSettings)  # noqa: S101 — `create_app` luôn đặt
    return settings


def _matches(request: Request) -> bool:
    """Có `Origin` và cùng origin với `PUBLIC_BASE_URL` không."""
    origin = request.headers.get(ORIGIN_HEADER)
    if origin is None:
        return False
    given = _origin_of(origin)
    return given is not None and given == _origin_of(_settings(request).public_base_url)


def require_origin(request: Request) -> None:
    """Thiếu hoặc lệch `Origin` → 403 `ORIGIN_MISMATCH`."""
    if not _matches(request):
        raise ORIGIN_MISMATCH.error()


def reject_foreign_origin(request: Request) -> None:
    """Chỉ chặn khi **có** `Origin` mà lệch (K31)."""
    if request.headers.get(ORIGIN_HEADER) is not None and not _matches(request):
        raise ORIGIN_MISMATCH.error()
