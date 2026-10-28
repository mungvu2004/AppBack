"""Nguồn gợi ý mực dư `residual.residual_ink_boxes`, `decode_page_raster` và nối vào `build_layer` (B4 vật sót)."""

from datetime import UTC, datetime

import cv2
import numpy as np
import pytest

from apps.worker.pipeline_build.build import BuiltLayer, _suggestions
from apps.worker.pipeline_build.residual import (
    MAX_SUGGESTIONS,
    Box,
    PageRaster,
    decode_page_raster,
    residual_ink_boxes,
)
from apps.worker.pipeline_build.tests.helpers import build_wrapped
from packages.ml_contracts.artifacts import BoxPx, DetectionPx, PointPx, WallPx, encode_mask, encode_rgb_png
from packages.testing.fixtures.clock import FakeClock

_MM_PER_PX = 10.0
"""1 m = 100 px."""

_W, _H = 800, 600
_SOFA: Box = (300.0, 250.0, 400.0, 310.0)
"""Một món đồ không nhãn: khung 1,0 x 0,6 m."""


def _page(fill: int = 255) -> PageRaster:
    """Căn hộ 7 x 5 m: tường bao dày 10 px vẽ đen trên nền `fill`, mặt nạ tường khớp nét vẽ."""
    gray = np.full((_H, _W), 255, np.uint8)
    walls = np.zeros((_H, _W), np.uint8)
    cv2.rectangle(walls, (50, 50), (750, 550), 1, 10)
    gray[55:546, 55:746] = fill
    gray[walls > 0] = 0
    return PageRaster(gray=gray, walls=walls.astype(np.bool_))


def _draw(page: PageRaster, box: Box) -> None:
    """Vẽ khung đồ nét 2 px lên trang."""
    x0, y0, x1, y1 = (int(v) for v in box)
    cv2.rectangle(page.gray, (x0, y0), (x1, y1), 0, 2)


def test_unlabelled_rectangle_yields_one_suggestion() -> None:
    """Nền trắng, một khung không có hộp phát hiện → đúng một gợi ý ôm khung đó."""
    page = _page()
    _draw(page, _SOFA)
    (box,) = residual_ink_boxes(page, detections=(), texts=(), mm_per_px=_MM_PER_PX)
    assert all(abs(a - b) <= 4 for a, b in zip(box, _SOFA, strict=True))


def test_coloured_page_yields_none() -> None:
    """Sàn tô xám 200 (dưới 50 % điểm trắng) → không gợi ý dù có khung."""
    page = _page(fill=200)
    _draw(page, _SOFA)
    assert residual_ink_boxes(page, detections=(), texts=(), mm_per_px=_MM_PER_PX) == []


def test_overlap_with_detection_yields_none() -> None:
    """Hộp phát hiện nằm trong khung (IoU ≥ 0,3 với phần mực còn lại) → bỏ gợi ý."""
    page = _page()
    _draw(page, _SOFA)
    inner = (_SOFA[0] + 6, _SOFA[1] + 6, _SOFA[2] - 6, _SOFA[3] - 6)
    assert residual_ink_boxes(page, detections=[("chair", inner)], texts=(), mm_per_px=_MM_PER_PX) == []


def test_text_and_detections_are_masked() -> None:
    """Khung nằm dưới hộp chữ hay hộp phát hiện bị trừ khỏi mực; khung còn lại vẫn ra gợi ý."""
    page = _page()
    _draw(page, _SOFA)
    other = (500.0, 100.0, 600.0, 160.0)
    _draw(page, other)
    covered = (_SOFA[0] - 3, _SOFA[1] - 3, _SOFA[2] + 3, _SOFA[3] + 3)
    (box,) = residual_ink_boxes(page, detections=(), texts=[covered], mm_per_px=_MM_PER_PX)
    assert abs(box[0] - other[0]) <= 4


def test_door_swing_square_is_masked() -> None:
    """Cung mở cạnh hộp cửa (hình vuông bán kính = cạnh dài cửa) không thành gợi ý."""
    page = _page()
    door = (100.0, 45.0, 190.0, 55.0)
    cv2.ellipse(page.gray, (100, 55), (85, 85), 0, 0, 90, 0, 2)
    assert residual_ink_boxes(page, detections=[("door", door)], texts=(), mm_per_px=_MM_PER_PX) == []


