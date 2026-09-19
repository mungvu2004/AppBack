"""Đồng hồ giả (B0-02): `fake_clock` bắt đầu ở 2026-01-01T00:00:00Z, chỉ nhận datetime có múi giờ."""

from datetime import UTC, datetime, timedelta

import pytest


class FakeClock:
    def __init__(self, start: datetime) -> None:
        self._now = _aware(start)

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> None:
        self._now += delta

    def set(self, dt: datetime) -> None:
        self._now = _aware(dt)


def _aware(dt: datetime) -> datetime:
    if dt.utcoffset() is None:
        raise ValueError("FakeClock chỉ nhận datetime có múi giờ")
    return dt.astimezone(UTC)


@pytest.fixture
def fake_clock() -> FakeClock:
    return FakeClock(start=datetime(2026, 1, 1, tzinfo=UTC))
