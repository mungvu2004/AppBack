"""Phân vùng bố cục trang `segment_page` trên ảnh tổng hợp (khung giấy, khối nét, khung tên)."""

import cv2
import numpy as np
import pytest
from numpy.typing import NDArray

from packages.vision.layout import Box, segment_page

_W, _H = 1400, 1000


def _page() -> NDArray[np.uint8]:
    """Trang trắng RGB `_H × _W` có đường khung giấy cách mép 2 %."""
    img = np.full((_H, _W, 3), 255, np.uint8)
    cv2.rectangle(img, (28, 20), (_W - 28, _H - 20), (0, 0, 0), 3)
    return img


def _plan(img: NDArray[np.uint8], x0: int, y0: int, x1: int, y1: int) -> None:
    """Vẽ một "mặt bằng": viền ngoài + vài vách trong, nét liền nhau."""
    cv2.rectangle(img, (x0, y0), (x1, y1), (0, 0, 0), 4)
    cv2.line(img, ((x0 + x1) // 2, y0), ((x0 + x1) // 2, y1), (0, 0, 0), 3)
    cv2.line(img, (x0, (y0 + y1) // 2), (x1, (y0 + y1) // 2), (0, 0, 0), 3)


def _area(box: Box) -> float:
    """Diện tích tỉ lệ của hộp."""
    return (box.x1 - box.x0) * (box.y1 - box.y0)


def test_segment_page__two_plans() -> None:
    """Hai mặt bằng + khung tên trong khung giấy → 2 hộp lớn + 1 hộp nhỏ, không hộp nào phủ cả trang."""
    img = _page()
    _plan(img, 100, 100, 640, 600)
    _plan(img, 760, 100, 1300, 600)
    cv2.rectangle(img, (950, 760), (1300, 940), (0, 0, 0), 3)
    cv2.putText(img, "TITLE", (990, 860), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 3)

    boxes = segment_page(img)

    assert len(boxes) == 3
    assert sorted(_area(b) > 0.15 for b in boxes) == [False, True, True]
    assert all(_area(b) < 0.5 for b in boxes)
    assert boxes[0].x0 < boxes[1].x0  # cùng hàng trên: trái trước phải
    assert boxes[2].y0 > boxes[0].y1  # khung tên ở dưới cùng


def test_segment_page__empty_page() -> None:
    """Trang chỉ có khung giấy (ảnh xám) → một hộp phủ cả trang."""
    gray = cv2.cvtColor(_page(), cv2.COLOR_RGB2GRAY)
    assert segment_page(gray) == (Box(0.0, 0.0, 1.0, 1.0),)


def test_segment_page__merges_overlaps() -> None:
    """Khối nét nằm trong viền một khối khác (không chạm) → gộp thành một hộp."""
    img = _page()
    cv2.rectangle(img, (150, 150), (900, 800), (0, 0, 0), 4)
    _plan(img, 350, 330, 700, 620)

    boxes = segment_page(img)

    assert len(boxes) == 1
    assert boxes[0].x0 < 150 / _W < 900 / _W < boxes[0].x1


def test_segment_page__boxes_normalized() -> None:
    """Mọi hộp có 0 ≤ x0 < x1 ≤ 1, 0 ≤ y0 < y1 ≤ 1 kể cả khi nét chạm mép ảnh; `Box` sai → ValueError."""
    img = np.full((_H, _W, 3), 255, np.uint8)
    _plan(img, 0, 0, 700, 600)
    _plan(img, 800, 500, _W - 1, _H - 1)

    boxes = segment_page(img)

    assert len(boxes) == 2
    for b in boxes:
        assert 0.0 <= b.x0 < b.x1 <= 1.0
        assert 0.0 <= b.y0 < b.y1 <= 1.0
    for bad in ((0.5, 0.0, 0.5, 1.0), (0.0, 0.6, 1.0, 0.2), (-0.1, 0.0, 1.0, 1.0), (0.0, 0.0, 1.0, 1.1)):
        with pytest.raises(ValueError):
            Box(*bad)
