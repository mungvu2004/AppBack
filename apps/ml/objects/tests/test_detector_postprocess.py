"""Test `decode_tile`/`merge_candidates` bằng tensor tay: ngưỡng, kẹp, bỏ mảnh lát cắt, NMS, nối lát (khối [8])."""

from collections.abc import Sequence

import numpy as np
import pytest

from apps.ml.objects.detector import (
    COCO_CONFIDENCE_MIN,
    CONFIDENCE_MIN,
    LABEL_CONFIDENCE_MIN,
    MAX_DETECTIONS,
    _Candidates,
    decode_tile,
    label_thresholds,
    merge_candidates,
)
from apps.ml.objects.labels import COCO_LABELS
from apps.ml.objects.tests.onnx_models import yolo_output
from apps.ml.objects.tiles import Window
from packages.ml_contracts.labels import DetectionLabel


def _candidates(
    rows: Sequence[tuple[tuple[float, float, float, float], int, float, tuple[float, float, float, float]]],
) -> _Candidates:
    """Dựng `_Candidates` tay từ `(box, label_idx, score, tile)` cho test hậu xử lý."""
    boxes = np.array([row[0] for row in rows], dtype=np.float64).reshape(-1, 4)
    classes = np.array([row[1] for row in rows], dtype=np.int64)
    scores = np.array([row[2] for row in rows], dtype=np.float64)
    tiles = np.array([row[3] for row in rows], dtype=np.float64).reshape(-1, 4)
    return _Candidates(boxes=boxes, scores=scores, classes=classes, tiles=tiles)


def test_decode_tile__drops_below_label_threshold() -> None:
    """Điểm dưới ngưỡng riêng của nhãn (`LABEL_CONFIDENCE_MIN`) bị bỏ, không sinh ứng viên."""
    output = yolo_output([(50, 50, 20, 20, 0, LABEL_CONFIDENCE_MIN["door"] - 0.05)], nc=1)
    assert len(decode_tile(output, Window(0, 0, 640, 640), ("door",), 640)) == 0


def test_decode_tile__explicit_thresholds_override_default() -> None:
    """`thresholds` truyền vào thay ngưỡng mặc định (đánh giá mAP hạ xuống 0,05)."""
    output = yolo_output([(50, 50, 20, 20, 0, 0.1)], nc=1)
    window = Window(0, 0, 640, 640)
    assert len(decode_tile(output, window, ("door",), 640)) == 0
    assert len(decode_tile(output, window, ("door",), 640, label_thresholds(("door",), 0.05))) == 1


def test_label_thresholds__defaults_per_label_and_overrides() -> None:
    """Nhãn có ngưỡng riêng dùng nó, nhãn vắng dùng `CONFIDENCE_MIN`, COCO dùng `COCO_CONFIDENCE_MIN`;
    số đè mọi nhãn, dict chỉ đè nhãn có trong dict, nhãn `None` không bao giờ qua (1,0)."""
    labels: tuple[DetectionLabel, ...] = ("door", "other")
    assert list(label_thresholds(labels)) == [LABEL_CONFIDENCE_MIN["door"], CONFIDENCE_MIN]
    assert list(label_thresholds(labels, 0.05)) == [0.05, 0.05]
    assert list(label_thresholds(labels, {"other": 0.6})) == [LABEL_CONFIDENCE_MIN["door"], 0.6]
    coco = label_thresholds(COCO_LABELS)
    mapped = [i for i, label in enumerate(COCO_LABELS) if label is not None]
    unmapped = [i for i, label in enumerate(COCO_LABELS) if label is None]
    assert set(coco[mapped]) == {COCO_CONFIDENCE_MIN}
    assert set(coco[unmapped]) == {1.0}


@pytest.mark.parametrize("bad", [-0.1, 1.5, {"door": 2.0}])
def test_label_thresholds__rejects_out_of_range(bad: float | dict[str, float]) -> None:
    """Ngưỡng ngoài `[0, 1]` là lỗi cấu hình → `ValueError` (không âm thầm bỏ hết/giữ hết)."""
    with pytest.raises(ValueError, match="ngưỡng"):
        label_thresholds(("door",), bad)


def test_decode_tile__coco_threshold_stricter_than_default() -> None:
    """`labels is COCO_LABELS` dùng ngưỡng `COCO_CONFIDENCE_MIN` (chặt hơn `CONFIDENCE_MIN`)."""
    cls = next(i for i, label in enumerate(COCO_LABELS) if label is not None)
    output = yolo_output([(50, 50, 20, 20, cls, 0.4)], nc=80)
    window = Window(0, 0, 640, 640)
    assert len(decode_tile(output, window, COCO_LABELS, 640)) == 0
    other: DetectionLabel = "other"  # không ngưỡng riêng -> `CONFIDENCE_MIN`
    other_labels = (other,) * len(COCO_LABELS)
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


