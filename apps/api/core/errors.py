"""Thân lỗi W7 và bộ xử lý ngoại lệ duy nhất của `apps/api` (BE-00 §4).

Mọi lỗi ra dây đúng một khuôn: `{"code", "requestId"}` cộng các khoá tuỳ chọn mà
`toAppError.ts` biết đọc. Ngoại lệ duy nhất là `VERSION_CONFLICT` (W20).

Ba luật bất biến:

- **bộ xử lý lỗi không bao giờ ném.** Dựng thân hỏng (giá trị lạ trong
  `remoteChanges`) thì trả thân tối thiểu, vì một 500 ở đây làm FE mất cả `requestId`;
- **401 chỉ dành cho token/phiên** (W10, K30) — `ERRORS.define` đã chặn ở B0-02;
- lỗi hạ tầng của Postgres/Redis/kho được dịch thành 503 `DEPENDENCY_UNAVAILABLE`
  (C13); lỗi lạ chỉ vào log kèm stack, trên dây là 500 `INTERNAL` không lộ gì.
"""

import json
import logging
from collections.abc import Iterable, Mapping
from typing import Final

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from pydantic.alias_generators import to_camel
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request
from starlette.responses import Response

from packages.core.error_codes import (
    INTERNAL,
    MALFORMED_JSON,
    NOT_FOUND,
    PAYLOAD_TOO_LARGE,
    VALIDATION,
)
from packages.core.errors import MISSING, AppError, ErrorCode, RemoteFieldChange, VersionConflictError
from packages.core.instants import to_wire
from packages.core.logging import request_id_var
from packages.db.errors import translate_db_error
from packages.messaging.redis import translate_redis_error

_log: Final = logging.getLogger(__name__)

REQUEST_ID_HEADER: Final = "X-Request-Id"
RETRY_AFTER_HEADER: Final = "Retry-After"
JSON_CONTENT_TYPE: Final = "application/json"

_LOC_ROOTS: Final = frozenset({"body", "query", "path"})
_JSON_INVALID: Final = "json_invalid"

# `HTTPException` do Starlette/FastAPI ném (không phải mã nghiệp vụ) → mã W7 tương ứng.
# 405 đi chung 404: hiến chương không cho FE thấy "method not allowed" (BE-00 §4).
_HTTP_STATUS_CODES: Final[Mapping[int, ErrorCode]] = {
    400: VALIDATION,
    404: NOT_FOUND,
    405: NOT_FOUND,
    413: PAYLOAD_TOO_LARGE,
}


def request_id() -> str:
    """`X-Request-Id` của request đang chạy; rỗng khi gọi ngoài vòng đời request."""
    return request_id_var.get() or ""


def _remote_change(change: RemoteFieldChange) -> dict[str, object]:
    """Một dòng `remoteChanges` (HOP-DONG-MOI §1.1); `MISSING` → **vắng** khoá `value`."""
    wire: dict[str, object] = {
        "entityId": change.entity_id,
        "entityType": change.entity_type,
        "field": change.field,
        "changedAt": to_wire(change.changed_at),
        "changedBy": change.changed_by,
        "changedByName": change.changed_by_name,
    }
    if change.value is not MISSING:
        wire["value"] = change.value
    return wire


def error_payload(exc: AppError, rid: str) -> dict[str, object]:
    """Thân W7 của một `AppError`, kể cả phần riêng của `VERSION_CONFLICT` (W20)."""
    body: dict[str, object] = {"code": exc.code.code, "requestId": rid, **exc.wire_params()}
    if isinstance(exc, VersionConflictError):
        body["currentVersion"] = exc.current_version
        body["remoteChanges"] = [_remote_change(change) for change in exc.remote_changes]
    return body


