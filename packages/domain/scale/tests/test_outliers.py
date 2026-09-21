"""Trung vị và MAD: chép các test `outliers` của `src/domain/units/__tests__/scale.test.ts:308-349`."""

import pytest

from packages.domain.scale import SCALE_THRESHOLDS, OutlierSplit, median, split_outliers

THRESHOLD = SCALE_THRESHOLDS.outlier_rejection


def test_median_of_odd_count() -> None:
    """Số lẻ phần tử → phần tử giữa."""
    assert median([3, 1, 2]) == 2


def test_median_of_even_count() -> None:
    """Số chẵn → trung bình hai phần tử giữa."""
    assert median([1, 2, 3, 4]) == 2.5


def test_median_of_empty() -> None:
    """Rỗng → không có trung vị."""
    assert median([]) is None


def test_identical_samples_are_all_kept() -> None:
    """Mọi mẫu bằng nhau → không loại mẫu nào, MAD bằng 0."""
    assert split_outliers([12, 12, 12, 12], THRESHOLD) == OutlierSplit((0, 1, 2, 3), (), 12, 0)


def test_stray_sample_among_identical_ones_is_caught() -> None:
    """MAD bằng 0 thì trung bình độ lệch thay vào, nên một mẫu lạc vẫn bị bắt."""
    split = split_outliers([12, 12, 12, 40], THRESHOLD)
    assert (split.kept_indices, split.rejected_indices) == ((0, 1, 2), (3,))


def test_rejected_positions_trace_back() -> None:
    """Trả chỉ số theo thứ tự gốc; MAD của `[10, 12, 14]` quanh 12 là 2."""
    assert split_outliers([12, 40, 12.1, 3, 11.9], THRESHOLD).rejected_indices == (1, 3)
    assert split_outliers([10, 12, 14], THRESHOLD).absolute_deviation == 2


def test_empty_split() -> None:
    """Không mẫu → không trung vị, MAD 0."""
    assert split_outliers([], THRESHOLD) == OutlierSplit((), (), None, 0.0)


@pytest.mark.parametrize("threshold", [0, -1, float("nan"), float("inf")])
def test_threshold_must_be_positive_and_finite(threshold: float) -> None:
    """Ngưỡng ≤ 0 hay không hữu hạn → `ValueError`."""
    with pytest.raises(ValueError, match="ngưỡng"):
        split_outliers([1, 2, 3], threshold)
