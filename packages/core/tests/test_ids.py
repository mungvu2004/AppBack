from datetime import UTC, datetime, timedelta

import pytest

from packages.core.ids import SPATIAL_PREFIX, SpatialKind, is_id, is_measurement_id, is_spatial_id, new_id
from packages.testing.fixtures.clock import FakeClock

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
ULID_BODY = "01J" + "0" * 22 + "Z"


def _ms_of(ulid_id: str) -> int:
    body = ulid_id.split("_", 1)[1]
    value = 0
    for char in body[:10]:  # 10 ký tự đầu = 2 bit 0 + 48 bit mili giây
        value = value * 32 + CROCKFORD.index(char)
    return value


def test_thousand_ids_unique_and_valid(fake_clock: FakeClock) -> None:
    ids = [new_id("prj", fake_clock) for _ in range(1000)]
    assert len(set(ids)) == 1000
    assert all(is_id("prj", i) for i in ids)
    assert all(len(i) == 30 for i in ids)


def test_time_part_follows_clock(fake_clock: FakeClock) -> None:
    first = new_id("usr", fake_clock)
    assert _ms_of(first) == int(datetime(2026, 1, 1, tzinfo=UTC).timestamp()) * 1000
    fake_clock.advance(timedelta(milliseconds=1))
    second = new_id("usr", fake_clock)
    assert _ms_of(second) == _ms_of(first) + 1
    assert second > first


def test_new_id_rejects_time_before_epoch() -> None:
    with pytest.raises(ValueError, match="1970"):
        new_id("job", FakeClock(datetime(1969, 12, 31, 23, 59, 59, tzinfo=UTC)))


def test_new_id_rejects_unknown_prefix(fake_clock: FakeClock) -> None:
    with pytest.raises(ValueError, match="tiền tố"):
        new_id("abc", fake_clock)  # type: ignore[arg-type]  # kiểm lúc chạy


def test_is_id_accepts_valid() -> None:
    assert is_id("tpl", f"tpl_{ULID_BODY}")


@pytest.mark.parametrize(
    "value",
    [
        f"prj_{ULID_BODY}",  # sai tiền tố
        f"usr_{ULID_BODY.lower()}",
        f"usr_{ULID_BODY[:-1]}",
        f"usr_{ULID_BODY}0",
        f"usr_{ULID_BODY[:-1]}I",
        f"usr_{ULID_BODY[:-1]}L",
        f"usr_{ULID_BODY[:-1]}O",
        f"usr_{ULID_BODY[:-1]}U",
        f"usr-{ULID_BODY}",
        f"usr_{ULID_BODY}\n",
    ],
)
def test_is_id_rejects(value: str) -> None:
    assert not is_id("usr", value)


def test_is_id_rejects_unknown_prefix() -> None:
    with pytest.raises(ValueError, match="tiền tố"):
        is_id("abc", f"abc_{ULID_BODY}")  # type: ignore[arg-type]  # kiểm lúc chạy


@pytest.mark.parametrize(("kind", "letter"), SPATIAL_PREFIX.items())
def test_is_spatial_id_each_kind(kind: SpatialKind, letter: str) -> None:
    assert is_spatial_id(kind, f"{letter}-0000010ABC")
    other = "W" if letter != "W" else "L"
    assert not is_spatial_id(kind, f"{other}-0000010ABC")


@pytest.mark.parametrize(
    ("value", "ok"),
    [
        ("W-" + "A" * 10, True),
        ("W-" + "Z9" * 32, True),  # 64 ký tự
        ("W-" + "A" * 9, False),
        ("W-" + "A" * 65, False),
        ("W-0000010abc", False),
        ("W_0000010ABC", False),
        ("W-0000010ABC\n", False),
        ("W-0000010ÀBC", False),
    ],
)
def test_is_spatial_id_body(value: str, ok: bool) -> None:
    assert is_spatial_id("wall", value) is ok


def test_spatial_prefix_matches_fe() -> None:
    assert SPATIAL_PREFIX == {
        "level": "L",
        "wall": "W",
        "opening": "D",
        "furniture": "F",
        "room": "R",
        "axis": "A",
        "dimension": "M",
    }


@pytest.mark.parametrize(
    ("value", "ok"),
    [
        ("MS-0001", True),
        ("MS-" + "9" * 15, True),
        ("MS-123", False),
        ("MS-" + "9" * 16, False),
        ("ms-1234", False),
        ("MS-" + chr(0x661) * 4, False),  # chữ số Ả Rập: `\d` khớp, `[0-9]` không
        ("MS-1234\n", False),
        ("MS1234", False),
    ],
)
def test_is_measurement_id(value: str, ok: bool) -> None:
    assert is_measurement_id(value) is ok
