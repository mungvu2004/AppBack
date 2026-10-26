"""Phân loại loại bản vẽ của một vùng bằng luật (thiết kế Phase 1 H4), không train.

Ba tín hiệu: T1 tỉ lệ điểm ảnh bão hoà (ảnh render/ảnh chụp), T2 chữ tiêu đề ven vùng (OCR do
bên gọi cấp, `None` = không có OCR), T3 hình học nét (đường đất ngang dài ở 1/3 dưới, ít nét dọc
dài). Thiếu bằng chứng ⇒ `unknown` (Q5 = A). `reasons` là câu tiếng Việt FE hiển thị nguyên văn.
"""

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

import cv2
import numpy as np
from numpy.typing import NDArray

from packages.vision.layout import Box
from packages.vision.preprocess.types import RgbImage

# Cùng Literal với `packages/db/models/documents.py`; định nghĩa lại vì vision không được nhập db (.importlinter).
type DrawingType = Literal["floorPlan", "section", "elevation", "detail", "other", "unknown"]

SATURATION_MIN: Final = 0.25  # điểm ảnh "màu" khi độ bão hoà HSV > 0,25
SATURATED_RATIO_OTHER: Final = 0.15  # > 15 % điểm ảnh màu ⇒ giống ảnh render
TITLE_BAND_RATIO: Final = 0.15  # dải chữ tiêu đề: 15 % chiều cao vùng ngay trên/dưới hộp
GROUND_LINE_RATIO: Final = 0.7  # đường đất: nét ngang dài > 70 % bề rộng vùng ở 1/3 dưới
LONG_LINE_RATIO: Final = 0.25  # nét "dài": ≥ 25 % cạnh vùng theo chiều của nét
FEW_VERTICAL_RATIO: Final = 0.35  # nét dọc dài < 35 % tổng nét dài ⇒ "ít nét dọc"
TITLE_BLOCK_AREA_RATIO: Final = 0.08  # vùng < 8 % trang …
DENSE_TEXT_RATIO: Final = 0.2  # … và chữ phủ > 20 % vùng ⇒ khung tên (`other`)

_KEYWORDS: Final[tuple[tuple[re.Pattern[str], DrawingType], ...]] = (
    (re.compile(r"\b(MAT BANG|MB)\b"), "floorPlan"),
    (re.compile(r"\b(MAT CAT|MC)\b"), "section"),
    (re.compile(r"\b(MAT DUNG|MD)\b"), "elevation"),
    (re.compile(r"\b(CHI TIET|CT)\b"), "detail"),
)
_LABELS: Final[dict[DrawingType, str]] = {
    "floorPlan": "mặt bằng",
    "section": "mặt cắt",
    "elevation": "mặt đứng",
    "detail": "chi tiết",
}


@dataclass(frozen=True, slots=True)
class TitleText:
    """Một chuỗi OCR và hộp của nó theo tỉ lệ trên TRANG (không phải trên vùng)."""

    text: str
    box: Box


@dataclass(frozen=True, slots=True)
class RegionSignals:
    """Tín hiệu đo được của một vùng; đầu vào duy nhất của `classify_region`."""

    saturated_ratio: float
    titles: tuple[str, ...] | None
    ground_line: bool
    long_vertical_ratio: float
    area_ratio: float
    text_density: float


@dataclass(frozen=True, slots=True)
class Classification:
    """Loại bản vẽ và các câu lý do tiếng Việt (lưu `type_signals`)."""

    drawing_type: DrawingType
    reasons: tuple[str, ...]


