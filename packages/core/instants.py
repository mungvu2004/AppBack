"""Ngày giờ trên dây (W3): `YYYY-MM-DDTHH:MM:SS.sssZ`, UTC, đúng 3 chữ số mili giây."""

import re
from datetime import UTC, datetime

_WIRE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}Z")


def _utc(dt: datetime) -> datetime:
    if dt.utcoffset() is None:
        raise ValueError("datetime không có múi giờ")
    return dt.astimezone(UTC)


def to_wire(dt: datetime) -> str:
    """Đổi sang UTC, cắt (không làm tròn) về mili giây."""
    u = _utc(dt)
    return (
        f"{u.year:04d}-{u.month:02d}-{u.day:02d}T{u.hour:02d}:{u.minute:02d}:{u.second:02d}"
        f".{u.microsecond // 1000:03d}Z"
    )


def parse_wire(s: str) -> datetime:
    if not _WIRE_RE.fullmatch(s):
        raise ValueError("chuỗi ngày giờ sai mẫu YYYY-MM-DDTHH:MM:SS.sssZ")
    return datetime.fromisoformat(s)


def floor_to_hour(dt: datetime) -> datetime:
    """Làm tròn xuống đầu giờ, UTC (W23: hạn ký URL ổn định giữa các lần đọc)."""
    return _utc(dt).replace(minute=0, second=0, microsecond=0)
