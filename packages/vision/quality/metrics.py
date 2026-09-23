"""Bốn số đo chất lượng trên bản làm việc: độ tương phản, nhiễu, vùng tệ nhất lưới 4x4.

`RESOLUTION` và `SKEW` không có hàm số đo riêng ở đây: độ phân giải là kích thước ảnh
gốc (việc gộp tự đọc), độ nghiêng là `geometry.estimate_skew`. Mọi hàm ở đây nhận
`gray` = `WorkingImage.gray` (BT.601, cạnh dài <= 2.000 px) để số đo ổn định qua các
kích thước ảnh gốc khác nhau.
"""

import math
from dataclasses import dataclass
from typing import Final

import cv2
import numpy as np
from numpy.typing import NDArray

from packages.vision.preprocess.geometry import js_round

_INK_PAPER_MIN_RATIO: Final = 0.005
_WALL_REFERENCE_SHORT_EDGE_PX: Final = 540
_REGION_TOLERANCE: Final = 1e-9
_GRID_SIZE: Final = 4


@dataclass(frozen=True, slots=True)
class Region:
    """Vùng chữ nhật theo tỉ lệ `[0, 1]` của khung ảnh (`quality.ts:84-97`).

    `x_ratio + width_ratio` và `y_ratio + height_ratio` phải `<= 1` (dung sai số thực
    `1e-9` cho sai số chia lưới); dải hoặc tổng sai → `ValueError` (lỗi lập trình).
    """

    x_ratio: float
    y_ratio: float
    width_ratio: float
    height_ratio: float

    def __post_init__(self) -> None:
        """Chốt bốn tỉ lệ trong `[0, 1]` và không tràn cạnh phải/dưới; sai → `ValueError` vì
        vùng sai dải là lỗi lập trình, và vùng tràn sẽ vẽ ra ngoài ảnh ở FE."""
        for value in (self.x_ratio, self.y_ratio, self.width_ratio, self.height_ratio):
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"Region cần mọi tỉ lệ trong [0, 1], nhận {value!r}")
        if self.x_ratio + self.width_ratio > 1.0 + _REGION_TOLERANCE:
            raise ValueError(f"Region tràn cạnh phải: x_ratio={self.x_ratio}, width_ratio={self.width_ratio}")
        if self.y_ratio + self.height_ratio > 1.0 + _REGION_TOLERANCE:
            raise ValueError(f"Region tràn cạnh dưới: y_ratio={self.y_ratio}, height_ratio={self.height_ratio}")


WHOLE_IMAGE: Final = Region(0.0, 0.0, 1.0, 1.0)


@dataclass(frozen=True, slots=True)
class Measurement:
    """Bốn số đo thô của một tầng, chưa phân loại — gương `quality.ts:115-130`.

    Bản ghi thuần; việc gộp của phần khác điền và phân loại bằng `thresholds`.
    """

    width_px: int
    height_px: int
    skew_deg: float
    contrast_score: float
    noise_score: float


def ink_mask(gray: NDArray[np.uint8]) -> NDArray[np.bool_]:
    """Tách mực (tối, `True`) khỏi giấy (sáng, `False`) bằng ngưỡng Otsu.

    Dùng chung cho `contrast_score` và `noise_score` để cả hai đồng nhất về "cái gì
    là mực" trên cùng một ảnh.
    """
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    return np.asarray(binary, dtype=np.uint8) > 0


def _contrast_from_mask(gray: NDArray[np.uint8], mask: NDArray[np.bool_]) -> float:
    """`(trung vị giấy - trung vị mực) / 255`, kẹp về `[0, 1]`; giả định đã đủ mực và giấy."""
    paper_median = float(np.median(gray[~mask]))
    ink_median = float(np.median(gray[mask]))
    score = (paper_median - ink_median) / 255.0
    return max(0.0, min(1.0, score))


def _has_enough_ink_and_paper(mask: NDArray[np.bool_]) -> bool:
    """Mực và giấy đều chiếm `>= 0,5 %` diện tích (không phải trang trắng hay đen).

    `mask` không rỗng: `gray` luôn có kích thước dương (`RgbImage.__post_init__`) và
    `_grid_cells` chỉ sinh ô đã lọc rỗng.
    """
    ink_ratio = float(mask.mean())
    return ink_ratio >= _INK_PAPER_MIN_RATIO and (1.0 - ink_ratio) >= _INK_PAPER_MIN_RATIO


def contrast_score(gray: NDArray[np.uint8]) -> float:
    """Độ tương phản `[0, 1]`, chưa làm tròn; trang trắng hoặc đen toàn phần → `0.0`."""
    mask = ink_mask(gray)
    if not _has_enough_ink_and_paper(mask):
        return 0.0
    return _contrast_from_mask(gray, mask)