def measure_signals(page: RgbImage, box: Box, titles: Sequence[TitleText] | None) -> RegionSignals:
    """Đo T1/T2/T3 của vùng `box` trên `page`; `titles` là OCR cả trang (`None` = không có OCR)."""
    h, w = page.pixels.shape[:2]
    x0, y0 = int(box.x0 * w), int(box.y0 * h)
    x1, y1 = max(x0 + 1, int(box.x1 * w)), max(y0 + 1, int(box.y1 * h))
    region = page.pixels[y0:y1, x0:x1]
    saturation = cv2.cvtColor(region, cv2.COLOR_RGB2HSV)[:, :, 1]
    gray = cv2.cvtColor(region, cv2.COLOR_RGB2GRAY)
    ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1].astype(np.uint8, copy=False)
    rh, rw = ink.shape
    ground = _long_lines(ink, (1, max(1, int(GROUND_LINE_RATIO * rw))))
    horiz = _long_lines(ink, (1, max(1, int(LONG_LINE_RATIO * rw))))
    vert = _long_lines(ink, (max(1, int(LONG_LINE_RATIO * rh)), 1))
    long_total = int(np.count_nonzero(horiz)) + int(np.count_nonzero(vert))
    region_area = (box.x1 - box.x0) * (box.y1 - box.y0)
    return RegionSignals(
        saturated_ratio=float(np.mean(saturation > SATURATION_MIN * 255)),
        titles=None if titles is None else tuple(t.text for t in titles if _in_title_band(t.box, box)),
        ground_line=bool(np.any(ground[rh - rh // 3 :])),
        long_vertical_ratio=int(np.count_nonzero(vert)) / long_total if long_total else 0.0,
        area_ratio=region_area,
        text_density=0.0 if titles is None else min(1.0, sum(_overlap(t.box, box) for t in titles) / region_area),
    )


def classify_region(signals: RegionSignals) -> Classification:
    """Áp luật kết hợp H4: T1 ⇒ `other`; khung tên ⇒ `other`; một từ khoá T2 không mâu thuẫn T3 ⇒ loại theo
    từ khoá; còn lại (không chữ, nhiều loại từ khoá, mâu thuẫn hình học) ⇒ `unknown`."""
    if signals.saturated_ratio > SATURATED_RATIO_OTHER:
        pct = round(signals.saturated_ratio * 100)
        return Classification("other", (f"{pct} % điểm ảnh có màu đậm, giống ảnh render hoặc ảnh chụp",))
    if signals.area_ratio < TITLE_BLOCK_AREA_RATIO and signals.text_density > DENSE_TEXT_RATIO:
        return Classification("other", ("Vùng nhỏ, chữ dày đặc, giống khung tên",))
    hits = {(kind, text) for text in signals.titles or () for kind in _keyword_kinds(text)}
    kinds = {kind for kind, _ in hits}
    if not kinds:
        return Classification("unknown", ("Không thấy chữ tiêu đề cho biết loại bản vẽ",))
    reasons = tuple(f"Chữ '{text}' ven vùng gợi ý {_LABELS[kind]}" for kind, text in sorted(hits))
    if len(kinds) > 1:
        return Classification("unknown", (*reasons, "Chữ tiêu đề gợi ý nhiều loại khác nhau"))
    (kind,) = kinds
    if kind == "floorPlan" and signals.ground_line and signals.long_vertical_ratio < FEW_VERTICAL_RATIO:
        return Classification("unknown", (*reasons, "Nét vẽ có đường đất và ít nét dọc, giống mặt cắt/mặt đứng"))
    return Classification(kind, reasons)


def _normalize_text(text: str) -> str:
    """NFC → bỏ dấu (NFD, bỏ ký tự Mn, "Đ"→"D") → hoa, gộp khoảng trắng; dùng để so từ khoá."""
    decomposed = unicodedata.normalize("NFD", unicodedata.normalize("NFC", text))
    plain = "".join(c for c in decomposed if unicodedata.category(c) != "Mn").replace("Đ", "D").replace("đ", "d")
    return " ".join(plain.upper().split())


def _keyword_kinds(text: str) -> set[DrawingType]:
    """Các loại có từ khoá khớp nguyên từ trong `text` đã chuẩn hoá."""
    norm = _normalize_text(text)
    return {kind for pattern, kind in _KEYWORDS if pattern.search(norm)}


def _long_lines(ink: NDArray[np.uint8], shape: tuple[int, int]) -> NDArray[np.uint8]:
    """Mặt nạ nét dài theo nhân `shape` (mở hình thái, ngoài ảnh là giấy trắng)."""
    kernel = np.ones(shape, np.uint8)
    opened = cv2.morphologyEx(ink, cv2.MORPH_OPEN, kernel, borderType=cv2.BORDER_CONSTANT, borderValue=0)
    return opened.astype(np.uint8, copy=False)


def _in_title_band(text_box: Box, region: Box) -> bool:
    """Tâm chữ nằm trong dải `TITLE_BAND_RATIO` chiều cao vùng ngay trên hoặc dưới vùng, cùng khoảng ngang."""
    cx, cy = (text_box.x0 + text_box.x1) / 2, (text_box.y0 + text_box.y1) / 2
    band = TITLE_BAND_RATIO * (region.y1 - region.y0)
    in_x = region.x0 <= cx <= region.x1
    return in_x and (region.y0 - band <= cy < region.y0 or region.y1 < cy <= region.y1 + band)


def _overlap(a: Box, b: Box) -> float:
    """Diện tích giao (tỉ lệ trang) của hai hộp."""
    return max(0.0, min(a.x1, b.x1) - max(a.x0, b.x0)) * max(0.0, min(a.y1, b.y1) - max(a.y0, b.y0))
