"""Mask tường cổ điển bằng ngưỡng Otsu + hình thái: mở rồi lấp khe cửa sổ (B5-02 [6], việc B).

Không mô hình học máy: ngưỡng xám BT.601 rồi Otsu tách mực, mở hình thái loại nét mảnh
hơn bề dày tường tối thiểu (chữ, đường kích thước, cung cửa), rồi lấp khe cửa sổ (nét
mảnh song song nối hai đầu tường) mà phép mở đã xoá. Gói này không nhập
`ml_contracts`/`messaging`/`storage`/`db`/`apps.*`.
"""

import math
from typing import Final

import cv2
import numpy as np
from numpy.typing import NDArray

from packages.vision.preprocess.types import RgbImage

_MIN_THICKNESS_PX_FLOOR: Final = 3
_WALL_MM: Final = 110.0
_PAPER_SCALE: Final = 1.1
_EDGE_TO_WALL_RATIO: Final = 270.0
_THICKNESS_FRACTION: Final = 0.6
_MAX_SPAN_PER_K: Final = 8
"""Trần độ dài phép đóng lấp cửa sổ, theo `k`: `k` ≈ 0,6 x vách 110 mm nên `8k` ≈ 530 mm,
dư cho cả cửa sổ chỉ vẽ hai nét mép trên tường 400 mm; trang tổng hợp cần ≤ 15 px (`k` = 3 → 25)."""


def default_min_thickness_px(width_px: int, height_px: int, px_per_paper_mm: float | None = None) -> int:
    """Bề dày tối thiểu (px) coi là tường: nửa bề dày vách 110 mm, sàn tại 3 px.

    Có `px_per_paper_mm` (tỉ lệ trang đã biết, vd 1:100 → 1,1 mm giấy cho vách 110 mm):
    `max(3, floor(0.6 x 1,1 x px_per_paper_mm))`. Không có (ước theo cạnh ngắn ảnh, vách
    110 mm ≈ 1/270 cạnh ngắn — `thresholds.ts:12-17`): `max(3, floor(0.6 x min(w, h) / 270))`.
    """
    if px_per_paper_mm is not None:
        raw = _THICKNESS_FRACTION * _PAPER_SCALE * px_per_paper_mm
    else:
        raw = _THICKNESS_FRACTION * min(width_px, height_px) / _EDGE_TO_WALL_RATIO
    return max(_MIN_THICKNESS_PX_FLOOR, int(np.floor(raw)))


def classic_wall_mask(img: RgbImage, *, min_thickness_px: int) -> NDArray[np.bool_]:
    """Mực (tối) → `True` sau ngưỡng Otsu, mở hình thái `k x k` xoá nét mảnh hơn tường, lấp cửa sổ.

    `min_thickness_px < 1` → `ValueError` (không có kernel hợp lệ). Không sửa `img.pixels`:
    các hàm `cv2` ở đây đều nhận mảng và trả mảng mới.
    """
    if min_thickness_px < 1:
        raise ValueError(f"min_thickness_px phải ≥ 1, nhận {min_thickness_px}")
    gray = cv2.cvtColor(img.pixels, cv2.COLOR_RGB2GRAY)
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    ink = np.asarray(otsu, np.uint8)
    return _bridge_windows(ink, _open_square(ink, min_thickness_px), min_thickness_px)


def _open_square(ink: NDArray[np.uint8], size: int) -> NDArray[np.uint8]:
    """Mở hình thái đúng nghĩa bằng hình vuông `size x size`, không dời ảnh khi `size` chẵn.

    `cv2.morphologyEx(MORPH_OPEN)` co rồi giãn với **cùng** neo `size // 2`; kernel chẵn
    thì cửa sổ không đối xứng nên kết quả lệch 1 px. Giãn phải dùng kernel phản chiếu:
    neo `size - 1 - a` với `a` là neo lúc co. Kernel lẻ hai neo trùng nhau, như cũ.
    """
    kernel = np.ones((size, size), np.uint8)
    erode_at = (size - 1) // 2
    dilate_at = size - 1 - erode_at
    eroded = cv2.erode(ink, kernel, anchor=(erode_at, erode_at))
    return np.asarray(cv2.dilate(eroded, kernel, anchor=(dilate_at, dilate_at)), np.uint8)