def error_response(exc: AppError, rid: str) -> Response:
    """Response JSON của một `AppError`; thân không dựng được → chỉ `code` + `requestId`."""
    try:
        content = json.dumps(error_payload(exc, rid), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        _log.exception("error_body_build_failed", extra={"code": exc.code.code})
        content = json.dumps({"code": exc.code.code, "requestId": rid})
    headers = {} if exc.retry_after is None else {RETRY_AFTER_HEADER: str(exc.retry_after)}
    return Response(content=content, status_code=exc.code.status, media_type=JSON_CONTENT_TYPE, headers=headers)


def simple_error(code: ErrorCode, rid: str) -> Response:
    """Response của một mã lõi không tham số — middleware ASGI dùng (413 của trần thân)."""
    return error_response(AppError(code), rid)


def field_of(loc: Iterable[object]) -> str | None:
    """`field` của một lỗi Pydantic (BE-00 §4).

    Bỏ đoạn gốc (`body`/`query`/`path`), đổi từng đoạn sang camelCase và **dừng**
    trước đoạn đầu tiên không khớp `^[A-Za-z0-9]+$` — khoá dict của người dùng
    (`overrides.WALL-THICKNESS`) hay tên validator (`function-after[...]`) không
    phải tên trường và không được lọt ra dây (`registry.ts:443`).
    """
    parts = list(loc)
    if parts and parts[0] in _LOC_ROOTS:
        parts = parts[1:]
    kept: list[str] = []
    for part in parts:
        segment = to_camel(part) if isinstance(part, str) else str(part)
        if not segment.isalnum() or not segment.isascii():
            break
        kept.append(segment)
    return ".".join(kept) or None


def validation_error(exc: RequestValidationError, rid: str) -> Response:
    """Lỗi Pydantic → 422 `VALIDATION` (`field` của lỗi đầu, `count` = số lỗi), JSON hỏng → 400."""
    errors = list(exc.errors())
    if any(error.get("type") == _JSON_INVALID for error in errors):
        return error_response(AppError(MALFORMED_JSON), rid)
    count = len(errors)
    field = field_of(errors[0].get("loc", ())) if errors else None
    if field is None:
        return error_response(AppError(VALIDATION, count=count), rid)
    try:
        return error_response(AppError(VALIDATION, count=count, field=field), rid)
    except ValueError:
        # `field` ghép ra chuỗi ngoài mẫu W7 (đoạn đầu là chỉ số mảng) → bỏ khoá `field`.
        return error_response(AppError(VALIDATION, count=count), rid)


def http_exception_error(exc: StarletteHTTPException, rid: str) -> Response:
    """`HTTPException` của Starlette/FastAPI → mã W7; status lạ → 500 `INTERNAL` có log."""
    code = _HTTP_STATUS_CODES.get(exc.status_code)
    if code is None:
        _log.warning("http_exception_unmapped", extra={"status": exc.status_code})
        return error_response(AppError(INTERNAL), rid)
    return error_response(AppError(code), rid)


def translate_unknown(exc: BaseException) -> AppError:
    """Ngoại lệ lạ → 503 khi là lỗi hạ tầng đã biết (C13), còn lại 500 `INTERNAL` có stack."""
    for translate in (translate_db_error, translate_redis_error):
        translated = translate(exc)
        if translated is not None:
            return translated
    _log.exception("unhandled_exception", exc_info=exc)
    return AppError(INTERNAL)


async def _app_error_handler(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, AppError)  # noqa: S101 — Starlette gọi đúng handler theo kiểu đã đăng ký
    return error_response(exc, request_id())


async def _validation_handler(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, RequestValidationError)  # noqa: S101 — như trên
    return validation_error(exc, request_id())


async def _http_exception_handler(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, StarletteHTTPException)  # noqa: S101 — như trên
    return http_exception_error(exc, request_id())


def install_error_handlers(app: FastAPI) -> None:
    """Gắn ba bộ xử lý lên app; ngoại lệ còn lại do `FinalErrorMiddleware` chặn."""
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_handler)
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
