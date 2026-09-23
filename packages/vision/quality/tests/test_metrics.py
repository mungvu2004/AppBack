"""Số đo dựng bằng numpy/cv2 ngay trong test — không tệp nhị phân commit (khối [3]).

Ảnh test cỡ 400x400 để lưới 4x4 chia hết (mỗi ô 100x100 px), giúp so `Region` kỳ vọng
bằng số hữu tỉ tròn thay vì phụ thuộc `np.array_split` chia dư.
"""

import cv2
import numpy as np
import pytest
from numpy.typing import NDArray

from packages.vision.quality.metrics import (
    WHOLE_IMAGE,
    Measurement,
    Region,
    _small_blob_area_threshold,
    contrast_score,
    densest_noise_region,
    ink_mask,
    lowest_contrast_region,
    noise_score,
    round_score,
    round_skew,
)

_SIZE = 400
_CELL = _SIZE // 4


def _white_canvas() -> NDArray[np.uint8]:
    """Trang trắng toàn phần, không mực."""
    return np.full((_SIZE, _SIZE), 255, dtype=np.uint8)


def _grid_drawing(*, line_gray: int = 0, bg_gray: int = 255, thickness: int = 6) -> NDArray[np.uint8]:
    """Bản vẽ giả: lưới đường kẻ phủ đều toàn ảnh, mỗi ô 4x4 đều có đủ mực và giấy."""
    img = np.full((_SIZE, _SIZE), bg_gray, dtype=np.uint8)
    for offset in range(0, _SIZE + 1, 40):
        cv2.line(img, (0, offset), (_SIZE, offset), line_gray, thickness)
        cv2.line(img, (offset, 0), (offset, _SIZE), line_gray, thickness)
    return img


def _region_for_cell(row_index: int, col_index: int) -> Region:
    """`Region` kỳ vọng của ô `(row_index, col_index)` trong lưới 4x4 của `_SIZE`."""
    ratio = _CELL / _SIZE
    return Region(col_index * ratio, row_index * ratio, ratio, ratio)


def test_contrast_score__white_page_is_zero() -> None:
    """Trang trắng không có mực để lấy trung vị: phải trả `0.0` chứ không nổ vì tập rỗng."""
    assert contrast_score(_white_canvas()) == 0.0


def test_contrast_score__black_page_is_zero() -> None:
    """Trang đen là mặt còn lại của cùng luật: thiếu giấy cũng cho `0.0`."""
    black = np.zeros((_SIZE, _SIZE), dtype=np.uint8)
    assert contrast_score(black) == 0.0


def test_noise_score__white_and_black_pages_are_zero() -> None:
    """Không thành phần liên thông nào thì nhiễu là `0.0`, không phải phép chia cho 0."""
    assert noise_score(_white_canvas()) == 0.0
    assert noise_score(np.zeros((_SIZE, _SIZE), dtype=np.uint8)) == 0.0


def test_contrast_score__black_ink_on_white_paper_is_near_one() -> None:
    """Mực đen trên giấy trắng là đầu tốt của thang: điểm phải sát 1, không kẹt giữa dải."""
    assert contrast_score(_grid_drawing()) > 0.95


def test_contrast_score__compressed_range_is_below_attention() -> None:
    """Nén dải xám còn 40 % (`128 ± 51`) → dưới ngưỡng `CONTRAST_ATTENTION_SCORE`."""
    gray = _grid_drawing(line_gray=128 - 51, bg_gray=128 + 51)
    assert contrast_score(gray) < 0.45


def test_lowest_contrast_region__one_faded_cell_is_found() -> None:
    """Một ô lưới bị nhạt đi → `lowest_contrast_region` trỏ đúng ô đó."""
    gray = _grid_drawing()
    row_index, col_index = 0, 2
    rows = slice(row_index * _CELL, (row_index + 1) * _CELL)
    cols = slice(col_index * _CELL, (col_index + 1) * _CELL)
    cell = gray[rows, cols].copy()
    cell[cell < 128] = 120
    gray[rows, cols] = cell

    assert lowest_contrast_region(gray) == _region_for_cell(row_index, col_index)


def test_lowest_contrast_region__no_cell_qualifies_returns_whole_image() -> None:
    """Không ô nào đủ cả mực lẫn giấy → trả cả ảnh, không trả `None` bắt bên gọi tự xử."""
    assert lowest_contrast_region(_white_canvas()) == WHOLE_IMAGE


def test_noise_score__thick_clean_lines_is_near_zero() -> None:
    """Nét dày sạch không được tính là đốm: chốt ngưỡng diện tích không quét nhầm nét thật."""
    assert noise_score(_grid_drawing()) < 0.05


