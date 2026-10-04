"""Test `packages.core.ids`: sinh và kiểm id có tiền tố, ULID trần, id không gian và phép đo."""

from datetime import UTC, datetime, timedelta

import pytest

from packages.core import ids
from packages.core.ids import SPATIAL_PREFIX, SpatialKind, is_id, is_measurement_id, is_spatial_id, new_id
from packages.testing.fixtures.clock import FakeClock

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
ULID_BODY = "01J" + "0" * 22 + "Z"


def _ms_of(ulid_id: str) -> int:
    """Mili giây 48 bit đọc lại từ thân ULID của một id."""
    body = ulid_id.split("_", 1)[1]
    value = 0
    for char in body[:10]:  # 10 ký tự đầu = 2 bit 0 + 48 bit mili giây
        value = value * 32 + CROCKFORD.index(char)
    return value


def test_thousand_ids_unique_and_valid(fake_clock: FakeClock) -> None:
    """Hành vi `thousand ids unique and valid` (W4, HOP-DONG-MOI §0.1)."""
    ids = [new_id("prj", fake_clock) for _ in range(1000)]
    assert len(set(ids)) == 1000
    assert all(is_id("prj", i) for i in ids)
    assert all(len(i) == 30 for i in ids)


def test_time_part_follows_clock(fake_clock: FakeClock) -> None:
    """Hành vi `time part follows clock` (W4, HOP-DONG-MOI §0.1)."""
    first = new_id("usr", fake_clock)
    assert _ms_of(first) == int(datetime(2026, 1, 1, tzinfo=UTC).timestamp()) * 1000
    fake_clock.advance(timedelta(milliseconds=1))
    second = new_id("usr", fake_clock)
    assert _ms_of(second) == _ms_of(first) + 1
    assert second > first


def test_new_id_rejects_time_before_epoch() -> None:
    """Hành vi `new id rejects time before epoch` (W4, HOP-DONG-MOI §0.1)."""
    with pytest.raises(ValueError, match="1970"):
        new_id("job", FakeClock(datetime(1969, 12, 31, 23, 59, 59, tzinfo=UTC)))


def test_new_id_rejects_unknown_prefix(fake_clock: FakeClock) -> None:
    """Hành vi `new id rejects unknown prefix` (W4, HOP-DONG-MOI §0.1)."""
    with pytest.raises(ValueError, match="tiền tố"):
        new_id("abc", fake_clock)  # type: ignore[arg-type]  # kiểm lúc chạy


def test_is_id_accepts_valid() -> None:
    """Hành vi `is id accepts valid` (W4, HOP-DONG-MOI §0.1)."""
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
    """Hành vi `is id rejects` (W4, HOP-DONG-MOI §0.1)."""
    assert not is_id("usr", value)


def test_is_id_rejects_unknown_prefix() -> None:
    """Hành vi `is id rejects unknown prefix` (W4, HOP-DONG-MOI §0.1)."""
    with pytest.raises(ValueError, match="tiền tố"):
        is_id("abc", f"abc_{ULID_BODY}")  # type: ignore[arg-type]  # kiểm lúc chạy


@pytest.mark.parametrize(
    ("value", "ok"),
    [
        (ULID_BODY, True),
        ("7" + "Z" * 25, True),
        ("", False),
        (ULID_BODY.lower(), False),
        (ULID_BODY[:-1], False),
        (f"{ULID_BODY}0", False),
        (f"{ULID_BODY[:-1]}I", False),
        (f"{ULID_BODY[:-1]}L", False),
        (f"{ULID_BODY[:-1]}O", False),
        (f"{ULID_BODY[:-1]}U", False),
        (f"{ULID_BODY}\n", False),
        (ULID_BODY[:-1] + chr(0xFF10), False),  # chữ số toàn khổ: không thuộc Crockford base32
        (f"usr_{ULID_BODY}", False),
    ],
)
def test_is_ulid(value: str, ok: bool) -> None:
    """NO-076: thân ULID trần (tên ảnh đại diện) — Crockford base32 HOA đúng 26 ký tự, không tiền tố."""
    assert ids.is_ulid(value) is ok


def test_is_id_reads_ulid_rule_of_is_ulid(monkeypatch: pytest.MonkeyPatch) -> None:
    """NO-076: `is_id` kiểm thân bằng đúng `is_ulid` — luật thân ULID chỉ có một nguồn."""
    assert is_id("usr", f"usr_{ULID_BODY}")
    monkeypatch.setattr(ids, "is_ulid", lambda _: False)
    assert not is_id("usr", f"usr_{ULID_BODY}")


def test_check_id_returns_valid_id() -> None:
    """Hành vi `check id returns valid id` (W4, HOP-DONG-MOI §0.1)."""
    assert ids.check_id("upl", f"upl_{ULID_BODY}") == f"upl_{ULID_BODY}"


@pytest.mark.parametrize("value", ["", f"prj_{ULID_BODY}", f"upl_{ULID_BODY[:-1]}", ULID_BODY])
def test_check_id_rejects_naming_the_prefix(value: str) -> None:
    """Dạng ném lỗi của `is_id` cho người dựng khoá: thông báo nêu đúng tiền tố cần."""
    with pytest.raises(ValueError, match="upl_<ULID>"):
        ids.check_id("upl", value)


def test_check_id_rejects_unknown_prefix() -> None:
    """Hành vi `check id rejects unknown prefix` (W4, HOP-DONG-MOI §0.1)."""
    with pytest.raises(ValueError, match="tiền tố"):
        ids.check_id("abc", f"abc_{ULID_BODY}")  # type: ignore[arg-type]  # kiểm lúc chạy


@pytest.mark.parametrize(("kind", "letter"), SPATIAL_PREFIX.items())
def test_is_spatial_id_each_kind(kind: SpatialKind, letter: str) -> None:
    """Hành vi `is spatial id each kind` (W4, HOP-DONG-MOI §0.1)."""
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
    """Hành vi `is spatial id body` (W4, HOP-DONG-MOI §0.1)."""
    assert is_spatial_id("wall", value) is ok


def test_spatial_prefix_matches_fe() -> None:
    """Hành vi `spatial prefix matches fe` (W4, HOP-DONG-MOI §0.1)."""
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
    """Hành vi `is measurement id` (W4, HOP-DONG-MOI §0.1)."""
    assert is_measurement_id(value) is ok


def test_new_ulid__bare_body_follows_clock(fake_clock: FakeClock) -> None:
    """NO-168: `new_ulid` trả thân 26 ký tự trần, mili giây theo đồng hồ, và là thân của `new_id`."""
    body = ids.new_ulid(fake_clock)
    assert ids.is_ulid(body)
    assert _ms_of(f"x_{body}") == int(datetime(2026, 1, 1, tzinfo=UTC).timestamp()) * 1000
    assert ids.is_id("prj", new_id("prj", fake_clock))


def test_new_ulid__rejects_time_before_epoch() -> None:
    """NO-168: thời điểm trước 1970 → `ValueError` như `new_id`."""
    with pytest.raises(ValueError, match="1970"):
        ids.new_ulid(FakeClock(datetime(1969, 12, 31, 23, 59, 59, tzinfo=UTC)))
