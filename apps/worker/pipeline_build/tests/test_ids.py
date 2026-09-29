"""`new_spatial_id` (B5-05 [6] "Id"): duy nhất, đúng tiền tố, thân 25 ký tự, tăng theo thời gian."""

from datetime import UTC, datetime, timedelta

import pytest

from apps.worker.pipeline_build.ids import new_spatial_id
from packages.core.ids import SPATIAL_PREFIX, SpatialKind, is_spatial_id
from packages.testing.fixtures.clock import FakeClock


def test_new_spatial_id__unique_and_well_formed(fake_clock: FakeClock) -> None:
    """10.000 id cùng mốc thời gian vẫn khác nhau (80 bit ngẫu nhiên) và đúng khuôn W4."""
    ids = {new_spatial_id("wall", fake_clock) for _ in range(10_000)}
    assert len(ids) == 10_000
    assert all(is_spatial_id("wall", value) for value in ids)
    assert {len(value.split("-")[1]) for value in ids} == {25}


@pytest.mark.parametrize("kind", sorted(SPATIAL_PREFIX))
def test_new_spatial_id__prefix_per_kind(kind: SpatialKind, fake_clock: FakeClock) -> None:
    """Mỗi loại thực thể lấy đúng tiền tố của `SPATIAL_PREFIX`."""
    value = new_spatial_id(kind, fake_clock)
    assert value.startswith(f"{SPATIAL_PREFIX[kind]}-")
    assert is_spatial_id(kind, value)


def test_new_spatial_id__sorts_by_time(fake_clock: FakeClock) -> None:
    """Đồng hồ tiến 1 ms → id sau lớn hơn theo thứ tự chuỗi (đệm `0` đủ 25 ký tự)."""
    earlier = new_spatial_id("room", fake_clock)
    fake_clock.advance(timedelta(milliseconds=1))
    assert new_spatial_id("room", fake_clock) > earlier


def test_new_spatial_id__negative_milliseconds_rejected() -> None:
    """Mốc trước 1970 không biểu diễn được bằng 48 bit ms → `ValueError`, không id rác."""
    clock = FakeClock(start=datetime(1969, 1, 1, tzinfo=UTC))
    with pytest.raises(ValueError, match="ULID"):
        new_spatial_id("wall", clock)
