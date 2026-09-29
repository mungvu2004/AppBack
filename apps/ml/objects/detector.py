"""Bộ nhận ô mở và đồ đạc chạy qua ONNX YOLO xuất kiểu ultralytics (B5-03 §B, khối [2]).

Lát trang bằng `tiles.tile_windows` (A), decode mỗi lát rồi nối NMS + ghép hộp bị lát cắt
(khối [6]). Không vòng Python theo điểm ảnh hay theo anchor (K28): decode/NMS/ghép hộp là
thao tác mảng numpy trên toàn bộ ứng viên một lượt, vòng Python còn lại chỉ theo lát (vài
chục) hay theo phát hiện cuối (≤ `MAX_DETECTIONS`). Suy luận luôn CPU qua phiên `load_onnx`
đã nạp sẵn (M04): module này không gọi `resolve_device`.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final, cast

import numpy as np
import onnxruntime as ort  # type: ignore[import-untyped]  # onnxruntime 1.30 không có py.typed
from numpy.typing import NDArray

from apps.ml.objects.labels import COCO_LABELS, check_labels
from apps.ml.objects.tiles import Window, overlap_for, tile_windows
from apps.ml.runtime.errors import MODEL_FORMAT_UNSUPPORTED, ORT_ERRORS
from packages.messaging.tasks import PermanentError
from packages.ml_contracts.artifacts import BoxPx, DetectionPx
from packages.ml_contracts.labels import DetectionLabel
from packages.ml_contracts.ports import RgbImage

__all__ = [
    "COCO_CONFIDENCE_MIN",
    "CONFIDENCE_MIN",
    "MAX_DETECTIONS",
    "MERGE_OVERLAP",
    "NMS_IOU",
    "YoloOnnxDetector",
    "decode_tile",
    "merge_candidates",
]

CONFIDENCE_MIN: Final = 0.25
COCO_CONFIDENCE_MIN: Final = 0.5
NMS_IOU: Final = 0.5
MERGE_OVERLAP: Final = 0.7
MAX_DETECTIONS: Final = 2000

_PAD_VALUE: Final = 114
_MIN_INPUT_PX: Final = 32
_MIN_BOX_SIDE_PX: Final = 2.0
_EDGE_TOUCH_PX: Final = 2.0

Labels = tuple[DetectionLabel | None, ...]


def _unsupported() -> PermanentError:
    """Lỗi chung cho mọi model/lỗi chạy không khớp hợp đồng (không tiết lộ chi tiết)."""
    return PermanentError(MODEL_FORMAT_UNSUPPORTED)


@dataclass(frozen=True, slots=True)
class _Candidates:
    """Ứng viên sau decode, theo cột: `boxes (n,4)` x1y1x2y2, `scores (n,)`, `classes (n,)`.

    `tiles (n,4)` là phần thật `x, y, w, h` của lát nguồn mỗi ứng viên — giữ để bước nối
    hộp bị lát cắt biết "khác lát" và "mép trong" mà không cần vòng Python theo ứng viên.
    """

    boxes: NDArray[np.float64]
    scores: NDArray[np.float64]
    classes: NDArray[np.int64]
    tiles: NDArray[np.float64]

    def __len__(self) -> int:
        """Số ứng viên (bằng số hàng của `boxes`)."""
        return int(self.boxes.shape[0])


@dataclass(frozen=True, slots=True)
class _Detections:
    """Phát hiện cuối sau nối/NMS: chỉ còn hộp/điểm/nhãn, không còn lát nguồn."""

    boxes: NDArray[np.float64]
    scores: NDArray[np.float64]
    classes: NDArray[np.int64]

    def __len__(self) -> int:
        """Số phát hiện."""
        return int(self.boxes.shape[0])


_EMPTY_CANDIDATES: Final = _Candidates(
    boxes=np.zeros((0, 4), dtype=np.float64),
    scores=np.zeros(0, dtype=np.float64),
    classes=np.zeros(0, dtype=np.int64),
    tiles=np.zeros((0, 4), dtype=np.float64),
)


def _checked_input_shape(inputs: Sequence[Any]) -> int:
    """Đúng 1 đầu vào `(1, 3, S, S)`, `S` số nguyên tĩnh ≥ 32 chia hết 32 (khối [2])."""
    if len(inputs) != 1:
        raise _unsupported()
    shape = list(inputs[0].shape)
    if len(shape) != 4 or shape[0] != 1 or shape[1] != 3:
        raise _unsupported()
    size = shape[2]
    if not isinstance(size, int) or shape[3] != size or size < _MIN_INPUT_PX or size % 32 != 0:
        raise _unsupported()
    return size


def _checked_output_shape(outputs: Sequence[Any], *, expected_channels: int) -> None:
    """Đúng 1 đầu ra `(1, 4+len(labels), A)`, `A` tĩnh hay động đều nhận (khối [2])."""
    if len(outputs) != 1:
        raise _unsupported()
    shape = list(outputs[0].shape)
    if len(shape) != 3 or shape[0] != 1 or shape[1] != expected_channels:
        raise _unsupported()


def _preprocess_tile(image: RgbImage, window: Window, input_px: int) -> NDArray[np.float32]:
    """Cắt phần thật của lát, đệm 114 tới `input_px²`, `float32/255` HWC→NCHW (khối [6], không co giãn)."""
    tile = np.full((input_px, input_px, 3), _PAD_VALUE, dtype=np.uint8)
    tile[: window.height, : window.width] = image[
        window.y : window.y + window.height, window.x : window.x + window.width
    ]
    chw = np.ascontiguousarray(tile.transpose(2, 0, 1).astype(np.float32) / 255.0)
    return chw[np.newaxis, ...]


def decode_tile(
    output: NDArray[np.float32],
    window: Window,
    labels: Labels,
    input_px: int,
) -> _Candidates:
    """`(1, 4+nc, A)` ultralytics → ứng viên trang, mảng hoá toàn bộ anchor cùng lúc (khối [6] bước 1-2, K28).

    `score = max` lớp, `cls = argmax` (hoà chỉ số nhỏ, `np.argmax` đã vậy); ngưỡng
    `COCO_CONFIDENCE_MIN` khi `labels is COCO_LABELS`, `CONFIDENCE_MIN` khác. Lớp `None`,
    NaN/vô cực, cạnh < 2px sau kẹp vào phần thật của lát đều bị bỏ (mặt nạ boolean, không vòng anchor).

    `input_px` giữ trong chữ ký vì khối [5] khai vậy cho mọi hàm hậu xử lý của bước, nhưng
    không dùng ở đây: vùng đệm bị trừ bằng `window` (phần thật của lát, luôn ≤ `input_px`),
    không phải bằng `input_px` trực tiếp — hàm này không cần biết kích cỡ đệm.
    """
    arr = output[0].T.astype(np.float64)
    class_scores = arr[:, 4:]
    classes = class_scores.argmax(axis=1)
    scores = class_scores[np.arange(classes.shape[0]), classes]
    threshold = COCO_CONFIDENCE_MIN if labels is COCO_LABELS else CONFIDENCE_MIN
    none_mask = np.array([label is None for label in labels], dtype=bool)
    keep = (scores >= threshold) & ~none_mask[classes]
    if not np.any(keep):
        return _EMPTY_CANDIDATES
    cx, cy, w, h = arr[keep, 0], arr[keep, 1], arr[keep, 2], arr[keep, 3]
    x1, y1 = cx - w / 2 + window.x, cy - h / 2 + window.y
    x2, y2 = cx + w / 2 + window.x, cy + h / 2 + window.y
    finite = np.isfinite(x1) & np.isfinite(y1) & np.isfinite(x2) & np.isfinite(y2)
    inner_x1, inner_y1 = float(window.x), float(window.y)
    inner_x2, inner_y2 = float(window.x + window.width), float(window.y + window.height)
    x1c, x2c = np.clip(x1, inner_x1, inner_x2), np.clip(x2, inner_x1, inner_x2)
    y1c, y2c = np.clip(y1, inner_y1, inner_y2), np.clip(y2, inner_y1, inner_y2)
    valid = finite & (x2c - x1c >= _MIN_BOX_SIDE_PX) & (y2c - y1c >= _MIN_BOX_SIDE_PX)
    if not np.any(valid):
        return _EMPTY_CANDIDATES
    boxes = np.stack([x1c, y1c, x2c, y2c], axis=1)[valid]
    n = boxes.shape[0]
    tile_row = np.array([window.x, window.y, window.width, window.height], dtype=np.float64)
    return _Candidates(
        boxes=boxes,
        scores=scores[keep][valid],
        classes=classes[keep][valid].astype(np.int64),
        tiles=np.tile(tile_row, (n, 1)),
    )


def _concat_candidates(parts: Sequence[_Candidates]) -> _Candidates:
    """Nối ứng viên mọi lát bằng `np.concatenate` (khối [6]: sinh lát tuần tự, gộp mảng)."""
    non_empty = [part for part in parts if len(part) > 0]
    if not non_empty:
        return _EMPTY_CANDIDATES
    return _Candidates(
        boxes=np.concatenate([p.boxes for p in non_empty]),
        scores=np.concatenate([p.scores for p in non_empty]),
        classes=np.concatenate([p.classes for p in non_empty]),
        tiles=np.concatenate([p.tiles for p in non_empty]),
    )


def _iou_against(box: NDArray[np.float64], boxes: NDArray[np.float64]) -> NDArray[np.float64]:
    """IoU của một hộp so với nhiều hộp, vector hoá (dùng cho NMS)."""
    x1 = np.maximum(box[0], boxes[:, 0])
    y1 = np.maximum(box[1], boxes[:, 1])
    x2 = np.minimum(box[2], boxes[:, 2])
    y2 = np.minimum(box[3], boxes[:, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    area_a = (box[2] - box[0]) * (box[3] - box[1])
    area_b = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    union = area_a + area_b - inter
    return cast(NDArray[np.float64], np.where(union > 0, inter / union, 0.0))


def _nms(candidates: _Candidates) -> _Candidates:
    """NMS tham lam theo nhãn (khối [6] bước 3): `np.lexsort` một lần; vòng chỉ lặp trên hộp còn giữ.

    Không vòng lồng: mỗi bước so IoU vector hoá với các hộp **cùng nhãn đã giữ**, không so
    lại toàn bộ cặp (n, n).
    """
    n = len(candidates)
    if n == 0:
        return candidates
    x1 = candidates.boxes[:, 0]
    y1 = candidates.boxes[:, 1]
    order = np.lexsort((y1, x1, candidates.classes, -candidates.scores))
    keep_mask = np.zeros(n, dtype=bool)
    kept_by_label: dict[int, NDArray[np.float64]] = {}
    for i in order:
        label = int(candidates.classes[i])
        box = candidates.boxes[i]
        existing = kept_by_label.get(label)
        if existing is not None and np.any(_iou_against(box, existing) >= NMS_IOU):
            continue
        keep_mask[i] = True
        kept_by_label[label] = box[None, :] if existing is None else np.vstack([existing, box[None, :]])
    idx = np.nonzero(keep_mask)[0]
    return _Candidates(
        boxes=candidates.boxes[idx],
        scores=candidates.scores[idx],
        classes=candidates.classes[idx],
        tiles=candidates.tiles[idx],
    )


def _pairwise_area_overlap(boxes: NDArray[np.float64]) -> NDArray[np.float64]:
    """Ma trận `(n,n)` giao/diện tích hộp nhỏ, cho điều kiện (a) của bước 4 (một lượt numpy)."""
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    ix1 = np.maximum(x1[:, None], x1[None, :])
    iy1 = np.maximum(y1[:, None], y1[None, :])
    ix2 = np.minimum(x2[:, None], x2[None, :])
    iy2 = np.minimum(y2[:, None], y2[None, :])
    inter = np.clip(ix2 - ix1, 0, None) * np.clip(iy2 - iy1, 0, None)
    area = (x2 - x1) * (y2 - y1)
    smaller = np.minimum(area[:, None], area[None, :])
    with np.errstate(divide="ignore", invalid="ignore"):
        return cast(NDArray[np.float64], np.where(smaller > 0, inter / smaller, 0.0))


def _interval_iou_matrix(lo: NDArray[np.float64], hi: NDArray[np.float64]) -> NDArray[np.float64]:
    """Ma trận `(n,n)` IoU một chiều của khoảng chiếu `[lo, hi]` (điều kiện (b), trục song song mép cắt)."""
    ilo = np.maximum(lo[:, None], lo[None, :])
    ihi = np.minimum(hi[:, None], hi[None, :])
    inter = np.clip(ihi - ilo, 0, None)
    union = (hi[:, None] - lo[:, None]) + (hi[None, :] - lo[None, :]) - inter
    with np.errstate(divide="ignore", invalid="ignore"):
        return cast(NDArray[np.float64], np.where(union > 0, inter / union, 0.0))


def _cut_edge_touches(
    boxes: NDArray[np.float64], tiles: NDArray[np.float64], page_w: int, page_h: int
) -> dict[str, NDArray[np.bool_]]:
    """Mỗi ứng viên có chạm mép trong (không trùng mép trang) của lát mình, vector hoá (điều kiện (b))."""
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    tile_x, tile_y, tile_w, tile_h = tiles[:, 0], tiles[:, 1], tiles[:, 2], tiles[:, 3]
    right, bottom = tile_x + tile_w, tile_y + tile_h
    return {
        "left": (tile_x > 0) & (np.abs(x1 - tile_x) <= _EDGE_TOUCH_PX),
        "right": (right < page_w) & (np.abs(x2 - right) <= _EDGE_TOUCH_PX),
        "top": (tile_y > 0) & (np.abs(y1 - tile_y) <= _EDGE_TOUCH_PX),
        "bottom": (bottom < page_h) & (np.abs(y2 - bottom) <= _EDGE_TOUCH_PX),
    }


def _merge_adjacency(candidates: _Candidates, *, page_w: int, page_h: int) -> NDArray[np.bool_]:
    """Ma trận kề `(n,n)` của điều kiện nối (khối [6] bước 4a/4b), toàn bộ cặp một lượt numpy."""
    n = len(candidates)
    same_label = candidates.classes[:, None] == candidates.classes[None, :]
    diff_tile = np.any(candidates.tiles[:, None, :] != candidates.tiles[None, :, :], axis=2)
    area_cond = _pairwise_area_overlap(candidates.boxes) >= MERGE_OVERLAP
    touch = _cut_edge_touches(candidates.boxes, candidates.tiles, page_w, page_h)
    horizontal_pair = (touch["right"][:, None] & touch["left"][None, :]) | (
        touch["left"][:, None] & touch["right"][None, :]
    )
    vertical_pair = (touch["bottom"][:, None] & touch["top"][None, :]) | (
        touch["top"][:, None] & touch["bottom"][None, :]
    )
    y1, y2 = candidates.boxes[:, 1], candidates.boxes[:, 3]
    x1, x2 = candidates.boxes[:, 0], candidates.boxes[:, 2]
    horizontal_cond = horizontal_pair & (_interval_iou_matrix(y1, y2) >= MERGE_OVERLAP)
    vertical_cond = vertical_pair & (_interval_iou_matrix(x1, x2) >= MERGE_OVERLAP)
    adjacency = same_label & diff_tile & (area_cond | horizontal_cond | vertical_cond)
    np.fill_diagonal(adjacency, False)
    return cast(NDArray[np.bool_], adjacency[:n, :n])


def _connected_components(n: int, edges: NDArray[np.int64]) -> NDArray[np.int64]:
    """Nhãn thành phần liên thông của `n` đỉnh theo `edges (m,2)` — union-find, chỉ lặp trên cạnh thật.

    Một lượt của `_merge_cut_boxes`: bao đóng bắc cầu của cặp thoả điều kiện nối trên **ma
    trận kề của lượt này**. Hộp bao sau khi nối có diện tích khác hộp gốc, nên một lượt không
    đủ bắt hết chuỗi nối gián tiếp (ví dụ #2 review lượt 1) — `_merge_cut_boxes` gọi lại hàm
    này ở mỗi lượt cho tới điểm bất động, không phải hàm này tự lặp.
    """
    parent = np.arange(n)

    def find(x: int) -> int:
        """Gốc của `x` theo path-halving (nén một nửa đường mỗi bước, không đệ quy)."""
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return int(x)

    for a, b in edges:
        ra, rb = find(int(a)), find(int(b))
        if ra != rb:
            parent[ra] = rb
    return np.array([find(i) for i in range(n)])


def _union_round(candidates: _Candidates, groups: NDArray[np.int64]) -> _Candidates:
    """Gộp mỗi thành phần liên thông thành một ứng viên: hộp bao, điểm max, nhãn chung.

    Lát nguồn (`tiles`) của một nhóm giữ nguyên **chỉ khi nhóm đó chỉ có một ứng viên** (chưa
    nối lượt nào) — vòng sau vẫn cần lát thật để loại cặp cùng lát (NMS đã xử trong-lát rồi).
    Nhóm đã nối (≥ 2 ứng viên) không còn thuộc một lát duy nhất: đặt `NaN`, để `!=` trong
    `_merge_adjacency` luôn coi nó "khác lát" với bất kỳ ứng viên nào ở vòng sau — quyết định
    này là phần "định nghĩa rõ lát nguồn của hộp nối" mà review lượt 1 yêu cầu.
    """
    unique_groups, inverse, counts = np.unique(groups, return_inverse=True, return_counts=True)
    g = unique_groups.shape[0]
    merged_x1 = np.full(g, np.inf)
    merged_y1 = np.full(g, np.inf)
    merged_x2 = np.full(g, -np.inf)
    merged_y2 = np.full(g, -np.inf)
    merged_score = np.full(g, -np.inf)
    merged_label = np.zeros(g, dtype=np.int64)
    np.minimum.at(merged_x1, inverse, candidates.boxes[:, 0])
    np.minimum.at(merged_y1, inverse, candidates.boxes[:, 1])
    np.maximum.at(merged_x2, inverse, candidates.boxes[:, 2])
    np.maximum.at(merged_y2, inverse, candidates.boxes[:, 3])
    np.maximum.at(merged_score, inverse, candidates.scores)
    merged_label[inverse] = candidates.classes
    merged_tiles = np.empty((g, 4))
    merged_tiles[inverse] = candidates.tiles
    merged_tiles[counts > 1] = np.nan
    boxes = np.stack([merged_x1, merged_y1, merged_x2, merged_y2], axis=1)
    return _Candidates(boxes=boxes, scores=merged_score, classes=merged_label, tiles=merged_tiles)


def _merge_cut_boxes_to_fixed_point(state: _Candidates, *, page_w: int, page_h: int) -> _Candidates:
    """Một nhãn: ma trận kề → thành phần liên thông → gộp, lặp tới khi không còn cặp kề (khối [6] bước 4).

    Mỗi vòng dùng ứng viên **hiện tại** (gồm cả hộp đã nối ở vòng trước). Dừng khi ma trận kề
    rỗng. Số vòng bị chặn trên bởi số ứng viên của nhãn này (mỗi vòng giảm ít nhất một nhóm);
    dữ liệu thật (chuỗi nối vắt vài ranh lát liền kề) hội tụ sau vài vòng, không phải `O(n)`.
    """
    while len(state) > 0:
        adjacency = _merge_adjacency(state, page_w=page_w, page_h=page_h)
        edges = np.argwhere(np.triu(adjacency, k=1))
        if edges.shape[0] == 0:
            break
        groups = _connected_components(len(state), edges)
        state = _union_round(state, groups)
    return state


def _merge_cut_boxes(candidates: _Candidates, *, page_w: int, page_h: int) -> _Detections:
    """Nối hộp bị lát cắt, theo từng nhãn riêng (khối [6] bước 4: điều kiện luôn đòi cùng nhãn,
    nên hai nhóm nhãn khác nhau không bao giờ ảnh hưởng nhau).

    Tách nhóm trước khi lặp: chi phí ma trận kề đổi từ `O(n²)` (một nhãn giả định) xuống
    `O(Σ mᵢ²)` với `mᵢ` là số ứng viên mỗi nhãn — cùng số phép so sánh hợp lệ (same-label vẫn
    là điều kiện bắt buộc trong `_merge_adjacency`) nhưng không tính phí cho cặp khác nhãn,
    đáng kể khi `n` lớn nhiều nhãn (trần hiệu năng `test_perf.py`).
    """
    if len(candidates) == 0:
        return _Detections(boxes=candidates.boxes, scores=candidates.scores, classes=candidates.classes)
    merged_groups = [
        _merge_cut_boxes_to_fixed_point(
            _Candidates(
                boxes=candidates.boxes[mask],
                scores=candidates.scores[mask],
                classes=candidates.classes[mask],
                tiles=candidates.tiles[mask],
            ),
            page_w=page_w,
            page_h=page_h,
        )
        for mask in (candidates.classes == label for label in np.unique(candidates.classes))
    ]
    return _Detections(
        boxes=np.concatenate([g.boxes for g in merged_groups]),
        scores=np.concatenate([g.scores for g in merged_groups]),
        classes=np.concatenate([g.classes for g in merged_groups]),
    )


def _cap_and_sort(detections: _Detections) -> _Detections:
    """Giữ tối đa `MAX_DETECTIONS` theo điểm, sắp `(y1, x1, nhãn)` — `np.argpartition`/`np.lexsort` (bước 5)."""
    n = len(detections)
    if n > MAX_DETECTIONS:
        top = np.argpartition(-detections.scores, MAX_DETECTIONS - 1)[:MAX_DETECTIONS]
        detections = _Detections(
            boxes=detections.boxes[top], scores=detections.scores[top], classes=detections.classes[top]
        )
    order = np.lexsort((detections.classes, detections.boxes[:, 0], detections.boxes[:, 1]))
    return _Detections(
        boxes=detections.boxes[order], scores=detections.scores[order], classes=detections.classes[order]
    )


def merge_candidates(candidates: _Candidates, *, page_w: int, page_h: int) -> _Detections:
    """NMS theo nhãn rồi nối hộp bị lát cắt, giữ tối đa `MAX_DETECTIONS` theo điểm (khối [6] bước 3-5).

    Lệch khỏi prompt: khổ trang (`page_w`, `page_h`) truyền tường minh (kích thước ảnh thật ở
    `detect`) thay vì suy từ hợp các lát, để không phụ thuộc việc lát cuối có còn trong ứng
    viên hay không.
    """
    return _cap_and_sort(_merge_cut_boxes(_nms(candidates), page_w=page_w, page_h=page_h))


def _finalize(detections: _Detections, labels: Labels) -> tuple[DetectionPx, ...]:
    """Làm tròn toạ độ 2 chữ số, điểm 4 chữ số `[0, 1]`; vòng Python chỉ để dựng `DetectionPx` (≤ `MAX_DETECTIONS`)."""
    boxes = np.round(detections.boxes, 2)
    confidences = np.round(np.clip(detections.scores, 0.0, 1.0), 4)
    results: list[DetectionPx] = []
    for i in range(len(detections)):
        label = cast(DetectionLabel, labels[int(detections.classes[i])])
        box = BoxPx(
            x_min=float(boxes[i, 0]), y_min=float(boxes[i, 1]), x_max=float(boxes[i, 2]), y_max=float(boxes[i, 3])
        )
        results.append(DetectionPx(label=label, box=box, confidence=float(confidences[i])))
    return tuple(results)


class YoloOnnxDetector:
    """`ObjectDetector` (B5-01) chạy trên phiên ONNX YOLO xuất kiểu ultralytics (khối [1])."""

    def __init__(self, session: ort.InferenceSession, labels: Labels) -> None:
        """Kiểm hình dạng và nhãn ngay lúc dựng (K12, M02); sai → `PermanentError(MODEL_FORMAT_UNSUPPORTED)`.

        Không đọc `names`/metadata khác của ONNX (khối [2]); nhãn ngoài `ARTIFACT_LABELS`
        và khác `None` → `ValueError` qua `check_labels`.
        """
        check_labels(labels)
        inputs, outputs = session.get_inputs(), session.get_outputs()
        self.input_px = _checked_input_shape(inputs)
        _checked_output_shape(outputs, expected_channels=4 + len(labels))
        self._session = session
        self._labels = labels
        self._input_name = inputs[0].name
        self._output_name = outputs[0].name

    def detect(self, image: RgbImage) -> tuple[DetectionPx, ...]:
        """Ảnh trang → phát hiện theo pixel trang: lát tuần tự → suy luận CPU → decode → nối/NMS.

        Lỗi `onnxruntime` lúc `session.run` (`ORT_ERRORS`) → `PermanentError(MODEL_FORMAT_UNSUPPORTED)`,
        như `apps/ml/walls/segformer.py:93` (M04: không `resolve_device`, luôn CPU qua phiên đã nạp).
        """
        overlap_px = overlap_for(self.input_px)
        height, width = image.shape[:2]
        windows = tile_windows(width, height, tile_px=self.input_px, overlap_px=overlap_px)
        per_tile: list[_Candidates] = []
        for window in windows:
            tile_input = _preprocess_tile(image, window, self.input_px)
            try:
                output = self._session.run([self._output_name], {self._input_name: tile_input})[0]
            except ORT_ERRORS as exc:
                raise _unsupported() from exc
            per_tile.append(decode_tile(output, window, self._labels, self.input_px))
        candidates = _concat_candidates(per_tile)
        detections = merge_candidates(candidates, page_w=width, page_h=height)
        return _finalize(detections, self._labels)
