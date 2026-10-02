"""Nhãn SVG → nhãn huấn luyện theo pixel: chọn ảnh, mặt nạ tường, hộp cửa/đồ, tỉ lệ mực (B6-02b [6]).

Luật toạ độ (phương án 1, đo 2026-10-02 trên 120 mẫu thật, xem docstring `svg.py`): toạ độ
`SvgLabels` là pixel `F1_scaled.png` 1:1. Khổ ảnh / khổ `viewBox` trải từ 0,98 tới 1,28 (trung
vị 1,05), nên luật "khổ SVG khớp khổ ảnh" của prompt bỏ 88 % mẫu thật và co giãn sai số còn
lại; `F1_original.png` không dùng.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Literal

import cv2
import numpy as np
from numpy.typing import NDArray

from apps.worker.datasets_cubicasa.svg import Polygon, SvgLabels
from packages.ml_contracts.artifacts import BoxPx, DetectionPx
from packages.ml_contracts.labels import ObjectLabel

ImageBranch = Literal["identity"]
"""Nhánh chọn ảnh in trong báo cáo; một nhánh duy nhất cho tới khi phép đo mới đòi thêm."""


@dataclass(frozen=True, slots=True)
class ImageChoice:
    """Ảnh đã chọn cho một mẫu và hệ số nhân toạ độ: `x_px = x * sx`, `y_px = y * sy`.

    `fit_x`, `fit_y` = khổ ảnh / khổ SVG: chỉ để báo cáo phân bố, chưa bỏ mẫu theo nó (ngưỡng
    đặt sau khi đo đủ dữ liệu thật, như `ink_ratio`).
    """

    filename: str
    sx: float
    sy: float
    branch: ImageBranch
    fit_x: float
    fit_y: float


FIXTURE_LABELS: Final[Mapping[str, ObjectLabel]] = MappingProxyType(
    {
        "Toilet": "sanitary_fixture",
        "Sink": "sanitary_fixture",
        "Bathtub": "sanitary_fixture",
        "Shower": "sanitary_fixture",
        "Closet": "wardrobe",
    }
)
"""Tên đồ (token thứ hai của `class="FixedFurniture <tên>"`) → nhãn huấn luyện; so đúng tên, không đoán thêm."""


def choose_image(svg_size: tuple[float, float], sizes: Mapping[str, tuple[int, int]]) -> ImageChoice | None:
    """Chọn `F1_scaled.png` nếu có (phương án 1); vắng → `None` (importer bỏ mẫu `no_image`)."""
    filename = "F1_scaled.png"
    if filename not in sizes:
        return None
    width_px, height_px = sizes[filename]
    svg_width, svg_height = svg_size
    fit_x, fit_y = width_px / svg_width, height_px / svg_height
    return ImageChoice(filename, sx=1.0, sy=1.0, branch="identity", fit_x=fit_x, fit_y=fit_y)


def _polygon_to_px(polygon: Polygon, choice: ImageChoice) -> NDArray[np.int32]:
    """Toạ độ pixel đã làm tròn của một đa giác (`x * sx`, `y * sy`), sẵn cho `cv2.fillPoly`."""
    points = np.asarray(polygon, dtype=np.float64) * (choice.sx, choice.sy)
    return np.round(points).astype(np.int32)


def wall_mask_from_polygons(
    labels: SvgLabels, choice: ImageChoice, *, width_px: int, height_px: int
) -> NDArray[np.bool_]:
    """Mặt nạ tường: tô mọi đa giác tường rồi khoét khe mọi đa giác cửa (bool, `height_px x width_px`).

    Một lệnh `fillPoly` **mỗi** đa giác (vòng theo đa giác, ≤ 20 000 tường/mẫu — K28 vẫn giữ, không
    vòng theo điểm ảnh): `fillPoly` nhiều đường viền trong **một** lệnh tô theo luật chẵn-lẻ toàn cục,
    nên góc hai tường chạm/chồng nhau (như chữ T của CubiCasa thật) bị tính hai lần và huỷ thành lỗ
    — đo được trong container (góc `(24, 19)` của tường trên + tường trái = 0 khi tô một lệnh, = 1 khi
    tô từng đa giác). Không tường → mặt nạ rỗng toàn `False` (importer bỏ mẫu `no_labels`).
    """
    mask = np.zeros((height_px, width_px), dtype=np.uint8)
    for wall in labels.walls:
        cv2.fillPoly(mask, [_polygon_to_px(wall, choice)], 1)
    for door in labels.doors:
        cv2.fillPoly(mask, [_polygon_to_px(door, choice)], 0)
    return mask.astype(bool)


def _box_from_polygon(polygon: Polygon, choice: ImageChoice, *, width_px: int, height_px: int) -> BoxPx | None:
    """Hộp bao min/max của một đa giác, kẹp vào khổ ảnh; suy biến sau khi kẹp → `None`."""
    points = _polygon_to_px(polygon, choice)
    x_min = float(np.clip(points[:, 0].min(), 0, width_px))
    x_max = float(np.clip(points[:, 0].max(), 0, width_px))
    y_min = float(np.clip(points[:, 1].min(), 0, height_px))
    y_max = float(np.clip(points[:, 1].max(), 0, height_px))
    if x_max <= x_min or y_max <= y_min:
        return None
    return BoxPx(x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max)


def boxes_from_labels(
    labels: SvgLabels, choice: ImageChoice, *, width_px: int, height_px: int
) -> tuple[tuple[DetectionPx, ...], dict[str, int]]:
    """Hộp cửa, cửa sổ, đồ đạc theo thứ tự SVG; tên đồ lạ đếm vào dict thứ hai, không tạo hộp."""
    detections: list[DetectionPx] = []
    unknown: dict[str, int] = {}
    for door in labels.doors:
        box = _box_from_polygon(door, choice, width_px=width_px, height_px=height_px)
        if box is not None:
            detections.append(DetectionPx(label="door", box=box, confidence=1.0))
    for window in labels.windows:
        box = _box_from_polygon(window, choice, width_px=width_px, height_px=height_px)
        if box is not None:
            detections.append(DetectionPx(label="window", box=box, confidence=1.0))
    for name, polygon in labels.fixtures:
        label = FIXTURE_LABELS.get(name)
        if label is None:
            unknown[name] = unknown.get(name, 0) + 1
            continue
        box = _box_from_polygon(polygon, choice, width_px=width_px, height_px=height_px)
        if box is not None:
            detections.append(DetectionPx(label=label, box=box, confidence=1.0))
    return tuple(detections), unknown


def ink_ratio(mask: NDArray[np.bool_], pixels: NDArray[np.uint8]) -> float | None:
    """Tỉ lệ pixel tối (mực) trong mặt nạ tường; mặt nạ rỗng → `None`; khổ lệch → `ValueError`."""
    if not mask.any():
        return None
    if mask.shape != pixels.shape[:2]:
        raise ValueError(f"khổ mặt nạ {mask.shape} khác khổ ảnh {pixels.shape[:2]}")
    gray = cv2.cvtColor(pixels, cv2.COLOR_RGB2GRAY)
    return float((mask & (gray < 128)).sum() / mask.sum())