def test_merge_candidates__drops_cut_fragment_before_nms() -> None:
    """Mảnh chạm mép trong lát A (điểm 0,9) bị bỏ vì lát B thấy trọn vật (điểm 0,6) — **trước** NMS.

    Nếu NMS chạy trước, IoU mảnh/hộp trọn 0,67 ≥ `NMS_IOU` sẽ bỏ hộp trọn và giữ mảnh cụt
    (lỗi đo được trên CubiCasa 2026-10-19).
    """
    tile_a, tile_b = (0.0, 0.0, 640.0, 640.0), (480.0, 0.0, 640.0, 640.0)
    candidates = _candidates(
        [
            ((600.0, 100.0, 640.0, 140.0), 0, 0.9, tile_a),
            ((600.0, 100.0, 660.0, 140.0), 0, 0.6, tile_b),
        ]
    )
    result = merge_candidates(candidates, page_w=1120, page_h=640)
    assert len(result) == 1
    assert tuple(result.boxes[0]) == (600.0, 100.0, 660.0, 140.0)
    assert result.scores[0] == 0.6


def test_merge_candidates__keeps_fragment_covered_by_other_label() -> None:
    """Hộp trọn khác nhãn không bỏ được mảnh: luật bỏ mảnh chỉ so cùng nhãn."""
    tile_a, tile_b = (0.0, 0.0, 640.0, 640.0), (480.0, 0.0, 640.0, 640.0)
    candidates = _candidates(
        [
            ((600.0, 100.0, 640.0, 140.0), 0, 0.9, tile_a),
            ((600.0, 100.0, 660.0, 140.0), 1, 0.6, tile_b),
        ]
    )
    result = merge_candidates(candidates, page_w=1120, page_h=640)
    assert sorted(int(c) for c in result.classes) == [0, 1]


_G5_PAGE: tuple[int, int] = (2080, 1600)
_G5_TILE: tuple[float, float, float, float] = (1440.0, 960.0, 640.0, 640.0)
_G5_SLIVER: tuple[float, float, float, float] = (1440.0, 1358.5, 1458.4, 1424.5)


def test_merge_candidates__drops_sliver_inside_larger_cut_box_same_tile() -> None:
    """BUG-IT-002 (CubiCasa G5): mảnh mỏng chạm mép trái lát nằm trong hộp tủ lớn cùng lát (cũng
    chạm mép, điểm 0,917) bị bỏ; trước đây NMS giữ nó vì IoU mảnh/hộp lớn chỉ ~3%."""
    big = (1440.4, 1351.1, 1697.8, 1522.5)
    candidates = _candidates([(_G5_SLIVER, 0, 0.338, _G5_TILE), (big, 0, 0.917, _G5_TILE)])
    result = merge_candidates(candidates, page_w=_G5_PAGE[0], page_h=_G5_PAGE[1])
    assert len(result) == 1
    assert tuple(result.boxes[0]) == big


def test_merge_candidates__drops_sliver_inside_larger_cut_box_other_tile() -> None:
    """Hộp phủ ở lát khác, chính nó chạm mép phải lát mình (vật rộng hơn độ chồng lát) vẫn bỏ được mảnh."""
    big = (1431.0, 1359.0, 1600.0, 1524.0)
    candidates = _candidates([(_G5_SLIVER, 0, 0.338, _G5_TILE), (big, 0, 0.885, (960.0, 960.0, 640.0, 640.0))])
    result = merge_candidates(candidates, page_w=_G5_PAGE[0], page_h=_G5_PAGE[1])
    assert len(result) == 1
    assert tuple(result.boxes[0]) == big


@pytest.mark.parametrize(("right", "kept"), [(556.0, 2), (560.0, 1)])
def test_merge_candidates__sliver_rule_needs_area_ratio(right: float, kept: int) -> None:
    """Hộp phủ 72% mảnh, cùng lát, chạm mép: lớn 1,9 lần thì giữ cả hai, đúng `CUT_SLIVER_AREA_RATIO`
    (2 lần) thì bỏ mảnh. IoU hai hộp ~0,33 < `NMS_IOU` nên NMS không xen vào."""
    tile = (480.0, 0.0, 640.0, 640.0)
    candidates = _candidates(
        [((480.0, 100.0, 520.0, 200.0), 0, 0.5, tile), ((480.0, 128.0, right, 228.0), 0, 0.9, tile)]
    )
    result = merge_candidates(candidates, page_w=1120, page_h=640)
    assert len(result) == kept


