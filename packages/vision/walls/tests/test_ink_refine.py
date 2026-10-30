"""Nắn tim/bề dày tường theo nét mực (UX41-B2, U19) trên trang tổng hợp vẽ tay trong test.

Đáp án biết trước: hai nét 2 px có tim cách nhau 12 px → bề dày 12 (không phải 14 mép ngoài-mép
ngoài của mặt nạ); dải tô đặc 10 px → 10; đường kích thước song song không kéo tường; trang nhạt
nhiễu → giữ số đo mặt nạ.
"""

import math

import cv2
import numpy as np
import pytest
from numpy.typing import NDArray

from packages.vision.walls.ink_refine import AxisWall, Frame, fit_profile, refine_line
from packages.vision.walls.vectorize import vectorize_with_stats

SHAPE = (240, 320)
"""`(cao, rộng)` của trang mẫu."""
STRAIGHT = Frame(0.0, ((SHAPE[1] - 1) / 2.0, (SHAPE[0] - 1) / 2.0))
"""Bản vẽ thẳng trục ảnh."""
CENTRE = 106.5
"""Tim tường ngang mẫu: nét trên ở hàng 100-101, nét dưới ở hàng 112-113 (tim nét 100,5 và 112,5)."""


def _page() -> NDArray[np.uint8]:
    """Giấy trắng."""
    return np.full(SHAPE, 255, np.uint8)


def _outline_wall(page: NDArray[np.uint8]) -> None:
    """Tường ngang vẽ hai nét 2 px, tim nét cách nhau 12 px, chạy x = 40..280."""
    page[100:102, 40:281] = 0
    page[112:114, 40:281] = 0


def _wall(value: float = CENTRE, thickness: float = 14.0, lo: float = 40.0, hi: float = 280.0) -> AxisWall:
    """Đoạn ngang như `vectorize` thấy trên mặt nạ phủ kín hai nét (mép ngoài-mép ngoài 14 px)."""
    return AxisWall("h", value, lo, hi, thickness)


def test_outline_wall_thickness_is_stroke_centre_distance() -> None:
    """Hai nét 2 px tim cách 12 px: bề dày 12 (mặt nạ đo 14), tim giữ giữa hai nét."""
    page = _page()
    _outline_wall(page)
    fit = refine_line(page, [_wall()], STRAIGHT)
    assert fit is not None
    assert fit.value == pytest.approx(CENTRE, abs=0.3)
    assert fit.thicknesses[0] == pytest.approx(12.0, abs=0.3)


def test_filled_wall_keeps_the_band_width() -> None:
    """Dải tô đặc 10 px (hàng 100-109): bề dày 10, tim 104,5 dù mặt nạ báo dày 12 và lệch 1 px."""
    page = _page()
    page[100:110, 40:281] = 0
    fit = refine_line(page, [_wall(value=105.5, thickness=12.0)], STRAIGHT)
    assert fit is not None
    assert fit.value == pytest.approx(104.5, abs=0.3)
    assert fit.thicknesses[0] == pytest.approx(10.0, abs=0.3)


def test_parallel_dimension_line_does_not_pull_the_wall() -> None:
    """Đường kích thước 1 px cách tim 11 px (trong cửa sổ ±1 bề dày): tường vẫn 12 px, tim không dời."""
    page = _page()
    _outline_wall(page)
    page[117, 20:300] = 0
    fit = refine_line(page, [_wall()], STRAIGHT)
    assert fit is not None
    assert fit.value == pytest.approx(CENTRE, abs=0.3)
    assert fit.thicknesses[0] == pytest.approx(12.0, abs=0.3)


def test_noisy_low_contrast_page_leaves_the_wall_unchanged() -> None:
    """Nét mờ (tương phản 30) trên giấy xám nhiễu: không đủ chứng cứ → `None` (giữ mặt nạ)."""
    rng = np.random.default_rng(7)
    page = np.full(SHAPE, 180.0) + rng.normal(0.0, 12.0, SHAPE)
    page[100:102, 40:281] -= 30
    page[112:114, 40:281] -= 30
    assert refine_line(np.clip(page, 0, 255).astype(np.uint8), [_wall()], STRAIGHT) is None


def test_blank_page_and_far_ink_leave_the_wall_unchanged() -> None:
    """Trang trắng (không lát nào đọc được) và nét nằm xa hơn ½ bề dày khỏi tim mặt nạ: `None`."""
    assert refine_line(_page(), [_wall()], STRAIGHT) is None
    page = _page()
    _outline_wall(page)
    assert refine_line(page, [_wall(value=CENTRE + 9.0)], STRAIGHT) is None


