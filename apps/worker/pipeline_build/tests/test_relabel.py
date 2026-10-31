"""Test `rooms.relabel_by_size` và chỗ `build_furniture` dùng nó (U34: sửa nhãn đồ theo kích thước mm)."""

from collections import Counter

import pytest

from apps.worker.pipeline_build.geometry import Scaling
from apps.worker.pipeline_build.rooms import build_furniture, relabel_by_size
from packages.domain.rules_ai import LOW_CONFIDENCE_CAP
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


@pytest.mark.parametrize(("trusted", "confidence"), [(True, 0.9), (False, LOW_CONFIDENCE_CAP)])
def test_build_furniture_relabels_at_final_scale(fake_clock: FakeClock, trusted: bool, confidence: float) -> None:
    """Kích thước xét ở tỉ lệ `final`; tỉ lệ chưa tin → vẫn đổi nhưng hạ `confidence`."""
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
    assert (items[0].kind, items[0].variant, items[0].confidence) == ("chair", "sofa", confidence)
