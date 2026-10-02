"""Test `metrics.{mask_iou, map50, cer, normalize_ocr_text}` (khối [8] "Số đo")."""

import numpy as np
import pytest

from apps.ml.ml_eval import metrics as m
from packages.messaging.tasks import PermanentError
from packages.ml_contracts.artifacts import BoxPx, DetectionPx, TextPx


def _box(x1: float, y1: float, x2: float, y2: float) -> BoxPx:
    """Hộp thẳng trục tiện cho test."""
    return BoxPx(x_min=x1, y_min=y1, x_max=x2, y_max=y2)


def _det(label: str, box: BoxPx, conf: float) -> DetectionPx:
    """Một phát hiện tiện cho test."""
    return DetectionPx(label=label, box=box, confidence=conf)


def test_mask_iou_empty_pairs_is_one() -> None:
    """Không cặp nào → hợp 0 → `1.0`."""
    assert m.mask_iou([]) == 1.0


def test_mask_iou_blank_masks_is_one() -> None:
    """Hai mặt nạ rỗng (hợp 0) → `1.0`."""
    blank = np.zeros((4, 4), dtype=np.bool_)
    assert m.mask_iou([(blank, blank)]) == 1.0


def test_mask_iou_hand_computed() -> None:
    """2x2 vuông: dự đoán {0,1}, đáp án {1,2} trên hàng 8 ô → giao 1, hợp 3 → 1/3."""
    pred = np.array([True, True, False, False])
    truth = np.array([False, True, True, False])
    assert m.mask_iou([(pred, truth)]) == pytest.approx(1 / 3)


def test_mask_iou_mismatched_shape_raises_model_format_unsupported() -> None:
    """Khác hình → `PermanentError(MODEL_FORMAT_UNSUPPORTED)`."""
    pred = np.zeros((2, 2), dtype=np.bool_)
    truth = np.zeros((3, 3), dtype=np.bool_)
    with pytest.raises(PermanentError) as exc:
        m.mask_iou([(pred, truth)])
    assert exc.value.code == "MODEL_FORMAT_UNSUPPORTED"


def test_map50_perfect_match_is_0_995() -> None:
    """Một seed, một đáp án, dự đoán khớp hoàn toàn → AP = 0.995 (sentinel + nội suy 101 điểm)."""
    gt = _det("door", _box(0, 0, 10, 10), 1.0)
    pred = _det("door", _box(0, 0, 10, 10), 0.9)
    assert m.map50([((pred,), (gt,))]) == pytest.approx(0.995)


def test_map50_false_positive_before_true_positive() -> None:
    """FP điểm cao sắp trước TP: entries=[(FP,conf=0.9),(TP,conf=0.5)] → recall=[0,0.5,1], precision=[0,0,0.5]."""
    gt = _det("door", _box(0, 0, 10, 10), 1.0)
    fp_pred = _det("door", _box(100, 100, 110, 110), 0.9)
    tp_pred = _det("door", _box(0, 0, 10, 10), 0.5)
    recall = np.array([0.0, 0.0, 1.0])
    precision = np.array([0.0, 0.0, 0.5])
    expected = m._ap(recall, precision)
    assert m.map50([((fp_pred, tp_pred), (gt,))]) == pytest.approx(expected)


def test_map50_second_pred_on_same_gt_is_false_positive() -> None:
    """Hai dự đoán cùng khớp một đáp án: cái confidence cao hơn là TP, cái sau là FP."""
    gt = _det("door", _box(0, 0, 10, 10), 1.0)
    first = _det("door", _box(0, 0, 10, 10), 0.9)
    second = _det("door", _box(0, 0, 10, 10), 0.8)
    recall = np.array([1.0, 1.0])
    precision = np.array([1.0, 0.5])
    expected = m._ap(recall, precision)
    assert m.map50([((first, second), (gt,))]) == pytest.approx(expected)


def test_map50_wrong_label_or_low_iou_is_false_positive() -> None:
    """Nhãn khác hay IoU 0.49 (không đạt 0.5) đều là FP → AP = 0.0 (không TP nào)."""
    gt = _det("door", _box(0, 0, 10, 10), 1.0)
    wrong_label = _det("window", _box(0, 0, 10, 10), 0.9)
    assert m.map50([((wrong_label,), (gt,))]) == 0.0


