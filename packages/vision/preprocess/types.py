"""Kiểu dữ liệu bất biến của gói ảnh: ảnh RGB, tứ giác góc, homography.

"Pixel" của cả hệ thống là pixel của trang đã nắn do gói này sinh
(HOP-DONG-MOI §4.2); homography nối pixel nguồn với pixel đó.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Self, cast

import numpy as np
from numpy.typing import NDArray

from packages.vision.preprocess.errors import VisionError

DEFAULT_MAX_PIXELS: Final = 40_000_000
DEFAULT_DPI: Final = 200

Point = tuple[float, float]
Row3 = tuple[float, float, float]
Matrix3 = tuple[Row3, Row3, Row3]
_SIZE_KEYS: Final = ("sourceWidthPx", "sourceHeightPx", "widthPx", "heightPx")


@dataclass(frozen=True, slots=True)
class RgbImage:
    """Ảnh RGB 8-bit `(H, W, 3)`, C-contiguous, chỉ đọc.

    Giữ một view chỉ đọc (chép khi mảng vào không liền bộ nhớ), nên người giữ
    `RgbImage` không sửa được điểm ảnh đã qua kiểm. Sai hình, sai dtype hoặc ảnh
    rỗng → `ValueError` (lỗi lập trình, không phải dữ liệu vào).
    """

    pixels: NDArray[np.uint8]

    def __post_init__(self) -> None:
        """Chốt bất biến `uint8 (H, W, 3)` không rỗng rồi khoá view chỉ đọc; sai hình hay sai
        dtype → `ValueError` vì đó là lỗi lập trình của bên gọi, không phải dữ liệu vào."""
        pixels = self.pixels
        if pixels.dtype != np.uint8 or pixels.ndim != 3 or pixels.shape[2] != 3:
            raise ValueError(f"RgbImage cần uint8 (H, W, 3), nhận {pixels.dtype} {pixels.shape}")
        if pixels.shape[0] == 0 or pixels.shape[1] == 0:
            raise ValueError("RgbImage không được rỗng")
        view = np.ascontiguousarray(pixels).view()
        view.flags.writeable = False
        object.__setattr__(self, "pixels", view)

    @property
    def width_px(self) -> int:
        """Số cột điểm ảnh."""
        return int(self.pixels.shape[1])

    @property
    def height_px(self) -> int:
        """Số hàng điểm ảnh."""
        return int(self.pixels.shape[0])


@dataclass(frozen=True, slots=True)
class Quad:
    """Bốn góc `(x, y)` pixel, chiều kim đồng hồ từ trên-trái (`quality.ts:139-159`).

    Chỉ kiểm hình dạng (đúng 4 điểm hữu hạn) → `VisionError("VALIDATION", field="corners")`;
    luật hình học (lồi, trong ảnh, thứ tự) ở `geometry.validate_quad` vì cần kích thước ảnh.
    """

    points: tuple[Point, Point, Point, Point]

    def __post_init__(self) -> None:
        """Chốt đúng 4 điểm số hữu hạn rồi ép về `float`; sai hình →
        `VisionError("VALIDATION", field="corners")` vì góc là thứ người dùng gửi lên."""
        points = self.points
        if len(points) != 4 or not all(len(p) == 2 and all(_is_number(v) for v in p) for p in points):
            raise VisionError("VALIDATION", field="corners")
        object.__setattr__(self, "points", tuple((float(x), float(y)) for x, y in points))


def _is_number(value: object) -> bool:
    """Số hữu hạn (int/float, không bool)."""
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def _positive_int(value: object) -> bool:
    """Số nguyên dương (không bool)."""
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


@dataclass(frozen=True, slots=True)
class Homography:
    """Ma trận 3x3 ánh xạ pixel nguồn → pixel đích, kèm kích thước hai phía.

    Kích thước đi kèm để `compose` bắt được việc nối hai phép không khớp nhau.
    Ma trận có phần tử không hữu hạn hoặc kích thước không nguyên dương →
    `VisionError("VALIDATION")`.
    """

    matrix: Matrix3
    source_width_px: int
    source_height_px: int
    width_px: int
    height_px: int

    def __post_init__(self) -> None:
        """Chốt ma trận 3x3 toàn số hữu hạn và bốn kích thước nguyên dương, rồi ép về `float`;
        sai → `VisionError("VALIDATION")` để phép nối tầng sau không chạy trên rác."""
        rows = self.matrix
        if len(rows) != 3 or not all(len(r) == 3 and all(_is_number(v) for v in r) for r in rows):
            raise VisionError("VALIDATION")
        sizes = (self.source_width_px, self.source_height_px, self.width_px, self.height_px)
        if not all(_positive_int(v) for v in sizes):
            raise VisionError("VALIDATION")
        object.__setattr__(self, "matrix", tuple(tuple(float(v) for v in r) for r in rows))

    @classmethod
    def identity(cls, width_px: int, height_px: int) -> Self:
        """Phép đơn vị cho ảnh không đổi hình (nguồn, đích cùng kích thước)."""
        return cls(((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)), width_px, height_px, width_px, height_px)

    @classmethod
    def from_array(cls, matrix: NDArray[np.float64], source: tuple[int, int], target: tuple[int, int]) -> Self:
        """Dựng từ mảng numpy 3x3; `source`, `target` là `(rộng, cao)`."""
        if matrix.shape != (3, 3):
            raise VisionError("VALIDATION")
        r = [[float(v) for v in row] for row in matrix.tolist()]
        rows: Matrix3 = ((r[0][0], r[0][1], r[0][2]), (r[1][0], r[1][1], r[1][2]), (r[2][0], r[2][1], r[2][2]))
        return cls(rows, source[0], source[1], target[0], target[1])

    def as_array(self) -> NDArray[np.float64]:
        """Ma trận dạng numpy `float64` để nhân hoặc biến đổi điểm."""
        return np.array(self.matrix, dtype=np.float64)

    def to_json(self) -> dict[str, object]:
        """Dạng dây `{matrix, sourceWidthPx, sourceHeightPx, widthPx, heightPx}`."""
        sizes = (self.source_width_px, self.source_height_px, self.width_px, self.height_px)
        return {"matrix": [list(r) for r in self.matrix], **dict(zip(_SIZE_KEYS, sizes, strict=True))}

    @classmethod
    def from_json(cls, data: Mapping[str, object]) -> Self:
        """Ngược của `to_json`; thiếu khoá, sai hình hoặc sai kiểu → `VisionError("VALIDATION")`."""
        matrix = data.get("matrix")
        if not isinstance(matrix, list) or len(matrix) != 3 or not all(isinstance(r, list) for r in matrix):
            raise VisionError("VALIDATION")
        sizes = [data.get(k) for k in _SIZE_KEYS]
        if not all(_positive_int(v) for v in sizes):
            raise VisionError("VALIDATION")
        if not all(len(row) == 3 and all(_is_number(v) for v in row) for row in matrix):
            raise VisionError("VALIDATION")
        w, h, tw, th = cast("list[int]", sizes)  # `_positive_int` đã kiểm
        return cls.from_array(np.array(matrix, dtype=np.float64), (w, h), (tw, th))


def compose(outer: Homography, inner: Homography) -> Homography:
    """Phép `outer ∘ inner` (áp `inner` trước): ma trận `outer · inner`.

    Đích của `inner` phải trùng nguồn của `outer`, không thì `VisionError("VALIDATION")`
    — nối hai phép lệch kích thước làm sai toạ độ mọi tầng sau.
    """
    if (inner.width_px, inner.height_px) != (outer.source_width_px, outer.source_height_px):
        raise VisionError("VALIDATION")
    product = outer.as_array() @ inner.as_array()
    source = (inner.source_width_px, inner.source_height_px)
    return Homography.from_array(product, source, (outer.width_px, outer.height_px))


@dataclass(frozen=True, slots=True)
class RectifyResult:
    """Ảnh đã nắn và homography từ ảnh vào tới nó (đã gồm phép co trần đầu ra)."""

    image: RgbImage
    homography: Homography

    def to_json(self) -> dict[str, object]:
        """Chỉ phần homography lên dây; ảnh lưu riêng dạng PNG."""
        return self.homography.to_json()
