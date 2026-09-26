"""Test hình học góc (B2-05b [6] #31 bước 1, 3): mỗi luật một test, khứ hồi với `rectify` thật."""

import math

import numpy as np
import pytest

from apps.api.quality.errors import QUALITY_DRAWING_CHANGED
from apps.api.quality.geometry import Ratios, corners_match, parse_homography, to_unrectified, validate_corner_ratios
from apps.api.quality.tests._images import desk_shot
from packages.core.errors import AppError
from packages.vision.preprocess import Homography, RgbImage, quad_from_ratios, rectify

MIN_AREA = 0.05
EPS = 0.002
GOOD: Ratios = ((0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9))


def _rejected(points: object) -> AppError:
    """Chạy `validate_corner_ratios` và trả lỗi phải có; không ném là test hỏng."""
    with pytest.raises(AppError) as info:
        validate_corner_ratios(points, min_area=MIN_AREA, eps=EPS)  # type: ignore[arg-type]
    return info.value


def _assert_field_corners(error: AppError) -> None:
    """422 `VALIDATION` gắn `field="corners"`."""
    assert (error.code.code, error.code.status) == ("VALIDATION", 422)
    assert error.wire_params() == {"field": "corners"}


@pytest.mark.parametrize(
    "points",
    [
        GOOD[:3],
        (*GOOD, (0.5, 0.5)),
        ((0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1,)),
        ((0.1, 0.1), (0.9, 0.1), (0.9, 0.9), ("a", 0.9)),
        ((0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, math.nan)),
        ((0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, True)),
    ],
)
def test_validate_corner_ratios__count_or_shape(points: object) -> None:
    """Không đúng 4 điểm, điểm không phải cặp số hữu hạn."""
    _assert_field_corners(_rejected(points))


@pytest.mark.parametrize("bad", [(-0.01, 0.1), (1.01, 0.1), (0.1, -0.01), (0.1, 1.01)])
def test_validate_corner_ratios__outside_unit_square(bad: tuple[float, float]) -> None:
    """Toạ độ ngoài [0, 1] ở cả hai trục, cả hai phía."""
    _assert_field_corners(_rejected((bad, (0.9, 0.1), (0.9, 0.9), (0.1, 0.9))))


def test_validate_corner_ratios__concave() -> None:
    """Tứ giác lõm (một góc thụt vào trong)."""
    _assert_field_corners(_rejected(((0.1, 0.1), (0.9, 0.1), (0.5, 0.3), (0.1, 0.9))))


def test_validate_corner_ratios__self_intersecting() -> None:
    """Hình nơ: hai cạnh đối cắt nhau."""
    _assert_field_corners(_rejected(((0.1, 0.1), (0.9, 0.9), (0.9, 0.1), (0.1, 0.9))))


def test_validate_corner_ratios__collinear() -> None:
    """Ba điểm thẳng hàng (tích có hướng 0) bị loại."""
    _assert_field_corners(_rejected(((0.1, 0.1), (0.5, 0.1), (0.9, 0.1), (0.1, 0.9))))


def test_validate_corner_ratios__counter_clockwise() -> None:
    """Đúng bốn góc nhưng ngược chiều kim đồng hồ."""
    _assert_field_corners(_rejected((GOOD[0], GOOD[3], GOOD[2], GOOD[1])))


def test_validate_corner_ratios__wrong_start() -> None:
    """Thuận chiều nhưng bắt đầu ở TR: không tự sắp lại."""
    _assert_field_corners(_rejected((GOOD[1], GOOD[2], GOOD[3], GOOD[0])))


def test_validate_corner_ratios__too_small() -> None:
    """Diện tích 0,04 < 0,05."""
    _assert_field_corners(_rejected(((0.4, 0.4), (0.6, 0.4), (0.6, 0.6), (0.4, 0.6))))


def test_validate_corner_ratios__full_page_and_ints() -> None:
    """Bốn góc toàn trang hợp lệ (số nguyên được ép về float); nhận cả list."""
    got = validate_corner_ratios([[0, 0], [1, 0], [1, 1], [0, 1]], min_area=MIN_AREA, eps=EPS)  # type: ignore[list-item]
    assert got == ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))
    assert validate_corner_ratios(GOOD, min_area=MIN_AREA, eps=EPS) == GOOD


def test_validate_corner_ratios__area_boundary() -> None:
    """Vừa qua diện tích tối thiểu thì hợp lệ."""
    side = math.sqrt(MIN_AREA) + 1e-9
    box = ((0.2, 0.2), (0.2 + side, 0.2), (0.2 + side, 0.2 + side), (0.2, 0.2 + side))
    assert validate_corner_ratios(box, min_area=MIN_AREA, eps=EPS) == box


