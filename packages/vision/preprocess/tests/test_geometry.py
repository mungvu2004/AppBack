"""Góc, khung, nắn phối cảnh, nắn nghiêng và trần đầu ra của `preprocess.geometry`."""

import itertools
import math

import cv2
import numpy as np
import pytest
from numpy.typing import NDArray

from packages.vision.preprocess.errors import VisionError
from packages.vision.preprocess.geometry import (
    deskew,
    estimate_skew,
    find_frame,
    order_corners,
    quad_from_ratios,
    quad_to_ratios,
    rectify,
    validate_quad,
    working_gray,
)
from packages.vision.preprocess.raster import encode_png, load_raster
from packages.vision.preprocess.tests.drawing import make_drawing, on_desk, rotate
from packages.vision.preprocess.types import Homography, Point, Quad, RgbImage, compose

_IMAGE_W, _IMAGE_H = 400, 300
_VALID_POINTS: tuple[Point, Point, Point, Point] = (
    (10.0, 20.0),
    (200.0, 15.0),
    (210.0, 180.0),
    (20.0, 190.0),
)
_SKEW_DEG = 3.4


def _valid_quad() -> Quad:
    """Tứ giác lồi, đúng thứ tự, đủ lớn trong ảnh 400x300 — mốc của các test `validate_quad`."""
    return Quad(_VALID_POINTS)


def _padded_drawing(angle_deg: float) -> NDArray[np.uint8]:
    """Bản vẽ có viền trắng rộng rồi xoay, để phép xoay không cắt mất nét nào."""
    drawing = make_drawing(1600, 1100)
    padded = np.pad(drawing, ((120, 120), (120, 120), (0, 0)), constant_values=255)
    return rotate(np.asarray(padded, dtype=np.uint8), angle_deg)


def _ink_count(pixels: NDArray[np.uint8]) -> int:
    """Số điểm ảnh tối (nét) — mốc so sánh trước/sau khi nắn để bắt việc cắt nét."""
    return int((cv2.cvtColor(pixels, cv2.COLOR_RGB2GRAY) < 128).sum())


# --- góc -------------------------------------------------------------------


@pytest.mark.parametrize("permutation", list(itertools.permutations(range(4))))
def test_order_corners_is_permutation_invariant(permutation: tuple[int, ...]) -> None:
    """Mọi hoán vị của 4 điểm cho cùng một thứ tự chuẩn (24 hoán vị)."""
    shuffled = [_VALID_POINTS[i] for i in permutation]
    assert order_corners(shuffled).points == _VALID_POINTS


def test_order_corners_starts_at_smallest_x_plus_y() -> None:
    """Điểm bắt đầu là điểm có `x + y` nhỏ nhất, chiều đi là kim đồng hồ trong hệ ảnh."""
    quad = order_corners([(90.0, 10.0), (10.0, 90.0), (90.0, 90.0), (10.0, 10.0)])
    assert quad.points == ((10.0, 10.0), (90.0, 10.0), (90.0, 90.0), (10.0, 90.0))


def test_order_corners_rejects_wrong_count() -> None:
    """Không đúng 4 điểm → `VALIDATION` gắn `corners`."""
    with pytest.raises(VisionError) as caught:
        order_corners([(0.0, 0.0), (1.0, 1.0), (2.0, 0.0)])
    assert (caught.value.code, caught.value.field) == ("VALIDATION", "corners")


def test_validate_quad_accepts_valid_quad() -> None:
    """Tứ giác hợp lệ đi qua mọi luật mà không ném."""
    validate_quad(_valid_quad(), _IMAGE_W, _IMAGE_H)


def _outside_quad() -> Quad:
    """Một góc nằm ngoài `[0, w]`."""
    return order_corners([(10.0, 20.0), (410.0, 15.0), (210.0, 180.0), (20.0, 190.0)])


