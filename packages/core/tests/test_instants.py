from datetime import UTC, datetime, timedelta, timezone

import pytest

from packages.core.instants import floor_to_hour, parse_wire, to_wire

ICT = timezone(timedelta(hours=7))


def test_to_wire_truncates_not_rounds() -> None:
    assert to_wire(datetime(2026, 1, 2, 3, 4, 5, 999999, tzinfo=UTC)) == "2026-01-02T03:04:05.999Z"
    assert to_wire(datetime(2026, 1, 2, 3, 4, 5, 999, tzinfo=UTC)) == "2026-01-02T03:04:05.000Z"


def test_to_wire_converts_offset_to_utc() -> None:
    assert to_wire(datetime(2026, 1, 1, 7, 0, 0, 123000, tzinfo=ICT)) == "2026-01-01T00:00:00.123Z"


def test_to_wire_pads_small_year() -> None:
    assert to_wire(datetime(5, 1, 1, tzinfo=UTC)) == "0005-01-01T00:00:00.000Z"


def test_to_wire_rejects_naive() -> None:
    with pytest.raises(ValueError, match="múi giờ"):
        to_wire(datetime(2026, 1, 1))  # noqa: DTZ001 — kiểm datetime không múi giờ bị từ chối


def test_parse_wire_round_trip() -> None:
    parsed = parse_wire("2026-03-04T05:06:07.089Z")
    assert parsed == datetime(2026, 3, 4, 5, 6, 7, 89000, tzinfo=UTC)
    assert parsed.utcoffset() == timedelta(0)
    assert to_wire(parsed) == "2026-03-04T05:06:07.089Z"


@pytest.mark.parametrize(
    "value",
    [
        "2026-01-01T00:00:00.000000Z",  # 6 chữ số
        "2026-01-01T00:00:00.000",  # thiếu Z
        "2026-01-01T00:00:00.000+00:00",
        "2026-01-01T00:00:00Z",
        "2026-01-01T00:00:00.00Z",
        "2026-01-01 00:00:00.000Z",
        "2026-01-01T00:00:00.000Z\n",
        f"2026-01-0{chr(0x661)}T00:00:00.000Z",  # chữ số Ả Rập
        "2026-13-01T00:00:00.000Z",  # đúng mẫu, sai lịch
    ],
)
def test_parse_wire_rejects(value: str) -> None:
    with pytest.raises(ValueError, match=r"mẫu|month"):
        parse_wire(value)


def test_floor_to_hour() -> None:
    assert floor_to_hour(datetime(2026, 1, 1, 10, 59, 59, 999999, tzinfo=ICT)) == datetime(2026, 1, 1, 3, tzinfo=UTC)


def test_floor_to_hour_rejects_naive() -> None:
    with pytest.raises(ValueError, match="múi giờ"):
        floor_to_hour(datetime(2026, 1, 1, 10))  # noqa: DTZ001 — kiểm datetime không múi giờ bị từ chối
