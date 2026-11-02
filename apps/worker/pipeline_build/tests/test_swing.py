"""`swing.read_leaf`: cửa một cánh vẽ tổng hợp (cánh + cung 1/4) ở 4 hướng tường x 2 bản lề x 2 phía."""

import math

import cv2
import numpy as np
import pytest

from apps.worker.pipeline_build.residual import PageRaster
from apps.worker.pipeline_build.swing import Leaf, Vec, read_leaf, rule_side, settle_reversed
from packages.domain.spatial import sample_layer

SIZE = 200
WIDTH = 60.0
HALF = 5.0
CENTRE = np.array([100.0, 100.0])


def _door(direction: Vec, hinge_at_b: bool, side: int, *, arc: bool = True) -> tuple[PageRaster, tuple[Vec, Vec]]:
    """Trang trắng, tường dày 10 px theo `direction` có khe rộng 60 px giữa trang, cánh + cung vẽ đen."""
    u = np.array(direction, float)
    n = np.array([-u[1], u[0]])
    a, b = CENTRE - u * WIDTH / 2, CENTRE + u * WIDTH / 2
    gray = np.full((SIZE, SIZE), 255, np.uint8)
    walls = np.zeros((SIZE, SIZE), np.uint8)
    for end, out in ((a, -u), (b, u)):
        cv2.line(walls, tuple(np.rint(end).astype(int)), tuple(np.rint(end + out * 80).astype(int)), 1, int(2 * HALF))
    gray[walls > 0] = 60
    hinge, other = (b, a) if hinge_at_b else (a, b)
    pivot = hinge + side * n * HALF
    tip = pivot + side * n * WIDTH
    cv2.line(gray, tuple(np.rint(pivot).astype(int)), tuple(np.rint(tip).astype(int)), 0, 2)
    if arc:
        t = (other - hinge) / WIDTH
        pts = [pivot + WIDTH * (t * math.cos(q) + side * n * math.sin(q)) for q in np.linspace(0, math.pi / 2, 40)]
        cv2.polylines(gray, [np.rint(pts).astype(np.int32)], False, 0, 1)
    return PageRaster(gray=gray, walls=walls.astype(bool)), ((float(a[0]), float(a[1])), (float(b[0]), float(b[1])))


@pytest.mark.parametrize("direction", [(1.0, 0.0), (-1.0, 0.0), (0.0, 1.0), (0.0, -1.0)])
@pytest.mark.parametrize("hinge_at_b", [False, True])
@pytest.mark.parametrize("side", [1, -1])
def test_reads_hinge_and_side(direction: tuple[float, float], hinge_at_b: bool, side: int) -> None:
    page, (a, b) = _door(direction, hinge_at_b, side)
    assert read_leaf(page, a, b, HALF) == Leaf(hinge_at_b=hinge_at_b, side=side)


def test_no_arc_is_none() -> None:
    """Chỉ có nét cánh (hay đường kích thước) mà không có cung → không đoán."""
    page, (a, b) = _door((1.0, 0.0), False, 1, arc=False)
    assert read_leaf(page, a, b, HALF) is None


def test_blank_and_narrow_are_none() -> None:
    blank = PageRaster(gray=np.full((SIZE, SIZE), 255, np.uint8), walls=np.zeros((SIZE, SIZE), bool))
    assert read_leaf(blank, (70.0, 100.0), (130.0, 100.0), HALF) is None
    page, _ = _door((1.0, 0.0), False, 1)
    assert read_leaf(page, (95.0, 100.0), (100.0, 100.0), HALF) is None


def test_settle_reversed_flips_only_against_rule() -> None:
    """Cánh đọc được cùng phía luật FE → giữ `reversed=False`; ngược phía → `True`."""
    layer = sample_layer(0)
    opening = layer.openings[0]
    wall = next(w for w in layer.walls if w.id == opening.wall_id)
    start, end = wall.centreline.start, wall.centreline.end
    length = math.hypot(end.x - start.x, end.y - start.y)
    rule = rule_side(opening, wall, layer.rooms)
    normal = (-(end.y - start.y) / length * rule, (end.x - start.x) / length * rule)
    same = settle_reversed(layer, {opening.id: normal})
    flipped = settle_reversed(layer, {opening.id: (-normal[0], -normal[1])})
    assert not same.openings[0].reversed
    assert flipped.openings[0].reversed
    assert settle_reversed(layer, {}) is layer