def test_corners_match__eps_boundary() -> None:
    """Lệch đúng eps vẫn trùng, quá eps thì không; khác số điểm thì không."""
    shifted = tuple((x + 0.002, y) for x, y in GOOD)
    assert corners_match(GOOD, shifted, 0.002 + 1e-12)
    assert not corners_match(GOOD, shifted, 0.001)
    assert corners_match(GOOD, GOOD, 0.0)
    assert not corners_match(GOOD, GOOD[:3], 1.0)


def test_to_unrectified__round_trip_with_real_rectify() -> None:
    """Góc trên trang nắn → tỉ lệ trang chưa nắn → qua homography thuận lại đúng chỗ (≤ 1 px)."""
    shot = desk_shot()
    base = RgbImage(shot.pixels)
    result = rectify(base, quad_from_ratios(shot.corners, base.width_px, base.height_px))
    width, height = result.image.width_px, result.image.height_px
    back = to_unrectified(GOOD, page_width_px=width, page_height_px=height, homography=result.homography)
    matrix = result.homography.as_array()
    for (rx, ry), (px, py) in zip(back, GOOD, strict=True):
        moved = matrix @ np.array([rx * base.width_px, ry * base.height_px, 1.0])
        assert abs(moved[0] / moved[2] - px * width) <= 1.0
        assert abs(moved[1] / moved[2] - py * height) <= 1.0
    assert all(0.0 <= v <= 1.0 for p in back for v in p)


def test_to_unrectified__clamps_outside_points() -> None:
    """Điểm suy ra nằm ngoài ảnh nguồn thì kẹp về [0, 1]."""
    shift = Homography(((1.0, 0.0, 50.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)), 100, 100, 100, 100)
    got = to_unrectified(GOOD, page_width_px=100, page_height_px=100, homography=shift)
    assert got[0][0] == 0.0  # (10 - 50) / 100 < 0


def test_to_unrectified__singular_is_conflict() -> None:
    """Ma trận suy biến → 409 `QUALITY_DRAWING_CHANGED`."""
    flat = Homography(((1.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0)), 100, 100, 100, 100)
    with pytest.raises(AppError) as info:
        to_unrectified(GOOD, page_width_px=100, page_height_px=100, homography=flat)
    assert info.value.code is QUALITY_DRAWING_CHANGED


def test_to_unrectified__point_at_infinity_is_conflict() -> None:
    """Điểm rơi vào đường chân trời (w = 0 sau nghịch đảo) → 409."""
    tilted = Homography(((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.01, 0.0, 1.0)), 100, 100, 100, 100)
    # nghịch đảo có hàng cuối (-0,01; 0; 1): điểm x = 100 px cho w = 0.
    edge: Ratios = ((1.0, 0.1), (1.0, 0.1), (1.0, 0.9), (0.1, 0.9))
    with pytest.raises(AppError) as info:
        to_unrectified(edge, page_width_px=100, page_height_px=100, homography=tilted)
    assert info.value.code is QUALITY_DRAWING_CHANGED


@pytest.mark.parametrize("broken", [{}, {"matrix": [[1, 0], [0, 1]]}, {"widthPx": 0}])
def test_parse_homography__broken_is_conflict(broken: dict[str, object]) -> None:
    """Thiếu khoá, sai hình, kích thước xấu → 409."""
    data = {**Homography.identity(80, 60).to_json(), **broken} if broken else {}
    with pytest.raises(AppError) as info:
        parse_homography(data)
    assert info.value.code is QUALITY_DRAWING_CHANGED


def test_parse_homography__round_trip() -> None:
    """JSON hợp lệ khứ hồi."""
    h = Homography.identity(80, 60)
    assert parse_homography(h.to_json()) == h


DIAMOND: Ratios = ((0.5, 0.0), (1.0, 0.5), (0.5, 1.0), (0.0, 0.5))


@pytest.mark.parametrize("start", [0, 3])
def test_validate_corner_ratios__diamond_starts_at_either_top_left_tie(start: int) -> None:
    """NO-227: hình thoi xoay 45° hợp lệ; `(0.5, 0)` và `(0, 0.5)` hoà `x + y` nhỏ nhất nên đều nhận làm TL."""
    points = DIAMOND[start:] + DIAMOND[:start]
    assert validate_corner_ratios(points, min_area=MIN_AREA, eps=EPS) == points


def test_validate_corner_ratios__diamond_starting_at_the_far_side_is_rejected() -> None:
    """NO-227: hình thoi bắt đầu ở `(1, 0.5)` (đỉnh dưới-phải) vẫn bị loại."""
    _assert_field_corners(_rejected((DIAMOND[1], DIAMOND[2], DIAMOND[3], DIAMOND[0])))


def test_validate_corner_ratios__tie_within_eps_only() -> None:
    """Điểm đầu hơn `min(x + y)` không quá `eps` thì nhận, quá `eps` thì loại."""
    within = ((0.001, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 0.0005))
    assert validate_corner_ratios(within, min_area=MIN_AREA, eps=EPS) == within
    _assert_field_corners(_rejected(((0.0031, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 0.0005))))
