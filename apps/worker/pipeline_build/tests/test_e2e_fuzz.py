"""Không ném trên đầu ra AI xấu (B5-05 việc E): `build_layer` phải xử lý được đầu vào lộn xộn.

200 bộ ngẫu nhiên hợp trần hình học B5-01 (hộp chồng nhau, tường ngắn, hộp ngoài đầu tường, chữ rác);
`build_layer` không được ném lỗi và `check_integrity` không được có vấn đề nghiêm trọng.
"""

import math
import random
from datetime import UTC, datetime
from decimal import Decimal
from typing import Final

import pytest

from apps.worker.pipeline_build.build import build_layer
from apps.worker.pipeline_build.ids import new_spatial_id
from packages.domain.spatial.integrity import check_integrity, has_critical
from packages.ml_contracts.artifacts import (
    BoxPx,
    DetectionPx,
    ObjectsResult,
    TextPx,
    TextResult,
    WallPx,
    WallsResult,
)
from packages.ml_contracts.labels import DETECTION_LABELS
from packages.testing.fixtures.clock import FakeClock

_WIDTH_PX = 1600
_HEIGHT_PX = 1200
_FALLBACK_MM_PER_PX = Decimal("10")
_LEVEL_ID: Final = new_spatial_id("level", FakeClock(start=datetime(2026, 1, 1, tzinfo=UTC)))


def _random_box(rng: random.Random) -> BoxPx:
    """Hộp thẳng trục ngẫu nhiên trong ảnh, cạnh dương (kể cả hộp rất nhỏ, chồng lấn tường)."""
    x0, x1 = sorted(rng.uniform(0, _WIDTH_PX) for _ in range(2))
    y0, y1 = sorted(rng.uniform(0, _HEIGHT_PX) for _ in range(2))
    if x1 - x0 < 1:
        x1 = x0 + 1
    if y1 - y0 < 1:
        y1 = y0 + 1
    return BoxPx(x_min=x0, y_min=y0, x_max=x1, y_max=y1)


def _random_wall(rng: random.Random) -> WallPx:
    """Tường ngẫu nhiên, gồm cả tường rất ngắn (vài px)."""
    x0, y0 = rng.uniform(0, _WIDTH_PX), rng.uniform(0, _HEIGHT_PX)
    length = rng.uniform(1, 400)
    angle = rng.uniform(0, 2 * math.pi)
    x1 = min(max(x0 + length * math.cos(angle), 0), _WIDTH_PX)
    y1 = min(max(y0 + length * math.sin(angle), 0), _HEIGHT_PX)
    if (x0, y0) == (x1, y1):
        x1 = min(x0 + 1, _WIDTH_PX)
    return WallPx(
        start={"x": x0, "y": y0},
        end={"x": x1, "y": y1},
        thickness_px=rng.uniform(1, 40),
        confidence=rng.uniform(0, 1),
    )


def _random_detection(rng: random.Random) -> DetectionPx:
    """Phát hiện ngẫu nhiên, hộp có thể nằm ngoài mọi đầu tường (không gắn được ô mở nào)."""
    return DetectionPx(label=rng.choice(DETECTION_LABELS), box=_random_box(rng), confidence=rng.uniform(0, 1))


def _random_text(rng: random.Random) -> TextPx:
    """Chữ rác ngẫu nhiên, không phải số đo hợp lệ."""
    junk = "".join(rng.choice("abcXYZ!@# ") for _ in range(rng.randint(1, 12))) or "x"
    return TextPx(text=junk, box=_random_box(rng), confidence=rng.uniform(0, 1))


@pytest.mark.parametrize("seed", range(200))
def test_build_layer__fuzz_does_not_raise(seed: int, fake_clock: FakeClock) -> None:
    """`random.Random(seed)` hợp trần B5-01 → `build_layer` không ném và không có vấn đề nghiêm trọng."""
    rng = random.Random(seed)  # noqa: S311 — dữ liệu fuzz test, không phải mật mã
    walls = tuple(_random_wall(rng) for _ in range(rng.randint(0, 20)))
    detections = tuple(_random_detection(rng) for _ in range(rng.randint(0, 20)))
    texts = tuple(_random_text(rng) for _ in range(rng.randint(0, 10)))

    built = build_layer(
        level_id=_LEVEL_ID,
        walls=WallsResult(walls=walls),
        objects=ObjectsResult(detections=detections),
        text=TextResult(items=texts),
        width_px=_WIDTH_PX,
        height_px=_HEIGHT_PX,
        fallback_mm_per_px=_FALLBACK_MM_PER_PX,
        clock=fake_clock,
    )

    issues = check_integrity(built.layer, level_id=_LEVEL_ID)
    assert not has_critical(issues), f"seed {seed}: {issues}"
