"""Test `decode_tile`/`merge_candidates` bằng tensor tay: ngưỡng, kẹp, NMS, nối lát (khối [8])."""

from collections.abc import Sequence

import numpy as np

from apps.ml.objects.detector import CONFIDENCE_MIN, MAX_DETECTIONS, _Candidates, decode_tile, merge_candidates
from apps.ml.objects.labels import COCO_LABELS
from apps.ml.objects.tests.onnx_models import yolo_output
from apps.ml.objects.tiles import Window


def _candidates(
    rows: Sequence[tuple[tuple[float, float, float, float], int, float, tuple[float, float, float, float]]],
) -> _Candidates:
    """Dựng `_Candidates` tay từ `(box, label_idx, score, tile)` cho test hậu xử lý."""
    boxes = np.array([row[0] for row in rows], dtype=np.float64).reshape(-1, 4)
    classes = np.array([row[1] for row in rows], dtype=np.int64)
    scores = np.array([row[2] for row in rows], dtype=np.float64)
    tiles = np.array([row[3] for row in rows], dtype=np.float64).reshape(-1, 4)
    return _Candidates(boxes=boxes, scores=scores, classes=classes, tiles=tiles)


def test_decode_tile__drops_below_confidence_min() -> None:
    """Điểm dưới `CONFIDENCE_MIN` bị bỏ, không sinh ứng viên."""
    output = yolo_output([(50, 50, 20, 20, 0, CONFIDENCE_MIN - 0.05)], nc=1)
    assert len(decode_tile(output, Window(0, 0, 640, 640), ("door",), 640)) == 0


def test_decode_tile__coco_threshold_stricter_than_default() -> None:
    """`labels is COCO_LABELS` dùng ngưỡng `COCO_CONFIDENCE_MIN` (chặt hơn `CONFIDENCE_MIN`)."""
    cls = next(i for i, label in enumerate(COCO_LABELS) if label is not None)
    output = yolo_output([(50, 50, 20, 20, cls, 0.4)], nc=80)
    window = Window(0, 0, 640, 640)
    assert len(decode_tile(output, window, COCO_LABELS, 640)) == 0
    other_labels = tuple(label if label is not None else "other" for label in COCO_LABELS)
    assert len(decode_tile(output, window, other_labels, 640)) == 1


def test_decode_tile__drops_unmapped_coco_class() -> None:
    """Lớp COCO không có đích trong `COCO_LABELS` (`None`) bị bỏ dù điểm cao."""
    cls = next(i for i, label in enumerate(COCO_LABELS) if label is None)
    output = yolo_output([(50, 50, 20, 20, cls, 0.9)], nc=80)
    assert len(decode_tile(output, Window(0, 0, 640, 640), COCO_LABELS, 640)) == 0


def test_decode_tile__drops_nan_box() -> None:
    """Toạ độ `NaN` (hỏng số) bị bỏ, không lọt qua mặt nạ `isfinite`."""
    output = yolo_output([(50, 50, 20, 20, 0, 0.9)], nc=1)
    output[0, 0, 0] = np.nan
    assert len(decode_tile(output, Window(0, 0, 640, 640), ("door",), 640)) == 0


def test_decode_tile__clips_box_into_real_tile_area() -> None:
    """Hộp tràn ra ngoài phần thật của lát bị kẹp về đúng mép lát (không phải mép đệm)."""
    output = yolo_output([(35, 10, 20, 10, 0, 0.9)], nc=1)
    window = Window(0, 0, 40, 40)
    candidates = decode_tile(output, window, ("door",), 64)
    assert len(candidates) == 1
    assert candidates.boxes[0, 2] == 40.0
    assert candidates.boxes[0, 0] == 25.0


def test_decode_tile__drops_box_below_minimum_side() -> None:
    """Cạnh hộp sau kẹp < 2px bị bỏ (không phải phát hiện thật)."""
    output = yolo_output([(50, 50, 1.0, 1.0, 0, 0.9)], nc=1)
    assert len(decode_tile(output, Window(0, 0, 640, 640), ("door",), 640)) == 0


def test_merge_candidates__joins_overlapping_boxes_from_different_tiles() -> None:
    """Điều kiện (a) khối [6] bước 4: giao/diện tích hộp nhỏ ≥ `MERGE_OVERLAP` (IoU thấp nên NMS không bỏ)."""
    tile_a, tile_b = (0.0, 0.0, 640.0, 640.0), (0.0, 0.0, 100.0, 100.0)
    candidates = _candidates(
        [
            ((0.0, 0.0, 100.0, 100.0), 0, 0.9, tile_a),
            ((10.0, 10.0, 40.0, 40.0), 0, 0.6, tile_b),
        ]
    )
    result = merge_candidates(candidates, page_w=1280, page_h=640)
    assert len(result) == 1
    assert tuple(result.boxes[0]) == (0.0, 0.0, 100.0, 100.0)
    assert result.scores[0] == 0.9