def test_short_member_keeps_its_mask_thickness() -> None:
    """Đường hai đoạn: đoạn dài đủ lát thì nắn, đoạn 6 px không đủ 3 lát thì giữ bề dày mặt nạ."""
    page = _page()
    _outline_wall(page)
    fit = refine_line(page, [_wall(), _wall(lo=284.0, hi=290.0)], STRAIGHT)
    assert fit is not None
    assert fit.thicknesses[0] == pytest.approx(12.0, abs=0.3)
    assert fit.thicknesses[1] is None


def test_line_members_of_different_kinds_share_one_centre() -> None:
    """Một trục: đoạn viền hai nét (12) và đoạn tô đặc 6 px cùng tim → cả đường nắn, mỗi đoạn bề dày riêng."""
    page = _page()
    page[100:102, 40:151] = 0
    page[112:114, 40:151] = 0
    page[104:110, 170:281] = 0
    fit = refine_line(page, [_wall(hi=150.0), _wall(lo=170.0, thickness=8.0)], STRAIGHT)
    assert fit is not None
    assert fit.value == pytest.approx(CENTRE, abs=0.3)
    assert fit.thicknesses[0] == pytest.approx(12.0, abs=0.3)
    assert fit.thicknesses[1] == pytest.approx(6.0, abs=0.3)


def test_fit_profile_ignores_bands_cut_by_the_window() -> None:
    """Dải tối chạm mép cửa sổ lấy mẫu bị cắt cụt: không làm ứng viên, chỉ còn dải giữa."""
    offsets = np.arange(-8.0, 8.5, 0.5)
    profile = np.full(offsets.shape, 255.0)
    profile[:3] = 0.0
    profile[14:19] = 0.0
    fit = fit_profile(profile, offsets, 3.0)
    assert fit is not None
    assert fit[0] == pytest.approx(0.0, abs=0.3)


def test_rotated_drawing_is_sampled_in_its_own_frame() -> None:
    """Bản vẽ xoay 2°: lấy mẫu trong hệ trục bản vẽ thì vẫn đọc ra tim và bề dày như bản thẳng."""
    straight = _page()
    _outline_wall(straight)
    frame = Frame(2.0, STRAIGHT.centre)
    ys, xs = np.mgrid[0 : SHAPE[0], 0 : SHAPE[1]].astype(np.float64)
    cos, sin = math.cos(math.radians(-2.0)), math.sin(math.radians(-2.0))
    cx, cy = frame.centre
    fx = cx + (xs - cx) * cos - (ys - cy) * sin
    fy = cy + (xs - cx) * sin + (ys - cy) * cos
    page = cv2.remap(straight, fx.astype(np.float32), fy.astype(np.float32), cv2.INTER_LINEAR, borderValue=(255.0,))
    fit = refine_line(np.asarray(page, np.uint8), [_wall()], frame)
    assert fit is not None
    assert fit.value == pytest.approx(CENTRE, abs=0.4)
    assert fit.thicknesses[0] == pytest.approx(12.0, abs=0.4)


CORNERS = ((56.5, 46.5), (244.5, 46.5), (56.5, 174.5), (244.5, 174.5))
"""Giao tim bốn tường của `_room` (giữa hai nét)."""


def _room() -> tuple[NDArray[np.bool_], NDArray[np.uint8]]:
    """Phòng tường vẽ hai nét 2 px (tim nét cách 12) và mặt nạ phủ kín mép ngoài-mép ngoài (14 px)."""
    page = _page()
    page[40:182, 50:252] = 0
    page[42:180, 52:250] = 255
    page[52:170, 62:240] = 0
    page[54:168, 64:238] = 255
    mask = np.zeros(SHAPE, bool)
    mask[40:182, 50:252] = True
    mask[54:168, 64:238] = False
    return mask, page


def test_vectorize_with_page_reads_stroke_centres_and_keeps_corners() -> None:
    """Không trang thì bề dày ~14 (mép ngoài); có trang thì ~12 và mọi đầu mút vẫn nằm trên bốn góc tim."""
    mask, page = _room()
    plain = vectorize_with_stats(mask).walls
    refined = vectorize_with_stats(mask, page).walls
    assert len(refined) == len(plain) == 4
    assert all(wall.thickness_px > 13.0 for wall in plain)
    assert all(wall.thickness_px == pytest.approx(12.0, abs=0.4) for wall in refined)
    for point in (point for wall in refined for point in (wall.start, wall.end)):
        assert min(math.dist(point, corner) for corner in CORNERS) <= 0.6


def test_vectorize_rejects_a_page_of_another_size() -> None:
    """Ảnh xám khác khổ mặt nạ là lỗi người gọi: `ValueError`, không lấy mẫu lệch."""
    mask, _ = _room()
    with pytest.raises(ValueError, match="page_gray"):
        vectorize_with_stats(mask, np.full((10, 10), 255, np.uint8))