def _bridge_windows(ink: NDArray[np.uint8], walls: NDArray[np.uint8], size: int) -> NDArray[np.bool_]:
    """Lấp khe cửa sổ: dải nét mảnh xếp chồng nối kín hai đầu tường thẳng hàng thành tường.

    Cửa sổ vẽ bằng các nét 1 px song song tường, cách nhau ≤ ½ bề dày, nên phép mở xoá
    mất nó dù đáp án coi là tường. Đóng hình thái **vuông góc** với hướng tường (dài bằng
    bề dày tường dày nhất đo được, lẻ nên không lệch tâm) lấp khoảng giữa các nét; chỉ giữ
    đoạn liền theo hướng tường có tường ở **cả hai** đầu. Khe cửa đi không có nét nên không
    bị lấp; lòng phòng không có nét liền suốt từ tường này sang tường kia nên cũng không.
    Cuối cùng mở lại `size x size`: dải cửa sổ dày bằng tường nên còn, một nét lẻ 1 px nối
    hai tường (đường trục, bệ cửa đi) mảnh hơn `size` nên bị xoá như mọi nét mảnh khác.
    Độ dài đóng kẹp ở `_MAX_SPAN_PER_K x size + 1`: một khối tô đặc (khung tên, logo) làm
    distance lớn nhất phình ra, không được kéo phép đóng nối mọi thứ quanh nó.
    Giới hạn đã đo trên CubiCasa5K (24 mẫu có cầu thang/lan can): IoU tường 0,379 → 0,483
    nhưng cụm nét song song mà phép mở đã coi là tường (sàn ván, bậc thang dày ≥ k) bị lấp
    kín thêm — mặt nạ đầu vào đã sai ở đó, phép lấp khuếch đại nó.
    """
    measured = 2 * math.ceil(float(cv2.distanceTransform(walls, cv2.DIST_L2, 5).max())) + 1
    span = min(measured, _MAX_SPAN_PER_K * size + 1)
    is_wall = walls > 0
    across_rows = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((span, 1), np.uint8)) > 0
    across_cols = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((1, span), np.uint8)) > 0
    horizontal = _closed_runs(across_rows & ~is_wall, is_wall)
    vertical = _closed_runs((across_cols & ~is_wall).T, is_wall.T).T
    return _open_square((is_wall | horizontal | vertical).astype(np.uint8), size) > 0


def _closed_runs(candidate: NDArray[np.bool_], walls: NDArray[np.bool_]) -> NDArray[np.bool_]:
    """Các đoạn liền theo hàng của `candidate` có điểm tường ngay trước **và** ngay sau.

    Đánh số đoạn bằng tổng dồn các điểm bắt đầu (theo thứ tự hàng), nên điểm đầu và điểm
    cuối thứ `i` cùng thuộc đoạn `i`; chạm mép ảnh coi như không có tường. Nhãn `int32` (ảnh
    ≤ 2^31 điểm) để ảnh 40 MP không tốn thêm 320 MB cho bảng nhãn `int64`.
    """
    rows, cols = candidate.shape
    pad_c = np.zeros((rows, cols + 2), np.bool_)
    pad_w = np.zeros((rows, cols + 2), np.bool_)
    pad_c[:, 1:-1] = candidate
    pad_w[:, 1:-1] = walls
    starts = pad_c[:, 1:-1] & ~pad_c[:, :-2]
    ends = pad_c[:, 1:-1] & ~pad_c[:, 2:]
    closed = pad_w[:, :-2][starts] & pad_w[:, 2:][ends]
    label = np.cumsum(starts.ravel(), dtype=np.int32).reshape(rows, cols)
    keep = np.zeros(closed.size + 1, np.bool_)
    keep[1:] = closed
    return candidate & keep[label]
