"""Lõi #37 — hàm thuần, **không** nhận `Request` (B7-01 [6]).

Handler của `router.py` chỉ đọc `await request.body()` rồi gọi `ingest()`. Không log
thân thô, IP, `User-Agent` (K11); không ghi DB hay gửi task nào — mỗi sự kiện chỉ
thành một mẫu metric và góp vào đúng **một** dòng log mỗi lô (K22).

Mọi kiểm tra kiểu ở đây theo đúng thứ tự "hẹp trước, tốn trước" (SEC-05, R-19):
`isinstance` hẹp kiểu **trước** khi so sánh (`in`, `<=`) hay gọi hàm toán học — dữ liệu
tới từ route công khai, không xác thực, nên một giá trị lạ kiểu (`list`, `dict`, số
nguyên hàng trăm chữ số) ném ra ngoài `except _EnvelopeError`/`try` cụ thể sẽ thành 500
`INTERNAL` thay vì 422/bỏ trường như hợp đồng đòi.
"""

import json
import logging
import math
import re
from dataclasses import dataclass
from typing import Final, TypeGuard

from apps.api.telemetry.metrics import (
    TELEMETRY_BATCHES_TOTAL,
    TELEMETRY_CLIENT_DROPPED_TOTAL,
    TELEMETRY_DURATION_MS,
    TELEMETRY_EVENTS_DROPPED_TOTAL,
    TELEMETRY_EVENTS_TOTAL,
    TELEMETRY_LOG_SUPPRESSED_TOTAL,
)
from apps.api.telemetry.settings import get_telemetry_settings
from packages.core.clock import Clock, SystemClock
from packages.core.error_codes import MALFORMED_JSON, VALIDATION
from packages.observability.settings import require_test_env

_log: Final = logging.getLogger(__name__)

EVENT_NAMES: Final = frozenset(
    {
        "drawing.upload",
        "ai.started",
        "ai.finished",
        "wall.edit",
        "rules.run",
        "export.file",
        "screen.error",
        "app.first-frame",
        "scene.build",
        "scene.frame-rate",
        "project.open",
        "user.role-change",
    }
)
"""Gương `src/lib/telemetry/events.ts:464-477` (12 tên)."""

ERROR_KINDS: Final = frozenset(
    {
        "network",
        "timeout",
        "unauthenticated",
        "forbidden",
        "notFound",
        "conflict",
        "validation",
        "rateLimited",
        "upload",
        "processing",
        "geometry",
        "export",
        "unknown",
    }
)
"""Gương `src/lib/errors/kinds.ts:1-15` (13 giá trị)."""

REASONS: Final = frozenset({"size", "interval", "manual", "close"})
DURATION_FIELDS: Final = frozenset({"durationMs", "latencyMs"})
ALLOWED_CONTENT_TYPES: Final = ("application/json", "text/plain")

_SESSION_ID_RE: Final = re.compile(r"^[a-z0-9][a-z0-9._-]{0,47}$")
_FIELD_KEY_RE: Final = re.compile(r"^[a-z][A-Za-z0-9]{0,47}$")
_FIELD_STR_VALUE_RE: Final = re.compile(r"^[a-z0-9][a-z0-9._-]{0,47}$")

MAX_FIELD_NUMBER: Final = 86_400_000
MAX_DROPPED_COUNT: Final = 1_000_000

_INVALID_REASON_LABEL: Final = "invalid"
_UNSET: Final = object()
_SYSTEM_CLOCK: Final = SystemClock()


class _LogBucket:
    """Xô token của log `telemetry_batch`, một cho cả tiến trình."""

    __slots__ = ("count", "minute")

    def __init__(self) -> None:
        self.minute: int | None = None
        self.count: int = 0


_log_bucket: Final = _LogBucket()


class _EnvelopeError(Exception):
    """Vỏ lô sai một trường; mang tên trường để dựng 422 `VALIDATION(field=...)`."""

    def __init__(self, field_name: str) -> None:
        super().__init__(field_name)
        self.field_name = field_name


@dataclass(frozen=True, slots=True)
class _Envelope:
    """Vỏ lô đã qua bước 3 — mọi trường bắt buộc hợp lệ."""

    reason: str
    events: list[object]
    dropped_count: int


