"""Test `rooms.relabel_by_size` và chỗ `build_furniture` dùng nó (U34: sửa nhãn đồ theo kích thước mm)."""

from collections import Counter

import pytest

from apps.worker.pipeline_build.geometry import Scaling
from apps.worker.pipeline_build.rooms import build_furniture, relabel_by_size
from packages.ml_contracts.artifacts import BoxPx, DetectionPx
from packages.testing.fixtures.clock import FakeClock

LEVEL_ID = "L-0000000000000000000000000"


@pytest.mark.parametrize(
    ("kind", "size", "expected"),
    [
        ("chair", (2600, 900), ("chair", "sofa")),
        ("chair", (850, 2500), ("chair", "sofa")),
        ("chair", (1043, 2075), ("bed", "bed")),
        ("other", (1600, 2000), ("bed", "bed")),
        ("chair", (500, 500), ("chair", None)),
        ("chair", (1300, 900), ("chair", None)),
        ("chair", (1500, 2400), ("chair", "sofa")),
        ("chair", (1600, 2600), ("chair", "sofa")),
        ("chair", (1700, 2600), ("chair", None)),
        ("other", (2600, 900), ("other", None)),
        ("table", (1000, 2000), ("table", None)),
        ("table", (900, 2600), ("table", None)),
        ("kitchenCabinet", (600, 2100), ("kitchenCabinet", None)),
        ("bed", (1600, 2000), ("bed", None)),
    ],
)
def test_relabel_by_size(kind: str, size: tuple[int, int], expected: tuple[str, str | None]) -> None:
    """Ghế dài → sofa, cỡ giường → giường; bàn, tủ bếp, nhãn đã đúng giữ nguyên."""
    assert relabel_by_size(kind, *size) == expected


@pytest.mark.parametrize(("usage", "expected"), [("livingRoom", ("chair", None)), ("bedroom", ("bed", "bed"))])
def test_no_bed_in_living_room(usage: str, expected: tuple[str, str | None]) -> None:
    """Bộ sofa + bàn trà cỡ giường ở phòng khách không thành giường."""
    assert relabel_by_size("chair", 1807, 2185, room_usage=usage) == expected


@pytest.mark.parametrize(("trusted", "variant"), [(True, "sofa"), (False, None)])
def test_build_furniture_relabels_at_final_scale(fake_clock: FakeClock, trusted: bool, variant: str | None) -> None:
    """Kích thước xét ở tỉ lệ `final`; tỉ lệ chưa tin → không đổi loại theo cỡ (B10)."""
    box = BoxPx(x_min=0, y_min=0, x_max=260, y_max=90)  # 2600 x 900 mm ở 10 mm/px
    detections = (DetectionPx(label="chair", box=box, confidence=0.9),)
    items = build_furniture(
        detections,
        (),
        level_id=LEVEL_ID,
        scaling=Scaling(build=1.0, final=10.0),
        clock=fake_clock,
        dropped=Counter(),
        scale_trusted=trusted,
    )
    assert (items[0].kind, items[0].variant, items[0].confidence) == ("chair", variant, 0.9)


@pytest.mark.parametrize(
    ("usage", "expected"),
    [
        ("livingRoom", ("bed", None)),
        ("bathroom", ("bed", None)),
        ("bedroom", ("bed", None)),
        (None, ("bed", None)),
    ],
)
def test_yolo_bed_stays_bed_in_every_room(usage: str | None, expected: tuple[str, str | None]) -> None:
    """B10: YOLO báo giường giữ là giường ở mọi phòng (luật "→ thảm" UX-14 bỏ: đổi nhầm giường thật)."""
    assert relabel_by_size("bed", 2476, 2079, room_usage=usage) == expected


@pytest.mark.parametrize(
    ("size", "near_table", "expected"),
    [
        ((1200, 450), True, ("chair", "bench")),
        ((1200, 450), False, ("chair", None)),
        ((900, 450), True, ("chair", None)),
        ((1200, 600), True, ("chair", None)),
    ],
)
def test_long_narrow_chair_near_table_is_bench(
    size: tuple[int, int], near_table: bool, expected: tuple[str, str | None]
) -> None:
    """B10: ghế dài ≥ 1000, cạnh ngắn < 600, cạnh bàn → băng ghế."""
    assert relabel_by_size("chair", *size, near_table=near_table) == expected


@pytest.mark.parametrize(("table_x", "variant"), [(1900, "bench"), (2500, None)])
def test_build_furniture_finds_table_within_900_mm(fake_clock: FakeClock, table_x: int, variant: str | None) -> None:
    """Ghế 1200 x 450 cách bàn 800 mm → băng ghế; cách 1400 mm → giữ ghế."""
    detections = (
        DetectionPx(label="chair", box=BoxPx(x_min=0, y_min=0, x_max=1200, y_max=450), confidence=0.9),
        DetectionPx(label="table", box=BoxPx(x_min=table_x, y_min=0, x_max=table_x + 800, y_max=800), confidence=0.9),
    )
    items = build_furniture(
        detections, (), level_id=LEVEL_ID, scaling=Scaling(build=1.0, final=1.0), clock=fake_clock, dropped=Counter()
    )
    assert items[0].variant == variant
