"""Vẽ mặt nạ tường và hộp ô mở/đồ đạc từ `SpatialLayer` sang không gian pixel (thuần numpy + cv2, K19).

**Ô mở mồ côi bị bỏ, không làm chết lượt dựng** (NO-274): `opening.wall_id` trỏ một tường không có
trong `walls` là dữ liệu nguồn không nhất quán — có thể vì tầng bị sửa giữa hai lượt đọc, hoặc vì
người gọi truyền một tập `walls` đã lọc. Bỏ đúng ô đó rồi vẽ tiếp cho ra một mẫu thiếu một ô mở;
`KeyError` sẽ làm hỏng cả một lượt dựng 2.000 tầng vì một tầng lẻ.

Không I/O: `mm_per_px` do người gọi tra sẵn từ `floor_documents`, không có mặc định ở đây
(K19 — tầng không có tỉ lệ bị bỏ ở tầng gọi, không mặc định 1 mm/px). Cùng quy ước hệ toạ độ
với `packages.ml_contracts.synthetic.render_plan`: gốc mm trùng góc trên-trái trang đã nắn, y
hướng xuống, mỗi đầu tường kéo dài nửa bề dày dọc đường tim (HOP-DONG-MOI §4.2).
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import cv2
import numpy as np
from numpy.typing import NDArray

from packages.domain.spatial.model import Furniture, Opening, SpatialLayer, Wall
from packages.ml_contracts.artifacts import BoxPx, DetectionPx
from packages.ml_contracts.labels import DetectionLabel

_FURNITURE_LABELS: dict[str, DetectionLabel] = {
    "table": "table",
    "chair": "chair",
    "bed": "bed",
    "wardrobe": "wardrobe",
    "kitchenCabinet": "kitchen_cabinet",
    "sanitaryFixture": "sanitary_fixture",
    "stair": "stair",
}
"""`other` cố ý vắng: không có nhãn huấn luyện (prompt khối [6])."""


def _segment_corners_px(
    start_x_mm: float,
    start_y_mm: float,
    end_x_mm: float,
    end_y_mm: float,
    thickness_mm: float,
    mm_per_px: float,
    *,
    extend_ends: bool,
    raster: bool = False,
) -> NDArray[np.float64]:
    """4 góc (px) của dải quanh đoạn `start→end` (mm), bề dày `thickness_mm`.

    `extend_ends`: kéo dài mỗi đầu nửa bề dày dọc hướng đoạn (thân tường) hay giữ nguyên
    (khe ô mở). Hoạt động cho đoạn xiên bất kỳ, không giả định trục (K19-kề, "tường chéo").

    `raster=True` (dùng cho `_fill_polygon`): lùi mép "xa" (cuối đoạn, phía `+n`) vào trong 1 px
    trước khi làm tròn — `cv2.fillPoly` tô cả hai mép (bao đóng), nếu không sẽ dư một hàng/cột so
    với quy ước nửa-mở của `PointPx` ("mép điểm ảnh"). Hộp trả cho `object_boxes` không cần bù
    (không rasterize), nên giữ toạ độ hình học thật.
    """
    sx_px, sy_px = start_x_mm / mm_per_px, start_y_mm / mm_per_px
    ex_px, ey_px = end_x_mm / mm_per_px, end_y_mm / mm_per_px
    length_px = math.hypot(ex_px - sx_px, ey_px - sy_px)
    ux, uy = (ex_px - sx_px) / length_px, (ey_px - sy_px) / length_px
    nx, ny = -uy, ux
    half_thickness_px = thickness_mm / mm_per_px / 2
    extend_px = half_thickness_px if extend_ends else 0.0
    shrink = 1.0 if raster else 0.0
    u0, u1 = -extend_px, length_px + extend_px - shrink
    n0, n1 = -half_thickness_px, half_thickness_px - shrink
    corners = (
        (sx_px + ux * u0 + nx * n0, sy_px + uy * u0 + ny * n0),
        (sx_px + ux * u1 + nx * n0, sy_px + uy * u1 + ny * n0),
        (sx_px + ux * u1 + nx * n1, sy_px + uy * u1 + ny * n1),
        (sx_px + ux * u0 + nx * n1, sy_px + uy * u0 + ny * n1),
    )
    return np.array(corners, dtype=np.float64)


def _fill_polygon(canvas: NDArray[np.uint8], corners_px: NDArray[np.float64], value: int) -> None:
    """`cv2.fillPoly` cắt tự nhiên theo khung `canvas`; góc đã làm tròn nửa lên trước khi tô."""
    points = np.round(corners_px).astype(np.int32)
    cv2.fillPoly(canvas, [points], value)


def _wall_span_corners_px(
    wall: Wall, offset_mm: float, width_mm: float, mm_per_px: float, *, raster: bool = False
) -> NDArray[np.float64]:
    """4 góc (px) của một đoạn `[offset, offset + width]` dọc `u` của `wall`, rộng bề dày tường."""
    start, end = wall.centreline.start, wall.centreline.end
    length_mm = math.hypot(end.x - start.x, end.y - start.y)
    ux, uy = (end.x - start.x) / length_mm, (end.y - start.y) / length_mm
    span_start = (start.x + ux * offset_mm, start.y + uy * offset_mm)
    span_end = (start.x + ux * (offset_mm + width_mm), start.y + uy * (offset_mm + width_mm))
    return _segment_corners_px(*span_start, *span_end, wall.thickness_mm, mm_per_px, extend_ends=False, raster=raster)


def wall_mask(
    walls: Sequence[Wall],
    *,
    width_px: int,
    height_px: int,
    mm_per_px: float,
    openings: Sequence[Opening] = (),
) -> NDArray[np.bool_]:
    """Mặt nạ tường (H, W): dải quanh đường tim mỗi tường, trừ khe của ô mở `door`.

    Lệch khỏi chữ ký prompt khối [2] (`wall_mask(walls, *, width_px, height_px, mm_per_px)`):
    thêm `openings` từ khoá, mặc định rỗng — không có cách nào khoét khe cửa mà không biết ô
    mở của tường (prompt khối [6] "rồi xoá hình chữ nhật của ô mở door"). Cửa sổ không đổi mặt
    nạ (chỉ đổi ảnh nền, việc của `render_plan`/pipeline suy luận, không phải nhãn huấn luyện).
    """
    canvas = np.zeros((height_px, width_px), dtype=np.uint8)
    for wall in walls:
        start, end = wall.centreline.start, wall.centreline.end
        corners = _segment_corners_px(
            start.x, start.y, end.x, end.y, wall.thickness_mm, mm_per_px, extend_ends=True, raster=True
        )
        _fill_polygon(canvas, corners, 1)
    walls_by_id = {wall.id: wall for wall in walls}
    for opening in openings:
        if opening.kind != "door":
            continue
        # Tên khác `wall`: biến đó đã bị vòng vẽ tường ở trên ràng kiểu `Wall`, còn `.get` trả `Wall | None`.
        host = walls_by_id.get(opening.wall_id)
        if host is None:
            continue
        corners = _wall_span_corners_px(host, opening.offset_mm, opening.width_mm, mm_per_px, raster=True)
        _fill_polygon(canvas, corners, 0)
    return canvas.astype(np.bool_)


def _clip_box(x_min: float, y_min: float, x_max: float, y_max: float, width_px: int, height_px: int) -> BoxPx | None:
    """Kẹp hộp vào khung ảnh; hộp rỗng sau kẹp (tràn hẳn ra ngoài) → `None`."""
    x_min, x_max = max(0.0, x_min), min(float(width_px), x_max)
    y_min, y_max = max(0.0, y_min), min(float(height_px), y_max)
    if x_min >= x_max or y_min >= y_max:
        return None
    return BoxPx(x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max)


def _bounding_box(corners_px: NDArray[np.float64]) -> tuple[float, float, float, float]:
    """Hộp trục thẳng bao 4 góc của một đoạn xiên (đáp ứng "hộp trục thẳng" dù tường chéo)."""
    return (
        float(corners_px[:, 0].min()),
        float(corners_px[:, 1].min()),
        float(corners_px[:, 0].max()),
        float(corners_px[:, 1].max()),
    )


def _opening_label(opening: Opening) -> DetectionLabel:
    """`door`/`double_door` theo `swing`, hay `window`."""
    if opening.kind == "window":
        return "window"
    return "double_door" if opening.swing == "double" else "door"


def object_boxes(layer: SpatialLayer, *, width_px: int, height_px: int, mm_per_px: float) -> tuple[DetectionPx, ...]:
    """Hộp px của ô mở (`door`/`double_door`/`window`) và đồ đạc có nhãn huấn luyện (`other` bỏ)."""
    walls_by_id = {wall.id: wall for wall in layer.walls}
    detections: list[DetectionPx] = []
    for opening in layer.openings:
        wall = walls_by_id.get(opening.wall_id)
        if wall is None:
            continue
        corners = _wall_span_corners_px(wall, opening.offset_mm, opening.width_mm, mm_per_px)
        box = _clip_box(*_bounding_box(corners), width_px, height_px)
        if box is not None:
            detections.append(DetectionPx(label=_opening_label(opening), box=box, confidence=1.0))
    for furniture in layer.furniture:
        label = _FURNITURE_LABELS.get(furniture.kind)
        if label is None:
            continue
        box = _clip_box(*_furniture_bounds_px(furniture, mm_per_px), width_px, height_px)
        if box is not None:
            detections.append(DetectionPx(label=label, box=box, confidence=1.0))
    return tuple(detections)


def _furniture_bounds_px(furniture: Furniture, mm_per_px: float) -> tuple[float, float, float, float]:
    """`boundingBox` của đồ đạc, đổi mm → px (thẳng theo mép, không xoay theo `rotationDeg`)."""
    box = furniture.bounding_box
    return (box.min.x / mm_per_px, box.min.y / mm_per_px, box.max.x / mm_per_px, box.max.y / mm_per_px)
