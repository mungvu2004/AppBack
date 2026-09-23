"""Kiểu hợp đồng của gói ảnh: `RgbImage`, `Quad`, `Homography`, `compose`, `RectifyResult`."""

import numpy as np
import pytest

from packages.vision.preprocess.errors import VisionError
from packages.vision.preprocess.types import (
    Homography,
    Quad,
    RectifyResult,
    RgbImage,
    compose,
)

_IDENTITY_ROWS = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def _pixels(height: int = 4, width: int = 6) -> np.ndarray:
    """Ảnh RGB hợp lệ nhỏ nhất đủ dùng cho test."""
    return np.zeros((height, width, 3), dtype=np.uint8)


@pytest.mark.parametrize(
    "pixels",
    [
        np.zeros((4, 6, 3), dtype=np.uint16),
        np.zeros((4, 6), dtype=np.uint8),
        np.zeros((4, 6, 4), dtype=np.uint8),
        np.zeros((0, 6, 3), dtype=np.uint8),
        np.zeros((4, 0, 3), dtype=np.uint8),
    ],
    ids=["dtype", "ndim", "channels", "no_rows", "no_cols"],
)
def test_rgb_image_rejects_bad_array(pixels: np.ndarray) -> None:
    """Sai dtype, sai hình hoặc rỗng là lỗi lập trình → `ValueError`, không phải `VisionError`."""
    with pytest.raises(ValueError, match="RgbImage"):
        RgbImage(pixels)


def test_rgb_image_is_read_only_and_reports_size() -> None:
    """Người giữ ảnh không sửa được điểm ảnh đã qua kiểm; `width_px`/`height_px` lấy từ hình."""
    image = RgbImage(_pixels(4, 6))
    assert (image.width_px, image.height_px) == (6, 4)
    assert not image.pixels.flags.writeable
    with pytest.raises(ValueError, match="read-only"):
        image.pixels[0, 0, 0] = 1


def test_rgb_image_copies_non_contiguous_input() -> None:
    """Mảng không liền bộ nhớ được chép, nên `cv2` nhận được vùng nhớ hợp lệ."""
    source = np.arange(4 * 12 * 3, dtype=np.uint8).reshape(4, 12, 3)[:, ::2]
    image = RgbImage(source)
    assert image.pixels.flags.c_contiguous
    assert np.array_equal(image.pixels, source)


@pytest.mark.parametrize(
    "points",
    [
        ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0)),
        ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0), (2.0, 2.0)),
        ((0.0, 0.0), (1.0, 0.0), (1.0, float("nan")), (0.0, 1.0)),
        ((0.0, 0.0), (1.0, 0.0), (1.0, float("inf")), (0.0, 1.0)),
        ((0.0, 0.0), (1.0, 0.0), (True, 1.0), (0.0, 1.0)),
    ],
    ids=["three", "five", "nan", "inf", "bool"],
)
def test_quad_rejects_bad_points(points: object) -> None:
    """Số điểm sai, giá trị không hữu hạn hay `bool` → `VALIDATION` gắn trường `corners`."""
    with pytest.raises(VisionError) as caught:
        Quad(points)  # type: ignore[arg-type]  # cố ý truyền sai hình để chốt lỗi lúc chạy
    assert (caught.value.code, caught.value.field) == ("VALIDATION", "corners")


def test_quad_normalises_to_float() -> None:
    """Điểm số nguyên được đổi sang `float` để so sánh và tính toán sau không lẫn kiểu."""
    quad = Quad(((0, 0), (10, 0), (10, 5), (0, 5)))
    assert quad.points == ((0.0, 0.0), (10.0, 0.0), (10.0, 5.0), (0.0, 5.0))


@pytest.mark.parametrize(
    ("matrix", "sizes"),
    [
        (((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)), (4, 3, 4, 3)),
        (((1.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)), (4, 3, 4, 3)),
        (((float("nan"), 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)), (4, 3, 4, 3)),
        (_IDENTITY_ROWS, (0, 3, 4, 3)),
        (_IDENTITY_ROWS, (4, 3, -1, 3)),
        (_IDENTITY_ROWS, (True, 3, 4, 3)),
    ],
    ids=["two_rows", "short_row", "nan", "zero", "negative", "bool"],
)
def test_homography_rejects_bad_input(matrix: object, sizes: tuple[object, ...]) -> None:
    """Ma trận sai hình/không hữu hạn hoặc kích thước không nguyên dương → `VALIDATION`."""
    with pytest.raises(VisionError) as caught:
        Homography(matrix, *sizes)  # type: ignore[arg-type]  # cố ý truyền sai hình/kiểu để chốt lỗi lúc chạy
    assert (caught.value.code, caught.value.field) == ("VALIDATION", None)


