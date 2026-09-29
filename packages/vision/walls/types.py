"""Kiểu kết quả của vector hoá tường, theo pixel trang (B5-02 [2]).

Cố ý là dataclass thuần, không phải model `ml_contracts`: gói này không nhập hợp đồng ML,
việc kiểm hợp đồng (`WallPx`) nằm ở `apps.ml.walls` khi đổi kiểu.
"""

from collections.abc import Mapping
from dataclasses import dataclass

type PointPx = tuple[float, float]


@dataclass(frozen=True, slots=True)
class WallSegment:
    """Một đoạn tường: đường tim `start`→`end` (px, `(x, y)`), bề dày đo thật, độ tin ∈ [0, 1].

    `thickness_px` không làm tròn về bộ chuẩn (việc của B5-05).
    """

    start: PointPx
    end: PointPx
    thickness_px: float
    confidence: float


@dataclass(frozen=True, slots=True)
class VectorizeResult:
    """Đoạn tường và số phần tử bị bỏ theo lý do (`spur`, `short`)."""

    walls: tuple[WallSegment, ...]
    dropped: Mapping[str, int]
