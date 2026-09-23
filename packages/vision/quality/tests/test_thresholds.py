"""Chép từng ca của `thresholds.test.ts:37-191`: đúng ngưỡng, dưới ngưỡng, dấu, `worst_level([])`.

Mọi số ở đây phải khớp `thresholds.py` với `src/domain/quality/thresholds.ts` — lệch
một ca là lệch mức hiển thị giữa BE và FE cho cùng một ảnh (T-04).
"""

import pytest

from packages.vision.quality.thresholds import (
    CONTRAST_ATTENTION_SCORE,
    CONTRAST_GOOD_SCORE,
    NOISE_ATTENTION_SCORE,
    NOISE_GOOD_SCORE,
    RESOLUTION_ATTENTION_SHORT_EDGE_PX,
    RESOLUTION_GOOD_SHORT_EDGE_PX,
    SKEW_ATTENTION_DEG,
    SKEW_GOOD_DEG,
    Level,
    classify_contrast,
    classify_noise,
    classify_resolution,
    classify_skew,
    worst_level,
)

# Ví dụ đặc tả nêu đích danh (thresholds.test.ts:30-54).
POOR_IMAGE_SHORT_EDGE_PX = 900
PASSING_SKEW_DEG = 0.2
STRAIGHTENABLE_SKEW_DEG = 3.4


def test_classify_resolution__poor_image_named_by_spec() -> None:
    """Ảnh 1.240 x 900 px → kém, theo cạnh ngắn 900 px."""
    assert classify_resolution(POOR_IMAGE_SHORT_EDGE_PX) == "poor"


def test_classify_resolution__good_examples_named_by_spec() -> None:
    """Từ 2.000 px trở lên → tốt."""
    assert classify_resolution(2000) == "good"
    assert classify_resolution(3200) == "good"


def test_classify_skew__spec_examples() -> None:
    """0,2 độ là đạt, 3,4 độ là cần nắn."""
    assert classify_skew(PASSING_SKEW_DEG) == "good"
    assert classify_skew(STRAIGHTENABLE_SKEW_DEG) == "attention"


def test_classify_resolution__good_at_exact_good_threshold() -> None:
    """Biên dùng `>=`: đúng 2.000 px thuộc mức tốt, không rơi xuống mức dưới."""
    assert classify_resolution(RESOLUTION_GOOD_SHORT_EDGE_PX) == "good"


def test_classify_resolution__attention_just_below_good_threshold() -> None:
    """Dưới biên một pixel đã rụng mức — chốt toán tử là `>=` chứ không phải `>`."""
    assert classify_resolution(RESOLUTION_GOOD_SHORT_EDGE_PX - 1) == "attention"


def test_classify_resolution__attention_at_exact_attention_threshold() -> None:
    """Biên dưới cũng `>=`: đúng 1.200 px vẫn là `attention`, chưa phải `poor`."""
    assert classify_resolution(RESOLUTION_ATTENTION_SHORT_EDGE_PX) == "attention"


def test_classify_resolution__poor_just_below_attention_threshold() -> None:
    """Dưới 1.200 px một pixel là `poor` — hai biên độ phân giải kiểm độc lập nhau."""
    assert classify_resolution(RESOLUTION_ATTENTION_SHORT_EDGE_PX - 1) == "poor"


def test_classify_resolution__poor_for_empty_image() -> None:
    """Cạnh ngắn 0 vẫn phân loại được, không nổ và không trả mức lạ."""
    assert classify_resolution(0) == "poor"


def test_classify_skew__good_at_exact_good_threshold() -> None:
    """Thang nghiêng dùng `<=` chứ không `>=` như ba thang kia: đúng 0,5 độ còn là tốt."""
    assert classify_skew(SKEW_GOOD_DEG) == "good"


def test_classify_skew__negative_and_positive_are_equal() -> None:
    """Phân loại theo trị tuyệt đối: nghiêng trái và phải cùng độ phải cho cùng mức."""
    assert classify_skew(-STRAIGHTENABLE_SKEW_DEG) == classify_skew(STRAIGHTENABLE_SKEW_DEG)
    assert classify_skew(-SKEW_GOOD_DEG) == "good"
    assert classify_skew(-SKEW_ATTENTION_DEG) == "poor"


def test_classify_skew__poor_at_exact_attention_threshold() -> None:
    """Biên 5 độ dùng `<` chứ không `<=`: đúng 5 độ đã là `poor` (`thresholds.ts:162-170`)."""
    assert classify_skew(SKEW_ATTENTION_DEG) == "poor"