def _concave_quad() -> Quad:
    """Một điểm nằm trong tam giác ba điểm còn lại → không lồi."""
    return order_corners([(10.0, 10.0), (200.0, 10.0), (100.0, 60.0), (10.0, 200.0)])


def _self_crossing_quad() -> Quad:
    """Hình nơ: hai cạnh đối cắt nhau (không đi qua `order_corners`)."""
    return Quad(((10.0, 10.0), (200.0, 200.0), (200.0, 10.0), (10.0, 200.0)))


def _reversed_quad() -> Quad:
    """Lồi nhưng ngược chiều kim đồng hồ → sai thứ tự."""
    p = _VALID_POINTS
    return Quad((p[0], p[3], p[2], p[1]))


def _short_edge_quad() -> Quad:
    """Cạnh trên chỉ dài ~14 px < 16 px, các luật khác vẫn đạt."""
    return order_corners([(10.0, 10.0), (24.0, 12.0), (240.0, 280.0), (12.0, 280.0)])


def _tiny_quad() -> Quad:
    """Vuông 30x30 = 900 px² < 1 % của 400x300, cạnh vẫn ≥ 16 px."""
    return order_corners([(10.0, 10.0), (40.0, 10.0), (40.0, 40.0), (10.0, 40.0)])


@pytest.mark.parametrize(
    "factory",
    [_outside_quad, _concave_quad, _self_crossing_quad, _reversed_quad, _short_edge_quad, _tiny_quad],
    ids=["outside", "concave", "self_crossing", "reversed", "short_edge", "tiny"],
)
def test_validate_quad_rejects_each_rule(factory: object) -> None:
    """Mỗi luật của khối [6] có một tứ giác vi phạm riêng, tất cả → `VALIDATION`/`corners`."""
    with pytest.raises(VisionError) as caught:
        validate_quad(factory(), _IMAGE_W, _IMAGE_H)  # type: ignore[operator]  # `factory` là `object` để bảng ca nhận mọi hàm dựng
    assert (caught.value.code, caught.value.field) == ("VALIDATION", "corners")


def test_quad_ratios_round_trip() -> None:
    """Pixel → tỉ lệ → pixel giữ nguyên toạ độ (dạng FE lưu độc lập độ phân giải)."""
    quad = _valid_quad()
    ratios = quad_to_ratios(quad, _IMAGE_W, _IMAGE_H)
    assert all(0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 for x, y in ratios)
    back = quad_from_ratios(ratios, _IMAGE_W, _IMAGE_H)
    assert max(math.dist(a, b) for a, b in zip(back.points, quad.points, strict=True)) < 1e-9


def test_quad_from_ratios_rejects_wrong_count() -> None:
    """Không đúng 4 tỉ lệ → `VALIDATION`/`corners` thay vì `IndexError`."""
    with pytest.raises(VisionError) as caught:
        quad_from_ratios([(0.0, 0.0), (1.0, 0.0)], _IMAGE_W, _IMAGE_H)
    assert (caught.value.code, caught.value.field) == ("VALIDATION", "corners")


# --- khung -----------------------------------------------------------------


def _desk_image() -> tuple[RgbImage, Quad, Quad]:
    """Bản vẽ 1200x900 có khung, nắn phối cảnh lên mặt bàn xám 1600x1200."""
    desk, frame_quad, paper_quad = on_desk(make_drawing(1200, 900), desk_px=(1600, 1200))
    return RgbImage(desk), frame_quad, paper_quad


def _max_corner_error(found: Quad, target: Quad) -> float:
    """Lệch lớn nhất giữa hai bộ góc đã sắp cùng thứ tự."""
    return max(math.dist(a, b) for a, b in zip(found.points, target.points, strict=True))


