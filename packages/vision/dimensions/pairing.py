"""Ghép chữ kích thước với tường thành mẫu tỉ lệ (`ScaleSample`), hàm thuần và tất định.

Không trả tỉ lệ: `infer_scale` (B3-01) quyết, loại ngoại lai và từ chối khi thiếu mẫu (K19).
Chữ nhịp (giữa hai vách) cho mẫu theo nhịp; chữ tổng nằm giữa tường cho mẫu cả tường.
Chữ nhịp của tường hai nhịp bằng nhau nằm ở 0,25 L và 0,75 L nên không được sinh mẫu cả tường.
"""

import bisect
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

from packages.domain.scale import ScaleSample, classify_scale_range
from packages.ml_contracts.artifacts import BoxPx, TextPx, WallPx
from packages.vision.dimensions.lengths import parse_length_mm

_AXIS_TOLERANCE_DEG: Final = 10.0
_TAN_TOLERANCE: Final = math.tan(math.radians(_AXIS_TOLERANCE_DEG))
_SIN_TOLERANCE: Final = math.sin(math.radians(_AXIS_TOLERANCE_DEG))
_REACH_SHORT_EDGES: Final = 4
"""Chữ cách tim tường tối đa 4 cạnh ngắn của hộp chữ (cộng ½ bề dày)."""
_SPAN_WINDOW: Final = (0.2, 0.8)
_WHOLE_WINDOW: Final = (0.4, 0.6)

Array = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class _WallIndex:
    """Các tường đã đổi sang mảng để chiếu hàng loạt: `start`/`vec`/`unit` hình `(n, 2)`, còn lại `(n,)`."""

    start: Array
    vec: Array
    unit: Array
    length: Array
    thickness: Array
    horizontal: NDArray[np.bool_]
    usable: NDArray[np.bool_]

    @classmethod
    def of(cls, walls: Sequence[WallPx]) -> "_WallIndex":
        """Dựng chỉ mục; tường dùng được khi lệch trục ngang hoặc dọc ≤ 10°."""
        start = np.array([[w.start.x, w.start.y] for w in walls], dtype=np.float64).reshape(-1, 2)
        end = np.array([[w.end.x, w.end.y] for w in walls], dtype=np.float64).reshape(-1, 2)
        vec = end - start
        length = np.hypot(vec[:, 0], vec[:, 1])
        ax, ay = np.abs(vec[:, 0]), np.abs(vec[:, 1])
        horizontal = ay <= ax * _TAN_TOLERANCE
        usable = horizontal | (ax <= ay * _TAN_TOLERANCE)
        thickness = np.array([w.thickness_px for w in walls], dtype=np.float64)
        return cls(start, vec, vec / length[:, None], length, thickness, horizontal, usable)

    def spans(self, j: int) -> tuple[float, ...]:
        """Điểm chia nhịp của tường `j` theo px từ `start`: `0`, chỗ tường khác chạm vào, `L`; tăng dần, không trùng.

        Tường chạm khi đường tim của nó cắt, hoặc một đầu của nó cách đường tim `j` không quá ½ bề dày
        lớn hơn (nút T). Tường gần song song (≤ 10°) không chia; điểm cách nhau ≤ ½ bề dày là một nút.
        """
        p, r, u, length = self.start[j], self.vec[j], self.unit[j], float(self.length[j])
        cross = r[0] * self.vec[:, 1] - r[1] * self.vec[:, 0]
        crossing = np.abs(cross) > _SIN_TOLERANCE * length * self.length
        offset = self.start - p
        # `den` chỉ để tránh chia cho 0 ở tường song song; chúng đã bị `crossing` loại.
        den = np.where(crossing, cross, 1.0)
        along = (offset[:, 0] * self.vec[:, 1] - offset[:, 1] * self.vec[:, 0]) / den
        across = (offset[:, 0] * r[1] - offset[:, 1] * r[0]) / den
        proper = crossing & (along >= 0) & (along <= 1) & (across >= 0) & (across <= 1)
        # `t` tính từ điểm nằm trên tường kia để nút vuông trục ra đúng số nguyên, không sai số `s * L`.
        hits = [((self.start + across[:, None] * self.vec - p) @ u)[proper]]
        reach = np.maximum(self.thickness[j], self.thickness) / 2
        for end in (self.start, self.start + self.vec):
            t = np.clip((end - p) @ u, 0.0, length)
            gap = np.hypot(*(end - (p + t[:, None] * u)).T)
            hits.append(t[crossing & ~proper & (gap <= reach)])
        return _merge_points(np.concatenate(hits), length, float(self.thickness[j]) / 2)

    def nearest(self, box: BoxPx) -> tuple[int, float] | None:
        """Tường hợp lệ đứng đầu theo `(d, -L, j)` cho hộp chữ và hình chiếu tâm `t` (px từ `start`), hoặc `None`."""
        width, height = box.x_max - box.x_min, box.y_max - box.y_min
        rel = np.array([(box.x_min + box.x_max) / 2, (box.y_min + box.y_max) / 2]) - self.start
        t = rel[:, 0] * self.unit[:, 0] + rel[:, 1] * self.unit[:, 1]
        d = np.abs(rel[:, 0] * self.unit[:, 1] - rel[:, 1] * self.unit[:, 0])
        reach = _REACH_SHORT_EDGES * min(width, height) + self.thickness / 2
        valid = self.usable & (self.horizontal == (width >= height)) & (t >= 0) & (t <= self.length) & (d <= reach)
        candidates = np.flatnonzero(valid)
        if candidates.size == 0:
            return None
        best = int(candidates[np.lexsort((candidates, -self.length[candidates], d[candidates]))[0]])
        return best, float(t[best])