def test_map50_prediction_only_label_excluded_from_average() -> None:
    """Nhãn chỉ có dự đoán (không đáp án nào) không vào trung bình: chỉ nhãn có đáp án mới tính."""
    gt = _det("door", _box(0, 0, 10, 10), 1.0)
    pred_matching = _det("door", _box(0, 0, 10, 10), 0.9)
    pred_other_label = _det("window", _box(50, 50, 60, 60), 0.9)
    only_door = m.map50([((pred_matching,), (gt,))])
    with_extra_label = m.map50([((pred_matching, pred_other_label), (gt,))])
    assert with_extra_label == pytest.approx(only_door)


def test_map50_no_ground_truth_is_zero() -> None:
    """Không đáp án nào → `0.0`."""
    pred = _det("door", _box(0, 0, 10, 10), 0.9)
    assert m.map50([((pred,), ())]) == 0.0


def test_ap_matches_ultralytics_compute_ap() -> None:
    """`_ap` khớp `ultralytics.utils.metrics.compute_ap` trên 20 đường cong tất định, lệch ≤ 1e-9.

    `ultralytics` nằm trong bản khoá nên test không bao giờ bị bỏ (K24); cờ ngoại tuyến đặt bằng
    `prepare_ultralytics()` của trainer — một chỗ duy nhất trong repo biết bộ cờ `YOLO_*` (R-02).
    """
    from apps.ml.training_yolo.trainer import prepare_ultralytics

    prepare_ultralytics()
    from ultralytics.utils.metrics import compute_ap

    for seed in range(20):
        rng = np.random.default_rng(seed)
        n = int(rng.integers(1, 30))
        recall = np.sort(rng.random(n))
        precision = np.sort(rng.random(n))[::-1]
        expected, _mpre, _mrec = compute_ap(list(recall), list(precision))
        actual = m._ap(recall, precision)
        assert actual == pytest.approx(expected, abs=1e-9)


def test_normalize_ocr_text_nfkc_diacritics_case_whitespace() -> None:
    """NFKC → bỏ dấu (đ→d) → casefold → gom khoảng trắng."""
    assert m.normalize_ocr_text("PHÒNG NGỦ  Đẹp") == "phong ngu dep"


def _text(s: str, box: BoxPx) -> TextPx:
    """Một chữ đọc được tiện cho test."""
    return TextPx(text=s, box=box, confidence=1.0)


def test_cer_exact_match_is_zero() -> None:
    """`3600`/`3600` → 0."""
    gt = _text("3600", _box(0, 0, 10, 10))
    pred = _text("3600", _box(0, 0, 10, 10))
    assert m.cer([((pred,), (gt,))]) == 0.0


def test_cer_partial_match() -> None:
    """`3600`/`360`: lev=1, len(gt)=4 → 0.25."""
    gt = _text("3600", _box(0, 0, 10, 10))
    pred = _text("360", _box(0, 0, 10, 10))
    assert m.cer([((pred,), (gt,))]) == pytest.approx(0.25)


def test_cer_extra_prediction_adds_its_length() -> None:
    """Dự đoán thừa (không khớp đáp án nào) cộng thẳng độ dài của nó vào tử số."""
    gt = _text("3600", _box(0, 0, 10, 10))
    pred = _text("3600", _box(0, 0, 10, 10))
    extra = _text("AB", _box(100, 100, 110, 110))
    assert m.cer([((pred, extra), (gt,))]) == pytest.approx(2 / 4)


def test_cer_unmatched_ground_truth_counts_every_character() -> None:
    """Đáp án không có dự đoán nào IoU ≥ 0,5 → so với chuỗi rỗng, cả độ dài vào tử số (nhánh `match_idx < 0`)."""
    gt = _text("3600", _box(0, 0, 10, 10))
    far = _text("3600", _box(500, 500, 510, 510))
    assert m.cer([((far,), (gt,))]) == pytest.approx((4 + 4) / 4)


def test_cer_vietnamese_diacritics_normalized_equal() -> None:
    """`PHÒNG NGỦ`/`PHONG NGU` chuẩn hoá về cùng chuỗi → 0."""
    gt = _text("PHÒNG NGỦ", _box(0, 0, 10, 10))
    pred = _text("PHONG NGU", _box(0, 0, 10, 10))
    assert m.cer([((pred,), (gt,))]) == 0.0


def test_cer_empty_ground_truth_denominator_is_one() -> None:
    """Không đáp án nào, có dự đoán thừa → mẫu số `max(1, 0) == 1`."""
    extra = _text("AB", _box(0, 0, 10, 10))
    assert m.cer([((extra,), ())]) == pytest.approx(2.0)