def test_homography_identity_and_as_array() -> None:
    """`identity` giữ nguyên kích thước hai phía và cho ma trận đơn vị."""
    homography = Homography.identity(8, 5)
    assert (homography.source_width_px, homography.height_px) == (8, 5)
    assert np.array_equal(homography.as_array(), np.eye(3))


def test_homography_from_array_rejects_wrong_shape() -> None:
    """Mảng không phải 3x3 → `VALIDATION` (chặn ngay chỗ dựng, không để sai lan xuống)."""
    with pytest.raises(VisionError):
        Homography.from_array(np.eye(2), (4, 3), (4, 3))


def test_homography_json_round_trip() -> None:
    """`from_json(to_json())` bằng chính nó — dạng dây là camelCase của hợp đồng FE."""
    homography = Homography(((2.0, 0.0, 1.0), (0.0, 3.0, 2.0), (0.0, 0.0, 1.0)), 9, 7, 18, 21)
    payload = homography.to_json()
    assert payload["sourceWidthPx"] == 9
    assert Homography.from_json(payload) == homography


@pytest.mark.parametrize(
    "payload",
    [
        {"sourceWidthPx": 4, "sourceHeightPx": 3, "widthPx": 4, "heightPx": 3},
        {
            "matrix": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            "sourceWidthPx": 4,
            "sourceHeightPx": 3,
            "widthPx": 4,
            "heightPx": 3,
        },
        {
            "matrix": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], "x"],
            "sourceWidthPx": 4,
            "sourceHeightPx": 3,
            "widthPx": 4,
            "heightPx": 3,
        },
        {"matrix": [list(r) for r in _IDENTITY_ROWS], "sourceWidthPx": 4, "sourceHeightPx": 3, "widthPx": 4},
        {
            "matrix": [[1.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "sourceWidthPx": 4,
            "sourceHeightPx": 3,
            "widthPx": 4,
            "heightPx": 3,
        },
        {
            "matrix": [[1.0, 0.0, None], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "sourceWidthPx": 4,
            "sourceHeightPx": 3,
            "widthPx": 4,
            "heightPx": 3,
        },
    ],
    ids=["no_matrix", "two_rows", "row_not_list", "missing_size", "short_row", "not_number"],
)
def test_homography_from_json_rejects_bad_payload(payload: dict[str, object]) -> None:
    """Mỗi nhánh lỗi của `from_json` đều dừng ở `VALIDATION`, không ném `KeyError`/`TypeError`."""
    with pytest.raises(VisionError):
        Homography.from_json(payload)


def test_compose_multiplies_outer_by_inner() -> None:
    """`compose(outer, inner)` = `outer · inner`: áp `inner` trước, đúng thứ tự nhân ma trận."""
    inner = Homography(((2.0, 0.0, 0.0), (0.0, 2.0, 0.0), (0.0, 0.0, 1.0)), 4, 3, 8, 6)
    outer = Homography(((1.0, 0.0, 5.0), (0.0, 1.0, 7.0), (0.0, 0.0, 1.0)), 8, 6, 8, 6)
    result = compose(outer, inner)
    assert result.matrix == ((2.0, 0.0, 5.0), (0.0, 2.0, 7.0), (0.0, 0.0, 1.0))
    assert (result.source_width_px, result.width_px) == (4, 8)


def test_compose_keeps_value_when_identity_on_either_side() -> None:
    """Ghép với phép đơn vị ở trước hay sau đều không đổi giá trị."""
    inner = Homography(((2.0, 0.0, 0.0), (0.0, 2.0, 0.0), (0.0, 0.0, 1.0)), 4, 3, 8, 6)
    assert compose(Homography.identity(8, 6), inner) == inner
    assert compose(inner, Homography.identity(4, 3)) == inner


def test_compose_rejects_size_mismatch() -> None:
    """Đích của `inner` khác nguồn của `outer` → `VALIDATION`, không ghép bừa."""
    inner = Homography.identity(4, 3)
    with pytest.raises(VisionError):
        compose(Homography.identity(8, 6), inner)


def test_rectify_result_to_json_is_homography_only() -> None:
    """Ảnh đi đường PNG riêng, nên dây chỉ mang homography."""
    result = RectifyResult(RgbImage(_pixels()), Homography.identity(6, 4))
    assert result.to_json() == Homography.identity(6, 4).to_json()
