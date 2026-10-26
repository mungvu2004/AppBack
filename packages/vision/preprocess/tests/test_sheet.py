"""Vùng vẽ của tờ: khung tên cột phải / dải dưới, nét viền sát mép, và đường cắt không nội suy của `rectify`."""

import numpy as np
import pytest
from numpy.typing import NDArray

from packages.vision.preprocess.geometry import rectify
from packages.vision.preprocess.sheet import drawing_box, drawing_quad
from packages.vision.preprocess.types import Quad, RgbImage

W, H = 600, 400
LINE = 150
"""Nét kẻ khung xám như CAD xuất ảnh (tối hơn nền 105 mức)."""


def sheet(*, frame: bool = True, title: str | None = "right", cells: int = 4) -> NDArray[np.uint8]:
    """Tờ xám `(H, W)`: viền cách mép 6 px, khung tên cột phải từ x=480 (hay dải dưới từ y=320) có `cells` ô."""
    gray = np.full((H, W), 255, dtype=np.uint8)
    if frame:
        gray[6, 6 : W - 6] = gray[H - 7, 6 : W - 6] = LINE
        gray[6 : H - 6, 6] = gray[6 : H - 6, W - 7] = LINE
    if title == "right":
        gray[6 : H - 6, 480] = LINE
        for k in range(1, cells + 1):
            gray[6 + k * (H - 12) // (cells + 1), 480 : W - 6] = LINE
    elif title == "bottom":
        gray[320, 6 : W - 6] = LINE
        for k in range(1, cells + 1):
            gray[320 : H - 6, 6 + k * (W - 12) // (cells + 1)] = LINE
    gray[100:250, 100:350] = 0  # "mặt bằng": khối đậm không chạm viền
    return gray


def test_drawing_box__drops_right_title_block_and_frame() -> None:
    """Cột khung tên có 4 ô + viền: vùng vẽ bên trái vạch ngăn, lùi 3 px khỏi viền và vạch."""
    assert drawing_box(sheet()) == (9, 9, 477, H - 10)


def test_drawing_box__drops_bottom_title_strip() -> None:
    """Dải khung tên dưới có ô đứng: vùng vẽ phía trên vạch ngăn."""
    assert drawing_box(sheet(title="bottom")) == (9, 9, W - 10, 317)


def test_drawing_box__frame_only() -> None:
    """Chỉ có viền: bỏ nét viền ở bốn mép."""
    assert drawing_box(sheet(title=None)) == (9, 9, W - 10, H - 10)


def test_drawing_box__strip_without_cells_is_not_a_title_block() -> None:
    """Đường dọc chạy suốt nhưng vùng phải không có ô bảng (tường dài của mặt bằng): không cắt ở đó."""
    assert drawing_box(sheet(cells=1)) == (9, 9, W - 10, H - 10)


def test_drawing_box__thick_walls_are_never_frame_lines() -> None:
    """Mặt bằng cắt sát: tường bao 10 px sát mép, vách dọc chạy suốt ở 76 % và cột phòng có 3 tường ngang: không cắt."""
    h, w = 800, 1000
    gray = np.full((h, w), 255, dtype=np.uint8)
    for y, x0, x1 in ((20, 20, 980), (770, 20, 980), (200, 760, 980), (400, 760, 980), (600, 760, 980), (450, 20, 760)):
        gray[y : y + 10, x0:x1] = 0
    for x in (20, 970, 760):
        gray[20:780, x : x + 10] = 0
    assert drawing_box(gray) is None


def test_drawing_box__nothing_to_trim() -> None:
    """Trang không viền, không khung tên (mặt bằng màu của chủ đầu tư): `None`."""
    assert drawing_box(sheet(frame=False, title=None)) is None


def rgb(gray: NDArray[np.uint8]) -> RgbImage:
    """Ảnh RGB từ ảnh xám."""
    return RgbImage(np.ascontiguousarray(np.repeat(gray[:, :, None], 3, axis=2)))


def test_drawing_quad__whole_page_without_frame() -> None:
    """Không có khung: dò trên cả trang, trả bốn góc vùng vẽ theo toạ độ ảnh."""
    quad = drawing_quad(rgb(sheet()), None)
    assert quad == Quad(((9.0, 9.0), (477.0, 9.0), (477.0, H - 10.0), (9.0, H - 10.0)))


def test_drawing_quad__inside_frame_maps_back_to_source() -> None:
    """Có khung (lệch 1 px vẫn coi là thẳng): góc vùng vẽ đưa ngược về ảnh gốc."""
    page = np.full((H + 40, W + 40), 255, dtype=np.uint8)
    page[20 : 20 + H, 20 : 20 + W] = sheet()
    frame = Quad(((20.0, 20.0), (20.0 + W, 21.0), (20.0 + W, 20.0 + H), (20.0, 20.0 + H)))
    quad = drawing_quad(rgb(page), frame)
    assert quad is not None
    assert quad.points[0] == pytest.approx((29.0, 29.0), abs=0.6)
    assert quad.points[2] == pytest.approx((497.0, 20.0 + H - 10.0), abs=0.6)


def test_drawing_quad__nothing_found_keeps_frame() -> None:
    """Không bỏ được gì: trả lại đúng khung (hay `None` khi không có khung)."""
    plain = rgb(sheet(frame=False, title=None))
    frame = Quad(((0.0, 0.0), (W - 1.0, 0.0), (W - 1.0, H - 1.0), (0.0, H - 1.0)))
    assert drawing_quad(plain, frame) == frame
    assert drawing_quad(plain, None) is None


def test_rectify__axis_aligned_quad_is_a_pixel_exact_crop() -> None:
    """Khung thẳng trục (lệch <= 2 px): cắt nguyên pixel, nét 1 px giữ nguyên độ đậm, homography tịnh tiến."""
    gray = np.full((H, W), 255, dtype=np.uint8)
    gray[200, :] = 246  # đường kích thước nhạt 9 mức: nắn nội suy làm mất nó
    quad = Quad(((10.4, 10.0), (500.0, 11.5), (499.0, 300.0), (11.0, 301.0)))
    result = rectify(rgb(gray), quad)
    assert result.image.pixels.shape == (290, 489, 3)  # x 11..500, y 11..301 (làm tròn nửa lên)
    assert int(result.image.pixels[189, :, 0].max()) == 246
    assert result.homography.as_array().tolist() == [[1.0, 0.0, -11.0], [0.0, 1.0, -11.0], [0.0, 0.0, 1.0]]


def test_rectify__tilted_quad_still_warps() -> None:
    """Lệch quá 2 px: vẫn nắn phối cảnh như trước (không cắt)."""
    quad = Quad(((10.0, 10.0), (500.0, 20.0), (500.0, 300.0), (10.0, 300.0)))
    result = rectify(rgb(np.full((H, W), 255, dtype=np.uint8)), quad)
    assert not np.allclose(result.homography.as_array()[:2, :2], np.eye(2))