def ingest(body: bytes, content_type: str | None, *, clock: Clock = _SYSTEM_CLOCK) -> None:
    """Bước 2-6 của #37; trả về nghĩa là 204. Sai → `AppError` (422/400).

    `clock` chỉ dùng cho xô token log (bước 6) — tiêm được để test ghim phút, mặc định
    đồng hồ hệ thống cho handler thật (BE-00 §2.2 không cấm đồng hồ thật ngoài request).
    """
    _check_content_type(content_type)
    data = _decode_json(body)
    envelope = _parse_envelope(data)
    accepted, dropped = _process_events(envelope.events)
    TELEMETRY_CLIENT_DROPPED_TOTAL.inc(envelope.dropped_count)
    _log_batch(envelope.reason, accepted, dropped, clock)


def _check_content_type(content_type: str | None) -> None:
    """`Content-Type` vắng, `application/json` hay `text/plain` (charset bất kỳ) mới nhận."""
    if not content_type:
        return
    base = content_type.split(";", 1)[0].strip().lower()
    if base not in ALLOWED_CONTENT_TYPES:
        raise VALIDATION.error(field="contentType")


def _decode_json(body: bytes) -> object:
    """UTF-8 rồi JSON; thân không phải UTF-8, JSON hỏng hay đệ quy sâu → 400 `MALFORMED_JSON`."""
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise MALFORMED_JSON.error() from exc


def _is_non_negative_int(value: object) -> TypeGuard[int]:
    """`int` thật (không `bool`) và ≥ 0."""
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_schema_version_one(value: object) -> bool:
    """`schemaVersion == 1` với `int` thật — `true`/`1.0` không được nhận (LOG-06)."""
    return _is_non_negative_int(value) and value == 1


def _is_valid_reason(value: object) -> TypeGuard[str]:
    """`reason` là chuỗi (không `list`/`dict`/…) **và** thuộc 4 giá trị hợp lệ.

    `isinstance` phải chạy trước `in REASONS`: `REASONS` là `frozenset`, và `x in
    frozenset` băm `x` trước khi so — `list`/`dict` không băm được, ném `TypeError` mà
    không hàm nào ở đây bắt, nên lọt ra ngoài thành 500 (SEC-05, đã tái hiện).
    """
    return isinstance(value, str) and value in REASONS


def _parse_envelope(data: object) -> _Envelope:
    """Vỏ lô (bước 3): khoá lạ ở vỏ bỏ qua, sai một trường bắt buộc → 422."""
    label_reason = _INVALID_REASON_LABEL
    try:
        if not isinstance(data, dict):
            raise _EnvelopeError("schemaVersion")
        raw_reason = data.get("reason")
        if _is_valid_reason(raw_reason):
            label_reason = raw_reason
        if not _is_schema_version_one(data.get("schemaVersion")):
            raise _EnvelopeError("schemaVersion")
        session_id = data.get("sessionId")
        if not isinstance(session_id, str) or not _SESSION_ID_RE.fullmatch(session_id):
            raise _EnvelopeError("sessionId")
        if not _is_non_negative_int(data.get("sentAtMs")):
            raise _EnvelopeError("sentAtMs")
        if not _is_valid_reason(raw_reason):
            raise _EnvelopeError("reason")
        events = data.get("events")
        max_events = get_telemetry_settings().telemetry_max_events
        if not isinstance(events, list) or not (0 <= len(events) <= max_events):
            raise _EnvelopeError("events")
        dropped_count = data.get("droppedCount")
        if not _is_non_negative_int(dropped_count):
            raise _EnvelopeError("droppedCount")
        if dropped_count > MAX_DROPPED_COUNT:
            raise _EnvelopeError("droppedCount")
    except _EnvelopeError as exc:
        TELEMETRY_BATCHES_TOTAL.inc(reason=label_reason, result="rejected")
        raise VALIDATION.error(field=exc.field_name) from None
    TELEMETRY_BATCHES_TOTAL.inc(reason=raw_reason, result="accepted")
    return _Envelope(reason=raw_reason, events=events, dropped_count=dropped_count)


def _shell_of(item: object) -> dict[str, object] | None:
    """`{sequence, atMs, event}` hợp lệ → thân `event`; sai bất kỳ phần nào → `None`."""
    if not isinstance(item, dict):
        return None
    if not _is_non_negative_int(item.get("sequence")):
        return None
    if not _is_non_negative_int(item.get("atMs")):
        return None
    event = item.get("event")
    return event if isinstance(event, dict) else None


