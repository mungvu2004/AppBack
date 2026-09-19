"""Log JSON có che bí mật (BE-00 §11, K11).

- Khoá luôn che (không phân biệt hoa thường, bỏ `-`/`_`) ở mọi độ sâu của dict, list, tuple.
- Mọi chuỗi (kể cả `msg`, `stack`) che thêm JWT, phần sau `Bearer `, giá trị query
  `X-Amz-Signature`, `X-Amz-Credential`, `token`; chuỗi dài hơn 2.000 ký tự bị cắt
  (trừ `stack`, để giữ khung ném lỗi ở cuối).
- Đối số của `msg` được che **trước** khi ghép, nên `log.info("%s", body)` cũng an toàn.
- Không in biến cục bộ.
"""

import json
import logging
import re
import sys
from collections.abc import Mapping
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Final

from packages.core.instants import to_wire
from packages.core.settings import CoreSettings

MASK: Final = "***"
MAX_STR_LEN: Final = 2000

_MASKED_KEYS: Final = frozenset(
    {
        "password",
        "newpassword",
        "currentpassword",
        "token",
        "accesstoken",
        "refreshtoken",
        "authorization",
        "cookie",
        "setcookie",
        "confirmemail",
        "chunk",
        "contentbase64",
    }
)
_STR_PATTERNS: Final = (
    (re.compile(r"eyJ[\w-]*\.[\w-]*\.[\w-]*"), MASK),
    (re.compile(r"(?i)(\bBearer\s+)\S+"), rf"\g<1>{MASK}"),
    (re.compile(r"(?i)([?&](?:X-Amz-Signature|X-Amz-Credential|token)=)[^&#\s\"']*"), rf"\g<1>{MASK}"),
)
# Thuộc tính sẵn có của LogRecord; phần còn lại là `extra=` của lời gọi.
_RECORD_ATTRS: Final = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {"message", "asctime"}

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
_context_var: ContextVar[Mapping[str, object]] = ContextVar("log_context", default=MappingProxyType({}))


def bind_log_context(**fields: object) -> Token[Mapping[str, object]]:
    """Thêm trường vào mọi bản ghi của task hiện tại (task asyncio khác không thấy)."""
    return _context_var.set(MappingProxyType({**_context_var.get(), **fields}))


def _mask_str(s: str, limit: int | None = MAX_STR_LEN) -> str:
    masked = s
    for pattern, repl in _STR_PATTERNS:
        masked = pattern.sub(repl, masked)
    if limit is not None and len(masked) > limit:
        return f"{masked[:limit]}…[cắt, dài {len(s)}]"
    return masked


def _mask_items[K](items: Mapping[K, object]) -> dict[K, object]:
    return {
        k: MASK if isinstance(k, str) and k.replace("-", "").replace("_", "").casefold() in _MASKED_KEYS else mask(v)
        for k, v in items.items()
    }


def mask(obj: object) -> object:
    """Bản sao đã che; kiểu lạ đổi thành chuỗi rồi che."""
    if obj is None or isinstance(obj, bool | int | float):
        return obj
    if isinstance(obj, str):
        return _mask_str(obj)
    if isinstance(obj, Mapping):
        return _mask_items(obj)
    if isinstance(obj, list):
        return [mask(item) for item in obj]
    if isinstance(obj, tuple):
        return tuple(mask(item) for item in obj)
    return _mask_str(str(obj))


class JsonFormatter(logging.Formatter):
    def payload(self, record: logging.LogRecord) -> dict[str, object]:
        msg = record.msg if isinstance(record.msg, str) else str(mask(record.msg))
        if record.args:
            msg = msg % mask(record.args)
        extras = {k: v for k, v in record.__dict__.items() if k not in _RECORD_ATTRS}
        data = _mask_items(
            {
                **_context_var.get(),
                **extras,
                "ts": to_wire(datetime.fromtimestamp(record.created, UTC)),
                "level": record.levelname,
                "logger": record.name,
                "msg": msg,
                "requestId": request_id_var.get(),
            }
        )
        if record.exc_info and record.exc_info[0] is not None:
            data["excType"] = record.exc_info[0].__name__
            data["stack"] = _mask_str(self.formatException(record.exc_info), limit=None)
        return data

    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(self.payload(record), ensure_ascii=False)


class _TextFormatter(JsonFormatter):
    """`LOG_JSON=false` (máy dev): cùng nội dung đã che, một dòng dễ đọc."""

    def format(self, record: logging.LogRecord) -> str:
        data = self.payload(record)
        head = " ".join(str(data.pop(k)) for k in ("ts", "level", "logger", "msg"))
        stack = data.pop("stack", None)
        line = f"{head} {json.dumps(data, ensure_ascii=False)}"
        return f"{line}\n{stack}" if stack else line


def configure_logging(settings: CoreSettings) -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter() if settings.log_json else _TextFormatter())
    root = logging.getLogger()
    for old in root.handlers[:]:
        root.removeHandler(old)
    root.addHandler(handler)
    root.setLevel(settings.log_level)