def test_classify_skew__attention_just_below_attention_threshold() -> None:
    """Ngay dưới 5 độ vẫn là `attention` — chốt chiều toán tử ở ca 5 độ không phải tình cờ."""
    assert classify_skew(SKEW_ATTENTION_DEG - 0.1) == "attention"


def test_classify_skew__good_for_perfectly_straight_image() -> None:
    """Ảnh thẳng tuyệt đối (0 độ) là mức tốt, không phải ca biên bị bỏ sót."""
    assert classify_skew(0) == "good"


def test_classify_contrast__good_at_exact_good_threshold() -> None:
    """Biên `>=` ở 0,75: đúng ngưỡng thuộc mức tốt."""
    assert classify_contrast(CONTRAST_GOOD_SCORE) == "good"


def test_classify_contrast__attention_just_below_good_threshold() -> None:
    """Dưới 0,75 một phần trăm đã rụng mức — chốt `>=` chứ không `>`."""
    assert classify_contrast(CONTRAST_GOOD_SCORE - 0.01) == "attention"


def test_classify_contrast__attention_at_exact_attention_threshold() -> None:
    """Biên dưới 0,45 cũng `>=`: đúng ngưỡng vẫn là `attention`."""
    assert classify_contrast(CONTRAST_ATTENTION_SCORE) == "attention"


def test_classify_contrast__poor_just_below_attention_threshold() -> None:
    """Dưới 0,45 là `poor` — hai biên tương phản kiểm độc lập nhau."""
    assert classify_contrast(CONTRAST_ATTENTION_SCORE - 0.01) == "poor"


def test_classify_contrast__good_at_top_and_poor_at_bottom() -> None:
    """Hai đầu dải `[0, 1]` cho đúng hai mức ngoài cùng, không mức lạ nào lọt ra."""
    assert classify_contrast(1) == "good"
    assert classify_contrast(0) == "poor"


def test_classify_noise__good_at_exact_good_threshold() -> None:
    """Thang này chạy ngược: điểm càng thấp càng tốt."""
    assert classify_noise(NOISE_GOOD_SCORE) == "good"


def test_classify_noise__attention_just_above_good_threshold() -> None:
    """Trên 0,2 một phần trăm là `attention`: thang chạy ngược nên phải kiểm chiều đi lên."""
    assert classify_noise(NOISE_GOOD_SCORE + 0.01) == "attention"


def test_classify_noise__attention_at_exact_attention_threshold() -> None:
    """Biên 0,4 dùng `<=`: đúng ngưỡng vẫn là `attention`, chưa phải `poor`."""
    assert classify_noise(NOISE_ATTENTION_SCORE) == "attention"


def test_classify_noise__poor_just_above_attention_threshold() -> None:
    """Trên 0,4 là `poor` — chốt biên nhiễu không lệch một nấc so với FE."""
    assert classify_noise(NOISE_ATTENTION_SCORE + 0.01) == "poor"


def test_classify_noise__good_at_bottom_and_poor_at_top() -> None:
    """Hai đầu dải nhiễu cho đúng hai mức ngoài cùng của thang chạy ngược."""
    assert classify_noise(0) == "good"
    assert classify_noise(1) == "poor"


def test_worst_level__good_for_empty_list() -> None:
    """Không phát hiện nào thì báo cáo là `good` — mặc định mà `QualityReport.level` dựa vào."""
    assert worst_level([]) == "good"


def test_worst_level__stays_good_when_all_good() -> None:
    """Toàn `good` không bị nâng mức: hàm lấy mức tệ nhất chứ không cộng dồn."""
    assert worst_level(["good", "good", "good"]) == "good"


def test_worst_level__lifts_to_attention_with_one_attention() -> None:
    """Một mục `attention` đủ kéo cả báo cáo lên `attention`."""
    assert worst_level(["good", "attention", "good"]) == "attention"


@pytest.mark.parametrize(
    "levels",
    [["poor", "attention", "good"], ["good", "attention", "poor"]],
)
def test_worst_level__lifts_to_poor_regardless_of_order(levels: list[Level]) -> None:
    """`poor` thắng dù đứng đầu hay cuối: kết quả không phụ thuộc thứ tự duyệt."""
    assert worst_level(levels) == "poor"


def test_worst_level__single_element_list() -> None:
    """Danh sách một phần tử trả về chính mức đó, không bị hạ về mặc định `good`."""
    assert worst_level(["attention"]) == "attention"