def test_find_frame_matches_frame_or_paper_corners() -> None:
    """Khung tìm được lệch ≤ 1,5 % đường chéo so với khung vẽ **hoặc** mép giấy."""
    image, frame_quad, paper_quad = _desk_image()
    found = find_frame(image)
    assert found is not None
    tolerance = 0.015 * math.hypot(image.width_px, image.height_px)
    assert min(_max_corner_error(found, frame_quad), _max_corner_error(found, paper_quad)) <= tolerance


def test_find_frame_returns_none_without_frame() -> None:
    """Bản vẽ không khung có đường kích thước ngoài tường bao → không tứ giác nào bao đủ nét."""
    assert find_frame(RgbImage(make_drawing(1200, 900, frame=False))) is None


def test_find_frame_ignores_image_border_quad() -> None:
    """Tứ giác trùng chính viền ảnh bị loại, nên ảnh chỉ có viền ngoài cho `None`."""
    canvas = np.full((300, 400, 3), 255, dtype=np.uint8)
    cv2.rectangle(canvas, (0, 0), (399, 299), (0, 0, 0), 1)
    assert find_frame(RgbImage(canvas)) is None


# --- nắn phối cảnh ---------------------------------------------------------


def test_rectify_keeps_frame_aspect_ratio() -> None:
    """Tỉ lệ khung ảnh nắn ra lệch ≤ 2 % so với tỉ lệ thật của vùng khung (4:3)."""
    image, frame_quad, _ = _desk_image()
    result = rectify(image, frame_quad)
    assert result.image.width_px / result.image.height_px == pytest.approx(4 / 3, rel=0.02)


def test_rectify_homography_maps_source_corners_to_target_corners() -> None:
    """Homography đưa 4 góc nguồn về đúng 4 góc ảnh đích, lệch ≤ 1 px."""
    image, frame_quad, _ = _desk_image()
    result = rectify(image, frame_quad)
    width, height = result.image.width_px, result.image.height_px
    source = np.array([frame_quad.points], dtype=np.float32)
    mapped = cv2.perspectiveTransform(source, result.homography.as_array())[0]
    expected = [(0.0, 0.0), (width, 0.0), (width, height), (0.0, height)]
    assert max(math.dist(tuple(m), e) for m, e in zip(mapped, expected, strict=True)) <= 1.0


def test_rectify_homography_survives_json_and_identity_compose() -> None:
    """Homography của kết quả đi được vòng JSON và ghép đơn vị hai phía không đổi."""
    image, frame_quad, _ = _desk_image()
    homography = rectify(image, frame_quad).homography
    assert Homography.from_json(homography.to_json()) == homography
    before = Homography.identity(homography.source_width_px, homography.source_height_px)
    after = Homography.identity(homography.width_px, homography.height_px)
    assert compose(homography, before) == homography
    assert compose(after, homography) == homography


def test_rectify_rejects_invalid_quad() -> None:
    """`validate_quad` chạy trước mọi thứ: góc xấu không tới được `warpPerspective`."""
    image = RgbImage(make_drawing(400, 300))
    with pytest.raises(VisionError) as caught:
        rectify(image, _tiny_quad())
    assert caught.value.field == "corners"


def test_rectify_respects_max_pixels() -> None:
    """Kích thước đích vượt trần → ảnh trả ra ≤ trần (ma trận co trước khi warp)."""
    image, frame_quad, _ = _desk_image()
    result = rectify(image, frame_quad, max_pixels=100_000)
    assert result.image.width_px * result.image.height_px <= 100_000
    assert result.homography.width_px == result.image.width_px


# --- nắn nghiêng -----------------------------------------------------------


def test_estimate_skew_reports_positive_rotation() -> None:
    """Ảnh xoay `+3,4°` bằng `getRotationMatrix2D` đo ra trong `[3,2; 3,6]` (chốt dấu)."""
    estimate = estimate_skew(working_gray(RgbImage(_padded_drawing(_SKEW_DEG))))
    assert 3.2 <= estimate.angle_deg <= 3.6
    assert estimate.segments_bbox is not None


