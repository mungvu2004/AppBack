"""Cụm tường liên thông và vùng hộp bao (U57), dùng chung cho bước dựng (bỏ cụm xa nhỏ) và bước
kiểm chất lượng (nhiều mặt bằng trên một trang)."""

import math
from collections import deque
from collections.abc import Collection, Sequence

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
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def box_area(box: Box) -> float:
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
