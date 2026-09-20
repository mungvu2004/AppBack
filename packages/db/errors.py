"""Dịch lỗi CSDL sang `AppError` (C13, BE-00 §4).

Chỉ dịch lỗi **hạ tầng** (mất kết nối, hết giờ, xung đột tuần tự hoá) sang 503
`DEPENDENCY_UNAVAILABLE`; lỗi do mã (cú pháp, ràng buộc) trả `None` để người gọi tự
xử. Thân lỗi không bao giờ mang thông điệp của Postgres (W7).
"""

import re
from typing import Final

from asyncpg.exceptions import CannotConnectNowError, ConnectionDoesNotExistError
from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError, TimeoutError as SATimeoutError

from packages.core.error_codes import DEPENDENCY_UNAVAILABLE
from packages.core.errors import AppError

RETRY_AFTER_S: Final = 5
RETRY_AFTER_SERIALIZATION_S: Final = 1

# 57014 statement_timeout · 55P03 lock_not_available · 57P0x máy chủ tắt · 08xxx kết nối · 53x hết tài nguyên
UNAVAILABLE_SQLSTATES: Final = frozenset(
    {"57014", "55P03", "57P01", "57P02", "57P03", "08000", "08001", "08003", "08004", "08006", "53300", "53400"}
)
SERIALIZATION_SQLSTATES: Final = frozenset({"40001", "40P01"})
UNIQUE_VIOLATION_SQLSTATE: Final = "23505"

_CONSTRAINT_RE: Final = re.compile(r'constraint "([^"]+)"')
_MAX_DEPTH: Final = 5


def _chain(exc: BaseException) -> list[BaseException]:
    seen: list[BaseException] = []
    node: BaseException | None = exc
    while node is not None and len(seen) < _MAX_DEPTH:
        seen.append(node)
        node = getattr(node, "orig", None) or node.__cause__
    return seen


def _sqlstate(exc: BaseException) -> str | None:
    for node in _chain(exc):
        for attr in ("sqlstate", "pgcode"):
            code = getattr(node, attr, None)
            if isinstance(code, str):
                return code
    return None


def _is_connection_error(exc: BaseException) -> bool:
    return any(
        isinstance(node, CannotConnectNowError | ConnectionDoesNotExistError | ConnectionError | OSError)
        for node in _chain(exc)
    )


def translate_db_error(exc: BaseException) -> AppError | None:
    """503 cho lỗi hạ tầng (kèm `Retry-After`), `None` cho lỗi còn lại."""
    state = _sqlstate(exc)
    if state in SERIALIZATION_SQLSTATES:
        return DEPENDENCY_UNAVAILABLE.error(retry_after=RETRY_AFTER_SERIALIZATION_S)
    if state in UNAVAILABLE_SQLSTATES:
        return DEPENDENCY_UNAVAILABLE.error(retry_after=RETRY_AFTER_S)
    if state is not None:  # lỗi có mã Postgres khác: của mã nghiệp vụ, không phải hạ tầng
        return None
    if isinstance(exc, SATimeoutError | InterfaceError | OperationalError) or _is_connection_error(exc):
        return DEPENDENCY_UNAVAILABLE.error(retry_after=RETRY_AFTER_S)
    if isinstance(exc, DBAPIError) and exc.connection_invalidated:
        return DEPENDENCY_UNAVAILABLE.error(retry_after=RETRY_AFTER_S)
    return None


def unique_violation(exc: BaseException) -> str | None:
    """Tên ràng buộc duy nhất bị vi phạm, hoặc `None`."""
    if _sqlstate(exc) != UNIQUE_VIOLATION_SQLSTATE:
        return None
    for node in _chain(exc):
        name = getattr(node, "constraint_name", None)
        if isinstance(name, str) and name:
            return name
    match = _CONSTRAINT_RE.search(str(exc))
    return match.group(1) if match else None