def _merge_points(points: Array, length: float, half_thickness: float) -> tuple[float, ...]:
    """`0`, các điểm trong `(½ bề dày, L - ½ bề dày)` gom nút cách nhau ≤ ½ bề dày, rồi `L`."""
    merged = [0.0]
    for point in np.sort(points[(points > half_thickness) & (points < length - half_thickness)]):
        if point - merged[-1] > half_thickness:
            merged.append(float(point))
    return (*merged, length)


def wall_spans(walls: Sequence[WallPx]) -> tuple[tuple[float, ...], ...]:
    """Điểm chia nhịp của từng tường, cùng thứ tự đầu vào; nhịp `k` là `[t_k, t_{k+1}]`."""
    index = _WallIndex.of(walls)
    return tuple(index.spans(j) for j in range(len(walls)))


def _samples_of(
    text_id: int, wall_id: int, value: int, t: float, length: float, spans: Sequence[float]
) -> list[ScaleSample]:
    """Tối đa hai mẫu của một chữ: theo nhịp chứa hình chiếu (0,2-0,8 nhịp) và cả tường (0,4-0,6 L, tường > 1 nhịp)."""
    k = min(bisect.bisect_right(spans, t) - 1, len(spans) - 2)
    span_px = spans[k + 1] - spans[k]
    candidates = []
    if _SPAN_WINDOW[0] <= (t - spans[k]) / span_px <= _SPAN_WINDOW[1]:
        candidates.append((f"s{k}", span_px))
    if len(spans) > 2 and _WHOLE_WINDOW[0] <= t / length <= _WHOLE_WINDOW[1]:
        candidates.append(("sall", length))
    return [
        ScaleSample(f"t{text_id}-w{wall_id}-{tag}", float(px), float(value))
        for tag, px in candidates
        if classify_scale_range(value / px) == "inRange"
    ]


def pair_dimension_lines(texts: Sequence[TextPx], walls: Sequence[WallPx]) -> tuple[ScaleSample, ...]:
    """Mẫu tỉ lệ từ chữ kích thước đọc được và tường; sắp theo `id` (`t{i}-w{j}-s{k|all}`).

    Chữ dùng được khi `parse_length_mm` khác `None`; chiều chữ ngang khi rộng ≥ cao. Mỗi chữ chỉ xét tường
    hợp lệ đứng đầu, không lùi sang tường thứ hai. Không luật một cặp mỗi tường: `infer_scale` loại ngoại lai.
    """
    index = _WallIndex.of(walls)
    spans: dict[int, tuple[float, ...]] = {}
    samples: list[ScaleSample] = []
    for text_id, text in enumerate(texts):
        value = parse_length_mm(text.text)
        match = None if value is None else index.nearest(text.box)
        if value is None or match is None:
            continue
        wall_id, t = match
        if wall_id not in spans:
            spans[wall_id] = index.spans(wall_id)
        samples += _samples_of(text_id, wall_id, value, t, float(index.length[wall_id]), spans[wall_id])
    return tuple(sorted(samples, key=lambda sample: sample.id))
