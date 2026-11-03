"""Cụm tường liên thông và vùng hộp bao (U57), dùng chung cho bước dựng (bỏ cụm xa nhỏ) và bước
kiểm chất lượng (nhiều mặt bằng trên một trang)."""

import math
from collections import deque
from collections.abc import Collection, Sequence
from typing import Final

import numpy as np
import shapely
from numpy.typing import NDArray
from shapely import STRtree

from apps.worker.pipeline_build.constants import FAR_CLUSTER_GAP_MM, WALL_JOIN_MM

Box = tuple[float, float, float, float]


def neighbours(tree: STRtree, geoms: NDArray[np.object_], distance: float) -> list[set[int]]:
    """Một truy vấn `dwithin` theo lô: các hình khác cách mỗi hình ≤ `distance`."""
    result: list[set[int]] = [set() for _ in range(len(geoms))]
    sources, targets = tree.query(geoms, predicate="dwithin", distance=distance)
    for source, target in zip(sources.tolist(), targets.tolist(), strict=True):
        if source != target:
            result[source].add(target)
    return result


def wall_clusters(geoms: NDArray[np.object_], widths: Sequence[float]) -> list[list[int]]:
    """Cụm tường liên thông: hai tường chạm nhau khi tim cách ≤ nửa tổng bề dày + `WALL_JOIN_MM`."""
    thickest = max(widths)
    near = neighbours(STRtree(geoms), geoms, thickest + float(WALL_JOIN_MM))
    seen = [False] * len(geoms)
    groups: list[list[int]] = []
    for root in range(len(geoms)):
        if seen[root]:
            continue
        seen[root] = True
        group: list[int] = []
        queue = deque([root])
        while queue:
            index = queue.popleft()
            group.append(index)
            for other in near[index]:
                gap = (widths[index] + widths[other]) / 2 + WALL_JOIN_MM
                if not seen[other] and shapely.distance(geoms[index], geoms[other]) <= gap:
                    seen[other] = True
                    queue.append(other)
        groups.append(group)
    return groups


def box_gap(a: Box, b: Box) -> float:
    """Khe ngắn nhất giữa hai hộp thẳng trục (0 khi chồng nhau)."""
    return math.hypot(max(b[0] - a[2], a[0] - b[2], 0.0), max(b[1] - a[3], a[1] - b[3], 0.0))


def box_union(a: Box, b: Box) -> Box:
    """Hộp thẳng trục nhỏ nhất bao cả hai hộp."""
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def box_area(box: Box) -> float:
    """Diện tích hộp thẳng trục."""
    return (box[2] - box[0]) * (box[3] - box[1])


def grow_region(boxes: Sequence[Box], candidates: Collection[int], seed: int) -> tuple[Box, set[int]]:
    """Vùng lớn dần từ hộp `seed`, nuốt mọi hộp trong `candidates` cách vùng ≤ `FAR_CLUSTER_GAP_MM`
    (tường bị khe cửa cắt rời, ban công, cột sát căn). Trả hộp vùng và các ứng viên còn ở xa."""
    region = boxes[seed]
    far = set(candidates)
    far.discard(seed)
    grown = True
    while grown:
        grown = False
        for index in sorted(far):
            if box_gap(boxes[index], region) <= FAR_CLUSTER_GAP_MM:
                far.discard(index)
                region = box_union(region, boxes[index])
                grown = True
    return region, far


def region_labels(boxes: Sequence[Box], lengths: Sequence[float]) -> list[int]:
    """Số vùng của từng hộp, đúng chuỗi vùng của `_multiple_plans`: `grow_region` từ cụm dài nhất còn lại (hoà lấy chỉ
    số nhỏ), lặp lại trên các cụm chưa thuộc vùng nào. Vùng 0 là vùng chính.

    Mỗi bước lớn dần nuốt cùng lúc mọi hộp chưa gán cách hộp vùng ≤ `FAR_CLUSTER_GAP_MM` (cùng điểm dừng với
    `grow_region` nuốt từng hộp), tra bằng một truy vấn `dwithin` trên `STRtree`: tờ 5 000 cụm tách rời không thành
    O(n²) như vòng `grow_region`, và không giữ mảng mọi cặp hộp chồng nhau.
    """
    if not boxes:
        return []
    coords = np.asarray(boxes, dtype=float)
    diagonals = shapely.linestrings(np.stack([coords[:, :2], coords[:, 2:]], axis=1))
    tree = STRtree(np.asarray(shapely.envelope(diagonals), dtype=object))
    labels = [-1] * len(boxes)
    label = 0
    for seed in sorted(range(len(boxes)), key=lambda index: (-lengths[index], index)):
        if labels[seed] >= 0:
            continue
        labels[seed] = label
        region = boxes[seed]
        while True:
            reach = shapely.envelope(shapely.LineString([region[:2], region[2:]]))
            hits = tree.query(reach, predicate="dwithin", distance=float(FAR_CLUSTER_GAP_MM)).tolist()
            fresh = [index for index in hits if labels[index] < 0]
            if not fresh:
                break
            for index in fresh:
                labels[index] = label
                region = box_union(region, boxes[index])
        label += 1
    return labels


AXIS_TOLERANCE_DEG: Final = 4.0
"""Nửa bề rộng họ hướng của `axis_share`: tường thẳng trục vẽ/dò lệch vài độ (bench A đến F: ≥ 0,92 chiều dài nằm
trong ±4° quanh hướng trội), cạnh phối cảnh 3D tản khắp các góc (0,23 đến 0,46)."""


def axis_share(vectors: NDArray[np.float64]) -> float:
    """Tỉ lệ chiều dài (trọng số) của các vectơ tim tường `(dx, dy)` nằm trong ±`AXIS_TOLERANCE_DEG` quanh hướng
    trội, góc lấy mod 90 (hai họ vuông góc của bản vẽ là một). Hướng trội tự tìm nên bản xoay vẫn ≈ 1.

    Cửa sổ rộng 2 x dung sai đặt mép dưới tại góc từng tường (góc đã sắp, nối thêm bản +90° cho vòng mod 90): bằng
    đúng cực đại trên mọi vị trí cửa sổ; O(n log n), không cấp phát n x n."""
    lengths = np.hypot(vectors[:, 0], vectors[:, 1])
    total = float(lengths.sum())
    if total <= 0:
        return 1.0
    angles = np.degrees(np.arctan2(vectors[:, 1], vectors[:, 0])) % 90
    order = np.argsort(angles)
    ring = np.concatenate([angles[order], angles[order] + 90])
    summed = np.concatenate([[0.0], np.cumsum(np.concatenate([lengths[order], lengths[order]]))])
    ends = np.searchsorted(ring, ring[: len(order)] + 2 * AXIS_TOLERANCE_DEG, side="right")
    return float((summed[ends] - summed[: len(order)]).max() / total)