def test_noise_score__salt_pepper_two_percent_exceeds_attention() -> None:
    """Muối tiêu 2 % trên bản vẽ → nhiễu vượt `NOISE_ATTENTION_SCORE` (0,4)."""
    gray = _grid_drawing().copy()
    rng = np.random.default_rng(20260923)
    speckle_mask = rng.random(gray.shape) < 0.02
    gray[speckle_mask] = 0

    assert noise_score(gray) > 0.4


def test_densest_noise_region__blobs_concentrated_in_one_cell_are_found() -> None:
    """Đốm nhiễu dồn một ô lưới → `densest_noise_region` trỏ đúng ô đó."""
    gray = _white_canvas()
    row_index, col_index = 2, 1
    row_start, col_start = row_index * _CELL, col_index * _CELL
    rows = np.arange(row_start + 10, row_start + _CELL - 10, 5)
    cols = np.arange(col_start + 10, col_start + _CELL - 10, 5)
    row_grid, col_grid = np.meshgrid(rows, cols, indexing="ij")
    gray[row_grid, col_grid] = 0

    assert densest_noise_region(gray) == _region_for_cell(row_index, col_index)


def test_densest_noise_region__no_blobs_returns_whole_image() -> None:
    """Không đốm nhỏ nào thì trả cả ảnh — cùng luật dự phòng với `lowest_contrast_region`."""
    assert densest_noise_region(_white_canvas()) == WHOLE_IMAGE


def test_densest_noise_region__only_large_blobs_returns_whole_image() -> None:
    """Có thành phần liên thông nhưng không đốm nào nhỏ hơn ngưỡng → cả ảnh."""
    assert densest_noise_region(_grid_drawing()) == WHOLE_IMAGE


def test_lowest_contrast_region__tiny_image_skips_empty_grid_cells() -> None:
    """Ảnh nhỏ hơn 4 px một cạnh → `np.array_split` sinh ô rỗng, `_grid_cells` phải bỏ qua."""
    gray = np.array([[0, 255], [255, 0]], dtype=np.uint8)
    assert isinstance(lowest_contrast_region(gray), Region)


@pytest.mark.parametrize(
    ("short_edge_px", "expected"),
    [(540, 1), (1080, 4)],
)
def test_small_blob_area_threshold__spec_examples(short_edge_px: int, expected: int) -> None:
    """Ngưỡng diện tích đốm theo cạnh ngắn: 540 px → 1 px, 1.080 px → 4 px."""
    assert _small_blob_area_threshold(short_edge_px) == expected


def test_ink_mask__separates_ink_from_paper() -> None:
    """Otsu phải tách thật: trên bản vẽ, mặt nạ không được toàn `True` hay toàn `False`."""
    mask = ink_mask(_grid_drawing())
    assert mask.dtype == np.bool_
    assert bool(mask.any())
    assert not bool(mask.all())


@pytest.mark.parametrize(
    "kwargs",
    [
        {"x_ratio": -0.1, "y_ratio": 0.0, "width_ratio": 1.0, "height_ratio": 1.0},
        {"x_ratio": 1.1, "y_ratio": 0.0, "width_ratio": 0.0, "height_ratio": 0.0},
        {"x_ratio": 0.6, "y_ratio": 0.0, "width_ratio": 0.6, "height_ratio": 0.1},
        {"x_ratio": 0.0, "y_ratio": 0.6, "width_ratio": 0.1, "height_ratio": 0.6},
    ],
)
def test_region__invalid_ranges_raise_value_error(kwargs: dict[str, float]) -> None:
    """Bốn kiểu sai dải (âm, quá 1, tràn phải, tràn dưới) đều bị chặn ngay lúc dựng `Region`."""
    with pytest.raises(ValueError, match="Region"):
        Region(**kwargs)


def test_round_score__matches_js_math_round_quirks() -> None:
    """Hai ca mà `round` của Python cho khác `Math.round` của JS — chốt BE và FE cùng một số."""
    assert round_score(0.4445) == 0.445
    assert round_score(0.0005) == 0.001


def test_round_skew__negative_half_rounds_toward_positive_infinity() -> None:
    """Nửa âm làm tròn về phía `+vô cùng` như JS, không về số chẵn như `round` của Python."""
    assert round_skew(-0.125) == -0.12


def test_measurement__is_a_plain_record() -> None:
    """`Measurement` không kiểm tra cũng không đổi giá trị: giữ nguyên số đã đặt vào."""
    measurement = Measurement(width_px=800, height_px=600, skew_deg=1.5, contrast_score=0.8, noise_score=0.1)
    assert measurement.width_px == 800
    assert measurement.noise_score == 0.1
