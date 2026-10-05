"""Log JSON có che bí mật (BE-00 §11, K11).

- Khoá luôn che (không phân biệt hoa thường, bỏ `-`/`_`, kể cả hậu tố `…password`/`…secret(key)`/`…token`)
  ở mọi độ sâu của dict, list, tuple.
- Mọi chuỗi (kể cả `msg`, `stack`) che thêm JWT, phần sau `Bearer `, giá trị query
  `X-Amz-Signature`, `X-Amz-Credential`, `token`, giá trị `KEY=…`/`KEY: …` của khoá nhạy cảm;
  chuỗi dài hơn 2.000 ký tự bị cắt
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
# Khoá kết thúc bằng các hậu tố này cũng che (`S3_SECRET_KEY`, `SMTP_PASSWORD`, `claim_token`…);
# `tokenCount`, `passwordPolicy` không kết thúc bằng hậu tố nên giữ nguyên.
_MASKED_SUFFIXES: Final = ("password", "secret", "secretkey", "token")
# `KEY=giá trị` / `KEY: giá trị` trong chuỗi tự do (env in ra, `str(exc)` của pydantic, query); khoá có
# thể nằm trong nháy (JSON/repr). Chỉ khớp phần khoá + dấu nối, không nuốt giá trị, để khoá nhạy cảm
# lồng trong giá trị của khoá thường (`input_value='SECRET_KEY=…'`) vẫn được thấy.
_KEY_SEP_RE: Final = re.compile(r"""\b(?P<key>[A-Za-z][\w.-]*)["']?\s*[=:]\s*""")
# Giá trị: chuỗi trong nháy, hoặc tới khoảng trắng/dấu phân cách (`#` để giữ fragment của URL).
_VALUE_RE: Final = re.compile(r""""[^"]*"|'[^']*'|[^\s,;&#"'}\]]+""")


def _is_masked_key(key: str) -> bool:
    """Khoá nhạy cảm: trong `_MASKED_KEYS` hoặc có hậu tố `_MASKED_SUFFIXES` (bỏ `-`/`_`, không kể hoa thường)."""
    norm = key.replace("-", "").replace("_", "").casefold()
    return norm in _MASKED_KEYS or norm.endswith(_MASKED_SUFFIXES)


def _mask_key_values(s: str) -> str:
    """Che giá trị sau `KEY=`/`KEY:` của khoá nhạy cảm; giữ nháy bao quanh giá trị.

    Bỏ qua giá trị mà ngay sau nó là `MASK` (vd `Authorization: Bearer ***` — mẫu `Bearer` đã che phần bí mật).
    """
    out: list[str] = []
    pos = 0
    for m in _KEY_SEP_RE.finditer(s):
        if m.start() < pos or not _is_masked_key(m["key"]):
            continue
        value = _VALUE_RE.match(s, m.end())
        if value is None or s[value.end() :].lstrip().startswith(MASK):
            continue
        text = value[0]
        out += [s[pos : m.end()], f"{text[0]}{MASK}{text[0]}" if text[0] in "\"'" else MASK]
        pos = value.end()
    out.append(s[pos:])
    return "".join(out)


_STR_PATTERNS: Final = (
    (re.compile(r"eyJ[\w-]*\.[\w-]*\.[\w-]*"), MASK),
    (re.compile(r"(?i)(\bBearer\s+)\S+"), rf"\g<1>{MASK}"),
    (re.compile(r"(?i)([?&](?:X-Amz-Signature|X-Amz-Credential|token)=)[^&#\s\"']*"), rf"\g<1>{MASK}"),
    # `scheme://user:mật-khẩu@host`: tham lam tới `/`, `?`, `#`: mật khẩu chứa `@` che hết, không lan sang host/query (SEC-042).
    (re.compile(r"(?i)(\b[a-z][a-z0-9+.-]*://[^\s:/@]*:)[^\s/?#]+@"), rf"\g<1>{MASK}@"),
)
# Thuộc tính sẵn có của LogRecord; phần còn lại là `extra=` của lời gọi.
_RECORD_ATTRS: Final = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {"message", "asctime"}

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
_context_var: ContextVar[Mapping[str, object]] = ContextVar("log_context", default=MappingProxyType({}))


def bind_log_context(**fields: object) -> Token[Mapping[str, object]]:
    """Thêm trường vào mọi bản ghi của task hiện tại (task asyncio khác không thấy)."""
    return _context_var.set(MappingProxyType({**_context_var.get(), **fields}))


def _mask_str(s: str, limit: int | None = MAX_STR_LEN) -> str:
    """Che mẫu bí mật trong chuỗi tự do (JWT, Bearer, query token, mật khẩu URL, `KEY=giá trị`), cắt theo `limit`."""
    masked = s
    for pattern, repl in _STR_PATTERNS:
        masked = pattern.sub(repl, masked)
    masked = _mask_key_values(masked)
    if limit is not None and len(masked) > limit:
        return f"{masked[:limit]}…[cắt, dài {len(s)}]"
    return masked


def _mask_items[K](items: Mapping[K, object]) -> dict[K, object]:
    """Che đệ quy một mapping: giá trị của khoá nhạy cảm thành `MASK`, giá trị khác đi qua `mask`."""
    return {k: MASK if isinstance(k, str) and _is_masked_key(k) else mask(v) for k, v in items.items()}


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
    """Định dạng `LogRecord` thành một dòng JSON đã che bí mật (BE-00 §5)."""

    def payload(self, record: logging.LogRecord) -> dict[str, object]:
        """Dựng dict bản ghi: trường cố định, ngữ cảnh gắn bằng `bind_log_context` và `extra=` của lời gọi, đã che."""
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
        """Trả bản ghi dưới dạng chuỗi đã che bí mật."""
        return json.dumps(self.payload(record), ensure_ascii=False)


class _TextFormatter(JsonFormatter):
    """`LOG_JSON=false` (máy dev): cùng nội dung đã che, một dòng dễ đọc."""

    def format(self, record: logging.LogRecord) -> str:
        """Trả bản ghi dưới dạng chuỗi đã che bí mật."""
        data = self.payload(record)
        head = " ".join(str(data.pop(k)) for k in ("ts", "level", "logger", "msg"))
        stack = data.pop("stack", None)
        line = f"{head} {json.dumps(data, ensure_ascii=False)}"
        return f"{line}\n{stack}" if stack else line


def configure_logging(settings: CoreSettings) -> None:
    """Gắn `JsonFormatter` (hoặc dạng dòng khi `LOG_JSON=false`) vào root logger theo `settings`."""
    install_log_handler(json_lines=settings.log_json, level=settings.log_level)


def install_log_handler(*, json_lines: bool = True, level: str = "INFO") -> None:
    """Thay mọi handler của root logger bằng một handler stderr đã che bí mật.

    Dùng trực tiếp ở tiến trình không có `CoreSettings` (con huấn luyện `ml` không cầm `SECRET_KEY`).
    """
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter() if json_lines else _TextFormatter())
    root = logging.getLogger()
    for old in root.handlers[:]:
        root.removeHandler(old)
    root.addHandler(handler)
    root.setLevel(level)