def test_merge_candidates__nms_drops_same_label_keeps_different_label() -> None:
    """NMS bỏ hộp cùng nhãn IoU cao (điểm thấp hơn); giữ nhãn khác dù cùng vị trí."""
    tile = (0.0, 0.0, 640.0, 640.0)
    candidates = _candidates(
        [
            ((10.0, 10.0, 50.0, 50.0), 0, 0.9, tile),
            ((12.0, 12.0, 52.0, 52.0), 0, 0.5, tile),
            ((12.0, 12.0, 52.0, 52.0), 1, 0.6, tile),
        ]
    )
    result = merge_candidates(candidates, page_w=640, page_h=640)
    kept = {(int(c), round(float(s), 2)) for c, s in zip(result.classes, result.scores, strict=True)}
    assert kept == {(0, 0.9), (1, 0.6)}


def test_merge_candidates__joins_chain_across_three_tiles() -> None:
    """Nối dây chuyền: ba mảnh vắt hai ranh lát → một hộp bao (thành phần liên thông một lượt)."""
    tile_a, tile_b, tile_c = (0.0, 0.0, 640.0, 640.0), (640.0, 0.0, 640.0, 640.0), (1280.0, 0.0, 640.0, 640.0)
    candidates = _candidates(
        [
            ((500.0, 100.0, 640.0, 300.0), 0, 0.8, tile_a),
            ((640.0, 100.0, 1280.0, 300.0), 0, 0.7, tile_b),
            ((1280.0, 100.0, 1400.0, 300.0), 0, 0.6, tile_c),
        ]
    )
    result = merge_candidates(candidates, page_w=1920, page_h=640)
    assert len(result) == 1
    assert tuple(result.boxes[0]) == (500.0, 100.0, 1400.0, 300.0)
    assert result.scores[0] == 0.8


def test_merge_candidates__joins_indirect_chain_through_intermediate_merge() -> None:
    """Phản ví dụ review lượt 1 (#2): C chỉ thoả điều kiện (a) với hộp **đã nối** AB (giao/dt-nhỏ = 1,0),
    không với A hay B riêng lẻ (0,5 mỗi cặp, dưới `MERGE_OVERLAP`) — vẫn phải ra **một** hộp, nghĩa là
    `merge_candidates` phải lặp tới điểm bất động chứ không dừng ở một lượt trên ma trận kề gốc.

    A `[100,0,500,100]` (tile phải khớp mép `x=500`) + B `[500,0,900,100]` (tile trái khớp mép `x=500`)
    nối qua điều kiện (b) (chạm mép trong, chiếu y IoU 1,0) → AB `[100,0,900,100]`; C `[400,0,600,100]`
    (tile thứ ba, không chạm mép A hay B) chỉ nối được với AB ở vòng thứ hai.
    """
    tile_a, tile_b, tile_c = (0.0, 0.0, 500.0, 640.0), (500.0, 0.0, 500.0, 640.0), (350.0, 0.0, 350.0, 640.0)
    candidates = _candidates(
        [
            ((100.0, 0.0, 500.0, 100.0), 0, 0.9, tile_a),
            ((500.0, 0.0, 900.0, 100.0), 0, 0.8, tile_b),
            ((400.0, 0.0, 600.0, 100.0), 0, 0.7, tile_c),
        ]
    )
    result = merge_candidates(candidates, page_w=1000, page_h=640)
    assert len(result) == 1
    assert tuple(result.boxes[0]) == (100.0, 0.0, 900.0, 100.0)


def test_merge_candidates__does_not_join_within_same_tile() -> None:
    """Hai hộp cùng lát (dù thoả điều kiện khác) không nối — NMS đã xử trong-lát rồi."""
    tile = (0.0, 0.0, 640.0, 640.0)
    candidates = _candidates(
        [
            ((100.0, 100.0, 200.0, 200.0), 0, 0.8, tile),
            ((202.0, 100.0, 300.0, 200.0), 0, 0.7, tile),
        ]
    )
    result = merge_candidates(candidates, page_w=640, page_h=640)
    assert len(result) == 2


def test_merge_candidates__does_not_join_without_touching_inner_edge() -> None:
    """Hai hộp khác lát nhưng không chạm mép trong của lát mình → không nối (điều kiện (b) không đạt)."""
    tile_a, tile_b = (0.0, 0.0, 640.0, 640.0), (640.0, 0.0, 640.0, 640.0)
    candidates = _candidates(
        [
            ((100.0, 100.0, 200.0, 200.0), 0, 0.8, tile_a),
            ((900.0, 100.0, 1000.0, 200.0), 0, 0.7, tile_b),
        ]
    )
    result = merge_candidates(candidates, page_w=1280, page_h=640)
    assert len(result) == 2


def test_merge_candidates__caps_at_max_detections_by_score() -> None:
    """Vượt `MAX_DETECTIONS` bị cắt còn đúng trần, giữ điểm cao nhất trước."""
    tile = (0.0, 0.0, 1_000_000.0, 1_000_000.0)
    n = MAX_DETECTIONS + 5
    rows = [((float(i * 3), 0.0, float(i * 3 + 2), 2.0), i % 10, 1.0 - i / (n + 10), tile) for i in range(n)]
    result = merge_candidates(_candidates(rows), page_w=1_000_000, page_h=1_000_000)
    assert len(result) == MAX_DETECTIONS
    assert result.scores[0] >= result.scores[-1]