def test_size_line_and_density_filters() -> None:
    """Nét quá nhỏ, quá dài, quá dẹt hay khối đặc đều bị bỏ."""
    page = _page()
    _draw(page, (100.0, 100.0, 115.0, 115.0))  # 0,15 m: nhỏ hơn 0,3 m
    cv2.line(page.gray, (100, 400), (500, 400), 0, 2)  # đường kích thước: dẹt
    cv2.rectangle(page.gray, (600, 300), (660, 360), 0, -1)  # khối đặc
    _draw(page, (400.0, 450.0, 480.0, 465.0))  # cạnh ngắn 0,15 m
    assert residual_ink_boxes(page, detections=(), texts=(), mm_per_px=_MM_PER_PX) == []


def test_cap_keeps_largest_ink() -> None:
    """20 khung → đúng `MAX_SUGGESTIONS`, khung nhiều mực trước."""
    page = _page()
    for i in range(20):
        x, y = 70 + (i % 5) * 135, 70 + (i // 5) * 115
        size = 35 + i * 2
        _draw(page, (float(x), float(y), float(x + size), float(y + 35)))
    boxes = residual_ink_boxes(page, detections=(), texts=(), mm_per_px=_MM_PER_PX)
    assert len(boxes) == MAX_SUGGESTIONS
    widths = [b[2] - b[0] for b in boxes]
    assert widths == sorted(widths, reverse=True)


def test_empty_interior_yields_none() -> None:
    """Không có tường khép căn hộ → không có điểm "trong căn hộ" → không gợi ý."""
    gray = np.full((_H, _W), 255, np.uint8)
    page = PageRaster(gray=gray, walls=np.zeros((_H, _W), np.bool_))
    _draw(page, _SOFA)
    assert residual_ink_boxes(page, detections=(), texts=(), mm_per_px=_MM_PER_PX) == []


def test_decode_page_raster_round_trip() -> None:
    """PNG trang RGB + `walls.png` → xám và mặt nạ đúng khổ."""
    page = _page()
    rgb = np.repeat(page.gray[:, :, None], 3, axis=2)
    raster = decode_page_raster(encode_rgb_png(rgb), encode_mask(page.walls), width_px=_W, height_px=_H)
    assert np.array_equal(raster.gray, page.gray)
    assert np.array_equal(raster.walls, page.walls)


def test_decode_page_raster_rejects_bad_input() -> None:
    """Khổ lệch hay PNG cụt sau IHDR → `ValueError`."""
    page = _page()
    png = encode_rgb_png(np.repeat(page.gray[:, :, None], 3, axis=2))
    mask = encode_mask(page.walls)
    with pytest.raises(ValueError, match="lệch khổ"):
        decode_page_raster(png, mask, width_px=_W + 1, height_px=_H)
    with pytest.raises(ValueError, match="không giải được"):
        decode_page_raster(png[:33] + png[-12:], mask, width_px=_W, height_px=_H)


def _wall(x0: float, y0: float, x1: float, y1: float) -> WallPx:
    """Tường px dày 10 cho test dựng lớp."""
    return WallPx(start=PointPx(x=x0, y=y0), end=PointPx(x=x1, y=y1), thickness_px=10.0, confidence=0.9)


_WALLS = (
    _wall(50, 50, 750, 50),
    _wall(750, 50, 750, 550),
    _wall(750, 550, 50, 550),
    _wall(50, 550, 50, 50),
)


def test_build_layer_adds_suggested_furniture() -> None:
    """`page` có khung không nhãn → lớp có một đồ `other` `suggested`, giữ qua `to_json`/`from_json`."""
    page = _page()
    _draw(page, _SOFA)
    clock = FakeClock(start=datetime(2026, 1, 1, tzinfo=UTC))
    built = build_wrapped(walls=_WALLS, width_px=_W, height_px=_H, clock=clock, page=page)
    (item,) = built.layer.furniture
    assert (item.kind, item.suggested, item.source, item.reviewed) == ("other", True, "ai", False)
    (again,) = BuiltLayer.from_json(built.to_json()).layer.furniture
    assert again.suggested


def test_suggestions_skip_without_usable_page() -> None:
    """Không trang, khổ lệch, hay tỉ lệ dự phòng mà không có tường để ước → không gợi ý."""
    page = _page()
    _draw(page, _SOFA)
    bad = PageRaster(gray=page.gray, walls=page.walls[:-1])
    assert _suggestions(None, _WALLS, (), (), _MM_PER_PX) == ()
    assert _suggestions(bad, _WALLS, (), (), _MM_PER_PX) == ()
    assert _suggestions(page, (), (), (), None) == ()
    (estimated,) = _suggestions(page, _WALLS, (), (), None)
    assert estimated.label == "other"
    chair = DetectionPx(
        label="chair", box=BoxPx(x_min=_SOFA[0], y_min=_SOFA[1], x_max=_SOFA[2], y_max=_SOFA[3]), confidence=0.9
    )
    assert _suggestions(page, _WALLS, (chair,), (), _MM_PER_PX) == ()
