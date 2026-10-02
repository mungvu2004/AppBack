"""Số đo đối chiếu dự đoán với đáp án tổng hợp (khối [6] B6-04b): IoU mặt nạ, mAP@50, CER.

Trả số thô, chưa làm tròn — `evaluate.py` làm tròn ở một chỗ. IoU hộp tính theo lô
numpy `(n_pred, n_gt)` mỗi seed, không vòng Python lồng điểm ảnh. AP đúng thuật toán
`ultralytics.utils.metrics.compute_ap` (8.4.155): sentinel (0, 1) hai đầu, bao lồi
precision giảm dần phải→trái, nội suy 101 điểm `np.trapezoid` — viết lại bằng numpy,
không nhập `ultralytics` ở đây (khối [9]).
"""

import unicodedata
from collections.abc import Iterable, Sequence

import numpy as np
from numpy.typing import NDArray

from apps.ml.runtime.errors import MODEL_FORMAT_UNSUPPORTED
from packages.messaging.tasks import PermanentError
from packages.ml_contracts.artifacts import DetectionPx, TextPx
from packages.vision.walls.metrics import mask_overlap

__all__ = ["cer", "map50", "mask_iou", "normalize_ocr_text"]

_IOU_THRESHOLD = 0.5


def mask_iou(pairs: Iterable[tuple[NDArray[np.bool_], NDArray[np.bool_]]]) -> float:
    """IoU cộng dồn `sum(P and G) / sum(P or G)` trên cả tập cặp; hợp 0 → 1.0; khác hình → `PermanentError`."""
    intersection = 0
    union = 0
    for pred, truth in pairs:
        try:
            sample_intersection, sample_union = mask_overlap(pred, truth)
        except ValueError as exc:
            raise PermanentError(MODEL_FORMAT_UNSUPPORTED) from exc
        intersection += sample_intersection
        union += sample_union
    if union == 0:
        return 1.0
    return intersection / union


def _box_iou(pred: NDArray[np.float64], gt: NDArray[np.float64]) -> NDArray[np.float64]:
    """IoU theo lô `(n_pred, n_gt)`, cột `x_min, y_min, x_max, y_max`; hộp rỗng trả mảng rỗng."""
    px1, py1, px2, py2 = pred[:, 0:1], pred[:, 1:2], pred[:, 2:3], pred[:, 3:4]
    gx1, gy1, gx2, gy2 = gt[:, 0], gt[:, 1], gt[:, 2], gt[:, 3]
    inter_w = np.clip(np.minimum(px2, gx2) - np.maximum(px1, gx1), 0, None)
    inter_h = np.clip(np.minimum(py2, gy2) - np.maximum(py1, gy1), 0, None)
    inter = inter_w * inter_h
    pred_area = (px2 - px1) * (py2 - py1)
    gt_area = (gx2 - gx1) * (gy2 - gy1)
    union = pred_area + gt_area - inter
    result: NDArray[np.float64] = np.divide(inter, union, out=np.zeros_like(inter), where=union > 0)
    return result


def _ap(recall: NDArray[np.float64], precision: NDArray[np.float64]) -> float:
    """Diện tích dưới đường precision-recall bao lồi, nội suy 101 điểm (`compute_ap` ultralytics 8.4.155,
    `ultralytics/utils/metrics.py` hàm `compute_ap`, dòng thêm sentinel trùng `recall[-1]` trước mốc `1.0`)."""
    last_recall = recall[-1] if len(recall) else 1.0
    mrec = np.concatenate(([0.0], recall, [last_recall], [1.0]))
    mpre = np.concatenate(([1.0], precision, [0.0], [0.0]))
    mpre = np.flip(np.maximum.accumulate(np.flip(mpre)))
    x = np.linspace(0.0, 1.0, 101)
    return float(np.trapezoid(np.interp(x, mrec, mpre), x))


def _boxes_of(dets: Sequence[DetectionPx], label: str) -> NDArray[np.float64]:
    """Hộp `(n, 4)` của các phát hiện mang `label`; không có → mảng `(0, 4)`."""
    rows = [(d.box.x_min, d.box.y_min, d.box.x_max, d.box.y_max) for d in dets if d.label == label]
    return np.array(rows, dtype=np.float64) if rows else np.zeros((0, 4), dtype=np.float64)