def test_estimate_skew_reports_negative_rotation() -> None:
    """Xoay ngược dấu cho góc ngược dấu, cùng độ lớn."""
    estimate = estimate_skew(working_gray(RgbImage(_padded_drawing(-_SKEW_DEG))))
    assert -3.6 <= estimate.angle_deg <= -3.2


def test_estimate_skew_returns_bbox_in_source_pixels() -> None:
    """Hộp bao đoạn thẳng tính theo pixel ảnh gốc, nằm trong ảnh gốc (không theo bản làm việc)."""
    pixels = _padded_drawing(_SKEW_DEG)
    image = RgbImage(pixels)
    bbox = estimate_skew(working_gray(image)).segments_bbox
    assert bbox is not None
    assert 0.0 <= bbox[0] <= bbox[2] <= image.width_px
    assert 0.0 <= bbox[1] <= bbox[3] <= image.height_px


def test_estimate_skew_on_blank_image() -> None:
    """Ảnh trắng không có đoạn nào → `0.0` và `segments_bbox=None`."""
    blank = RgbImage(np.full((600, 800, 3), 255, dtype=np.uint8))
    assert estimate_skew(working_gray(blank)) == estimate_skew(working_gray(blank))
    estimate = estimate_skew(working_gray(blank))
    assert (estimate.angle_deg, estimate.segments_bbox) == (0.0, None)


def test_working_gray_downscales_long_edge() -> None:
    """Ảnh cạnh dài > 2.000 px được thu nhỏ, `scale` = làm việc / gốc."""
    work = working_gray(RgbImage(make_drawing(2400, 1700)))
    assert max(work.gray.shape) == 2000
    assert work.scale == pytest.approx(2000 / 2400)


def test_deskew_straightens_and_keeps_all_ink() -> None:
    """Sau `deskew`, góc đo lại ≤ 0,2° và tổng điểm mực lệch ≤ 3 % (không cắt nét)."""
    tilted = _padded_drawing(_SKEW_DEG)
    result = deskew(RgbImage(tilted))
    assert abs(estimate_skew(working_gray(result.image)).angle_deg) <= 0.2
    assert _ink_count(result.image.pixels) == pytest.approx(_ink_count(tilted), rel=0.03)


def test_deskew_keeps_identity_for_straight_image() -> None:
    """Ảnh đã thẳng (`|skew| < 0,05°`) giữ nguyên điểm ảnh và trả `Homography.identity`."""
    pixels = make_drawing(800, 600)
    result = deskew(RgbImage(pixels))
    assert result.homography == Homography.identity(800, 600)
    assert np.array_equal(result.image.pixels, pixels)


def test_deskew_caps_straight_image_above_max_pixels() -> None:
    """Nhánh ảnh thẳng cũng qua trần đầu ra; homography thành phép co, không còn đơn vị."""
    result = deskew(RgbImage(make_drawing(800, 600)), max_pixels=120_000)
    assert result.image.width_px * result.image.height_px <= 120_000
    assert result.homography != Homography.identity(800, 600)
    assert result.homography.matrix[0][0] == pytest.approx(result.image.width_px / 800)


def test_deskew_respects_max_pixels_when_rotating() -> None:
    """Xoay 10° trên ảnh 800x600 với trần 480.000: ảnh trả ra và bản PNG của nó đều ≤ trần.

    Đi qua đúng `encode_png` + `load_raster` của gói (khối [8]) chứ không phải
    `cv2.imencode`: chốt luôn rằng ảnh đã lọt trần thì nạp lại cũng không chạm U03.
    """
    tilted = rotate(make_drawing(800, 600), 10.0)
    result = deskew(RgbImage(tilted), max_pixels=480_000)
    width, height = result.image.width_px, result.image.height_px
    assert width * height <= 480_000
    reloaded = load_raster(encode_png(result.image), max_pixels=480_000)
    assert reloaded.width_px == width
    assert reloaded.height_px == height