def _small_blob_area_threshold(short_edge_px: int) -> int:
    """Diện tích đốm nhỏ tối đa: nửa bề dày tường 110 mm ở A3 1:100 (`thresholds.ts:12-23`)."""
    return max(1, js_round((short_edge_px / _WALL_REFERENCE_SHORT_EDGE_PX) ** 2))


def noise_score(gray: NDArray[np.uint8]) -> float:
    """Tỉ lệ thành phần liên thông 8 hướng của mực có diện tích <= ngưỡng đốm nhỏ."""
    mask_u8 = np.asarray(ink_mask(gray), dtype=np.uint8)
    num_labels, _labels, raw_stats, _centroids = cv2.connectedComponentsWithStats(mask_u8, connectivity=8)
    components = int(num_labels) - 1
    if components <= 0:
        return 0.0
    short_edge = min(gray.shape[0], gray.shape[1])
    threshold = _small_blob_area_threshold(short_edge)
    stats = np.asarray(raw_stats, dtype=np.int32)
    small = int((stats[1:, cv2.CC_STAT_AREA] <= threshold).sum())
    return small / components


def round_score(x: float) -> float:
    """3 chữ số, tròn nửa lên kiểu JS (`js_round(x·1000)/1000`) để khớp `Math.round` của FE."""
    return js_round(x * 1000) / 1000


def round_skew(x: float) -> float:
    """2 chữ số, cùng luật tròn với `round_score` (`js_round(x·100)/100`)."""
    return js_round(x * 100) / 100


def _grid_cells(height: int, width: int) -> list[tuple[Region, slice, slice]]:
    """Lưới 4x4 bằng biên nguyên (`np.array_split`), ô sát mép nhận phần dư (R-07).

    Dùng chung cho `lowest_contrast_region` và `densest_noise_region`; trả `(Region,
    lát hàng, lát cột)` theo pixel của `gray`.
    """
    row_edges = np.array_split(np.arange(height), _GRID_SIZE)
    col_edges = np.array_split(np.arange(width), _GRID_SIZE)
    cells: list[tuple[Region, slice, slice]] = []
    for rows in row_edges:
        if rows.size == 0:
            continue
        row_slice = slice(int(rows[0]), int(rows[-1]) + 1)
        for cols in col_edges:
            if cols.size == 0:
                continue
            col_slice = slice(int(cols[0]), int(cols[-1]) + 1)
            region = Region(
                x_ratio=col_slice.start / width,
                y_ratio=row_slice.start / height,
                width_ratio=(col_slice.stop - col_slice.start) / width,
                height_ratio=(row_slice.stop - row_slice.start) / height,
            )
            cells.append((region, row_slice, col_slice))
    return cells


def lowest_contrast_region(gray: NDArray[np.uint8]) -> Region:
    """Ô tệ nhất của lưới 4x4 trong số ô có đủ mực và giấy; không ô nào đủ → cả ảnh."""
    mask = ink_mask(gray)
    height, width = gray.shape[0], gray.shape[1]
    best_region: Region | None = None
    best_score = math.inf
    for region, row_slice, col_slice in _grid_cells(height, width):
        cell_mask = mask[row_slice, col_slice]
        if not _has_enough_ink_and_paper(cell_mask):
            continue
        score = _contrast_from_mask(gray[row_slice, col_slice], cell_mask)
        if score < best_score:
            best_score = score
            best_region = region
    return best_region if best_region is not None else WHOLE_IMAGE


def densest_noise_region(gray: NDArray[np.uint8]) -> Region:
    """Ô mật độ đốm nhỏ cao nhất của lưới 4x4 (đốm/diện tích ô); không đốm nào → cả ảnh."""
    mask_u8 = np.asarray(ink_mask(gray), dtype=np.uint8)
    height, width = gray.shape[0], gray.shape[1]
    num_labels, _labels, raw_stats, raw_centroids = cv2.connectedComponentsWithStats(mask_u8, connectivity=8)
    if int(num_labels) <= 1:
        return WHOLE_IMAGE
    stats = np.asarray(raw_stats, dtype=np.int32)
    centroids = np.asarray(raw_centroids, dtype=np.float64)
    threshold = _small_blob_area_threshold(min(height, width))
    small_mask = stats[1:, cv2.CC_STAT_AREA] <= threshold
    if not small_mask.any():
        return WHOLE_IMAGE
    small_centroids = centroids[1:][small_mask]
    centroid_x, centroid_y = small_centroids[:, 0], small_centroids[:, 1]

    best_region: Region | None = None
    best_density = -1.0
    for region, row_slice, col_slice in _grid_cells(height, width):
        in_cell = (
            (centroid_x >= col_slice.start)
            & (centroid_x < col_slice.stop)
            & (centroid_y >= row_slice.start)
            & (centroid_y < row_slice.stop)
        )
        count = int(in_cell.sum())
        cell_area = (row_slice.stop - row_slice.start) * (col_slice.stop - col_slice.start)
        density = count / cell_area
        if density > best_density:
            best_density = density
            best_region = region
    return best_region if best_region is not None else WHOLE_IMAGE
