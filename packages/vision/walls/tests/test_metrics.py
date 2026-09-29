"""`mask_overlap`/`mask_iou`: giao/hợp điểm ảnh, khác hình → `ValueError` (B5-02 [8])."""

import numpy as np
import pytest

from packages.vision.walls.metrics import mask_iou, mask_overlap


def test_mask_iou_identical_masks_is_one() -> None:
    """Hai mặt nạ trùng nhau → IoU = 1."""
    mask = np.zeros((10, 10), dtype=np.bool_)
    mask[2:5, 2:5] = True
    assert mask_iou(mask, mask.copy()) == 1.0


def test_mask_iou_disjoint_masks_is_zero() -> None:
    """Hai mặt nạ rời nhau (giao rỗng) → IoU = 0."""
    a = np.zeros((10, 10), dtype=np.bool_)
    b = np.zeros((10, 10), dtype=np.bool_)
    a[0:3, 0:3] = True
    b[7:10, 7:10] = True
    assert mask_iou(a, b) == 0.0


def test_mask_iou_half_overlap_is_half() -> None:
    """Nửa trái so với cả ảnh: giao = nửa trái, hợp = cả ảnh → IoU = 0,5."""
    left = np.zeros((10, 10), dtype=np.bool_)
    left[:, :5] = True
    full = np.ones((10, 10), dtype=np.bool_)
    assert mask_iou(left, full) == pytest.approx(0.5)


def test_mask_iou_both_empty_is_one() -> None:
    """Hai mặt nạ rỗng (hợp = 0) → coi là khớp tuyệt đối, IoU = 1."""
    empty = np.zeros((10, 10), dtype=np.bool_)
    assert mask_iou(empty, empty.copy()) == 1.0


def test_mask_iou_shape_mismatch_raises() -> None:
    """Khác hình → `ValueError`."""
    a = np.zeros((10, 10), dtype=np.bool_)
    b = np.zeros((5, 5), dtype=np.bool_)
    with pytest.raises(ValueError, match="hình"):
        mask_iou(a, b)


def test_mask_overlap_shape_mismatch_raises() -> None:
    """`mask_overlap` cũng chặn khác hình bằng `ValueError`."""
    a = np.zeros((10, 10), dtype=np.bool_)
    b = np.zeros((5, 5), dtype=np.bool_)
    with pytest.raises(ValueError, match="hình"):
        mask_overlap(a, b)


def test_mask_overlap_counts() -> None:
    """Giao/hợp trả đúng số điểm ảnh, không chỉ tỉ số."""
    a = np.zeros((10, 10), dtype=np.bool_)
    b = np.zeros((10, 10), dtype=np.bool_)
    a[0:4, 0:4] = True
    b[2:6, 2:6] = True
    intersection, union = mask_overlap(a, b)
    assert (intersection, union) == (4, 28)