def _process_events(items: list[object]) -> tuple[dict[str, int], dict[str, int]]:
    """Bước 4-6: đếm sự kiện chấp nhận theo tên, mục bị bỏ theo lý do; observe duration."""
    accepted: dict[str, int] = {}
    dropped: dict[str, int] = {"malformed": 0, "unknown_name": 0}
    max_fields = get_telemetry_settings().telemetry_max_fields
    for item in items:
        event = _shell_of(item)
        if event is None:
            dropped["malformed"] += 1
            TELEMETRY_EVENTS_DROPPED_TOTAL.inc(cause="malformed")
            continue
        name = event.get("name")
        if not isinstance(name, str) or name not in EVENT_NAMES:
            dropped["unknown_name"] += 1
            TELEMETRY_EVENTS_DROPPED_TOTAL.inc(cause="unknown_name")
            continue
        accepted[name] = accepted.get(name, 0) + 1
        TELEMETRY_EVENTS_TOTAL.inc(name=name)
        fields = _sanitize_fields(event, max_fields)
        for duration_key in DURATION_FIELDS:
            value = fields.get(duration_key)
            if isinstance(value, int | float):
                TELEMETRY_DURATION_MS.observe(float(value), name=name)
    return accepted, dropped


def _sanitize_fields(event: dict[str, object], max_fields: int) -> dict[str, object]:
    """Bước 5: giữ trường hợp lệ theo thứ tự tên, dừng khi đủ `TELEMETRY_MAX_FIELDS`."""
    kept: dict[str, object] = {}
    for key, value in event.items():
        if key == "name":
            continue
        if len(kept) >= max_fields:
            break
        if not _FIELD_KEY_RE.fullmatch(key):
            continue
        sanitized = _sanitize_value(key, value)
        if sanitized is not _UNSET:
            kept[key] = sanitized
    return kept


def _sanitize_value(key: str, value: object) -> object:
    """Giá trị hợp lệ (bool, số 0..86.400.000, hay mã chuỗi) hay `_UNSET` để bỏ trường.

    `int` và `float` tách riêng: `int` của Python là số nguyên lớn tuỳ ý, so sánh trực
    tiếp với `MAX_FIELD_NUMBER` không bao giờ ném; `math.isfinite` chỉ gọi được cho
    `float` — gọi nó cho một `int` hàng trăm chữ số ném `OverflowError` lúc đổi sang
    double, một lỗi khác đã tái hiện trên route công khai (SEC-05).
    """
    if key == "errorKind":
        return value if isinstance(value, str) and value in ERROR_KINDS else _UNSET
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value if 0 <= value <= MAX_FIELD_NUMBER else _UNSET
    if isinstance(value, float):
        if math.isfinite(value) and 0 <= value <= MAX_FIELD_NUMBER:
            return round(value)
        return _UNSET
    if isinstance(value, str):
        return value if _FIELD_STR_VALUE_RE.fullmatch(value) else _UNSET
    return _UNSET


def _log_batch(reason: str, accepted: dict[str, int], dropped: dict[str, int], clock: Clock) -> None:
    """Một dòng log mỗi lô, qua xô token mỗi phút mỗi tiến trình (K11: không thân, không IP)."""
    limit = get_telemetry_settings().telemetry_log_max_per_min
    if not _allow_log(limit, clock):
        TELEMETRY_LOG_SUPPRESSED_TOTAL.inc()
        return
    _log.info("telemetry_batch", extra={"reason": reason, "accepted": accepted, "dropped": dropped})


def _allow_log(limit: int, clock: Clock) -> bool:
    """Cửa sổ cố định một phút, đọc phút hiện tại từ `clock` (tiêm được, không `time.time()`)."""
    minute = int(clock.now().timestamp() // 60)
    if _log_bucket.minute != minute:
        _log_bucket.minute = minute
        _log_bucket.count = 0
    if _log_bucket.count >= limit:
        return False
    _log_bucket.count += 1
    return True


def reset_log_bucket() -> None:
    """Chỉ cho test: đặt lại xô token mỗi phút; ngoài `APP_ENV=test` → `RuntimeError`."""
    require_test_env("reset_log_bucket()")
    _log_bucket.minute = None
    _log_bucket.count = 0
