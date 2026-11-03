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


def region_labels(boxes: Sequence[Box]) -> list[int]:
    """Số vùng của từng hộp: gộp các hộp cách nhau ≤ `FAR_CLUSTER_GAP_MM`, thay bằng hộp bao của nhóm, lặp tới khi
    không nhóm nào còn sát nhau. Mỗi vùng của `grow_region` nằm trọn trong một vùng ở đây (hộp nuốt vào luôn cách
    hộp đang lớn ≤ khe); khác chuỗi `grow_region` ở chỗ hai vùng lớn dần tới sát nhau thì gộp (không phụ thuộc thứ tự).

    Mỗi vòng một truy vấn `dwithin` trên `STRtree` — tờ 5 000 cụm tách rời không thành O(n²) như chuỗi `grow_region`.
    """
    labels = list(range(len(boxes)))
    current: list[Box] = list(boxes)
    while len(current) > 1:
        coords = np.asarray(current, dtype=float)
        diagonals = shapely.linestrings(np.stack([coords[:, :2], coords[:, 2:]], axis=1))
        geoms = np.asarray(shapely.envelope(diagonals), dtype=object)
        sources, targets = STRtree(geoms).query(geoms, predicate="dwithin", distance=float(FAR_CLUSTER_GAP_MM))
        parent = list(range(len(current)))

        def root(item: int, parent: list[int] = parent) -> int:
            while parent[item] != item:
                parent[item] = parent[parent[item]]
                item = parent[item]
            return item

        for source, target in zip(sources.tolist(), targets.tolist(), strict=True):
            parent[root(source)] = root(target)
        roots = [root(item) for item in range(len(current))]
        merged = {r: i for i, r in enumerate(dict.fromkeys(roots))}
        if len(merged) == len(current):
            break
        grouped: dict[int, Box] = {}
        for item, r in enumerate(roots):
            box = current[item]
            grouped[merged[r]] = box if merged[r] not in grouped else box_union(grouped[merged[r]], box)
        labels = [merged[roots[label]] for label in labels]
        current = [grouped[i] for i in range(len(merged))]
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
