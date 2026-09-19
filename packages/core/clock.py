"""Đồng hồ tiêm được: mã nghiệp vụ nhận `Clock` qua tham số, không gọi `datetime.now()`."""

from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:
        """Giờ hiện tại, UTC, có múi giờ."""
        ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)