def _ap_for_label(samples: Sequence[tuple[Sequence[DetectionPx], Sequence[DetectionPx]]], label: str) -> float:
    """AP một nhãn: TP/FP theo IoU≥0.5 khớp đáp án **chưa khớp** cùng seed, sắp confidence giảm."""
    gt_boxes_by_seed = [_boxes_of(gts, label) for _, gts in samples]
    total_gt = sum(boxes.shape[0] for boxes in gt_boxes_by_seed)
    if total_gt == 0:
        return 0.0
    entries: list[tuple[float, int, int, NDArray[np.float64]]] = []
    for seed_idx, (preds, _gts) in enumerate(samples):
        for pred_idx, pred in enumerate(preds):
            if pred.label == label:
                box = np.array([pred.box.x_min, pred.box.y_min, pred.box.x_max, pred.box.y_max])
                entries.append((pred.confidence, seed_idx, pred_idx, box))
    if not entries:
        return 0.0
    entries.sort(key=lambda e: (-e[0], e[1], e[2]))
    matched = [np.zeros(boxes.shape[0], dtype=bool) for boxes in gt_boxes_by_seed]
    tp = np.zeros(len(entries))
    for i, (_conf, seed_idx, _pred_idx, box) in enumerate(entries):
        gt_boxes = gt_boxes_by_seed[seed_idx]
        if gt_boxes.shape[0] == 0:
            continue
        ious = _box_iou(box[np.newaxis, :], gt_boxes)[0]
        ious = np.where(matched[seed_idx], -1.0, ious)
        best = int(np.argmax(ious))
        if ious[best] >= _IOU_THRESHOLD:
            tp[i] = 1.0
            matched[seed_idx][best] = True
    cum_tp = np.cumsum(tp)
    cum_fp = np.cumsum(1.0 - tp)
    recall = cum_tp / total_gt
    precision = cum_tp / np.clip(cum_tp + cum_fp, 1, None)
    return _ap(recall, precision)


def map50(samples: Sequence[tuple[Sequence[DetectionPx], Sequence[DetectionPx]]]) -> float:
    """mAP@0.5 trung bình theo nhãn **có đáp án**; không đáp án nào → 0.0; nhãn chỉ có dự đoán bị bỏ."""
    gt_labels = sorted({det.label for _, gts in samples for det in gts})
    if not gt_labels:
        return 0.0
    return float(np.mean([_ap_for_label(samples, label) for label in gt_labels]))


def normalize_ocr_text(s: str) -> str:
    """NFKC → bỏ dấu (NFD bỏ `Mn`, `đ/Đ`→`d/D`) → `casefold` → gom khoảng trắng."""
    s = unicodedata.normalize("NFKC", s).replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return " ".join(s.casefold().split())


def _levenshtein(a: str, b: str) -> int:
    """Khoảng cách Levenshtein (chèn/xoá/thay phí 1), DP hai hàng `O(len(b))` bộ nhớ."""
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i] + [0] * len(b)
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
        prev = curr
    return prev[-1]


def _best_match(gt_box: NDArray[np.float64], pred_boxes: NDArray[np.float64], used: list[bool]) -> int:
    """Chỉ số dự đoán **chưa dùng** IoU lớn nhất ≥ 0.5 với `gt_box`; không có → `-1`."""
    if pred_boxes.shape[0] == 0:
        return -1
    ious = _box_iou(gt_box[np.newaxis, :], pred_boxes)[0]
    ious = np.array([iou if not used[i] else -1.0 for i, iou in enumerate(ious)])
    best = int(np.argmax(ious))
    return best if ious[best] >= _IOU_THRESHOLD else -1


def cer(samples: Sequence[tuple[Sequence[TextPx], Sequence[TextPx]]]) -> float:
    """CER cộng dồn: mỗi đáp án (sắp `(y1, x1)`) khớp dự đoán chưa dùng IoU hộp lớn nhất ≥ 0.5."""
    total_errors = 0
    total_gt_len = 0
    for preds, gts in samples:
        pred_list = list(preds)
        pred_boxes = (
            np.array([(p.box.x_min, p.box.y_min, p.box.x_max, p.box.y_max) for p in pred_list], dtype=np.float64)
            if pred_list
            else np.zeros((0, 4), dtype=np.float64)
        )
        used = [False] * len(pred_list)
        for gt in sorted(gts, key=lambda g: (g.box.y_min, g.box.x_min)):
            gt_box = np.array([gt.box.x_min, gt.box.y_min, gt.box.x_max, gt.box.y_max])
            match_idx = _best_match(gt_box, pred_boxes, used)
            gt_norm = normalize_ocr_text(gt.text)
            pred_norm = ""
            if match_idx >= 0:
                used[match_idx] = True
                pred_norm = normalize_ocr_text(pred_list[match_idx].text)
            total_errors += _levenshtein(gt_norm, pred_norm)
            total_gt_len += len(gt_norm)
        for i, pred in enumerate(pred_list):
            if not used[i]:
                total_errors += len(normalize_ocr_text(pred.text))
    return total_errors / max(1, total_gt_len)