def test_merge_candidates__keeps_sliver_with_low_cover() -> None:
    """Hộp lớn 2,5 lần nhưng chỉ phủ 60% mảnh (< `CUT_COVER_MIN`) — hai vật kề nhau, giữ cả hai."""
    tile = (480.0, 0.0, 640.0, 640.0)
    candidates = _candidates(
        [((480.0, 100.0, 520.0, 200.0), 0, 0.5, tile), ((480.0, 140.0, 580.0, 240.0), 0, 0.9, tile)]
    )
    result = merge_candidates(candidates, page_w=1120, page_h=640)
    assert len(result) == 2


def test_merge_candidates__keeps_sliver_scored_above_larger_box() -> None:
    """Hộp lớn điểm thấp hơn mảnh không bỏ được mảnh (luật mới đòi điểm `j` ≥ `i`)."""
    big = (1440.4, 1351.1, 1697.8, 1522.5)
    candidates = _candidates([(_G5_SLIVER, 0, 0.9, _G5_TILE), (big, 0, 0.5, _G5_TILE)])
    result = merge_candidates(candidates, page_w=_G5_PAGE[0], page_h=_G5_PAGE[1])
    assert len(result) == 2


def test_merge_candidates__keeps_sliver_inside_larger_box_of_other_label() -> None:
    """Hộp lớn khác nhãn không bỏ mảnh: luật mảnh mỏng cũng chỉ so cùng nhãn."""
    big = (1440.4, 1351.1, 1697.8, 1522.5)
    candidates = _candidates([(_G5_SLIVER, 0, 0.338, _G5_TILE), (big, 1, 0.917, _G5_TILE)])
    result = merge_candidates(candidates, page_w=_G5_PAGE[0], page_h=_G5_PAGE[1])
    assert sorted(int(c) for c in result.classes) == [0, 1]


def test_merge_candidates__keeps_whole_small_box_inside_larger_cut_box() -> None:
    """Review P2 M06: hộp nhỏ không chạm mép trong (vật riêng, lát thấy trọn) trong hộp cắt lớn > 3 lần → giữ cả hai."""
    big = (1440.4, 1351.1, 1697.8, 1522.5)
    small = (1500.0, 1400.0, 1540.0, 1440.0)
    candidates = _candidates([(small, 0, 0.5, _G5_TILE), (big, 0, 0.917, _G5_TILE)])
    result = merge_candidates(candidates, page_w=_G5_PAGE[0], page_h=_G5_PAGE[1])
    assert len(result.classes) == 2


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
    """Vật dài 1000px vắt ba lát chồng nhau (lưới 640/160): ba mảnh → một hộp bao, điểm max."""
    tile_a, tile_b, tile_c = (0.0, 0.0, 640.0, 640.0), (480.0, 0.0, 640.0, 640.0), (960.0, 0.0, 640.0, 640.0)
    candidates = _candidates(
        [
            ((500.0, 100.0, 640.0, 300.0), 0, 0.8, tile_a),
            ((480.0, 100.0, 1120.0, 300.0), 0, 0.7, tile_b),
            ((960.0, 100.0, 1500.0, 300.0), 0, 0.6, tile_c),
        ]
    )
    result = merge_candidates(candidates, page_w=1600, page_h=640)
    assert len(result) == 1
    assert tuple(result.boxes[0]) == (480.0, 100.0, 1500.0, 300.0)
    assert result.scores[0] == 0.8


def test_merge_candidates__does_not_join_far_apart_cut_boxes() -> None:
    """Hồi quy `high_quality_architectural-1217`: hai cửa sổ chạm mép ở hai lát cách ~2000px cùng
    hàng ngang **không** nối; cửa sổ ở giữa không bị nuốt (luật cũ ra một hộp dài 2047px)."""
    candidates = _candidates(
        [
            ((587.0, 593.0, 640.0, 626.0), 0, 0.8, (0.0, 480.0, 640.0, 640.0)),
            ((1200.0, 594.0, 1260.0, 625.0), 0, 0.8, (960.0, 480.0, 640.0, 640.0)),
            ((2606.0, 595.0, 2629.0, 625.0), 0, 0.7, (2606.0, 480.0, 640.0, 640.0)),
        ]
    )
    result = merge_candidates(candidates, page_w=4000, page_h=2000)
    assert len(result) == 3
    assert max(float(b[2] - b[0]) for b in result.boxes) == 60.0


def test_merge_candidates__does_not_join_pieces_not_spanning_overlap_strip() -> None:
    """Hai hộp chạm mép ở hai lát kề nhưng không cùng phủ dải chồng (hai vật sát ranh) → không nối."""
    tile_a, tile_b = (0.0, 0.0, 640.0, 640.0), (480.0, 0.0, 640.0, 640.0)
    candidates = _candidates(
        [
            ((620.0, 100.0, 640.0, 200.0), 0, 0.8, tile_a),
            ((480.0, 100.0, 500.0, 200.0), 0, 0.7, tile_b),
        ]
    )
    result = merge_candidates(candidates, page_w=1120, page_h=640)
    assert len(result) == 2


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
