"""Đo đoạn kích thước mà mỗi chữ ghi: đường kích thước sát chữ và hai vạch giới hạn kẹp tâm chữ.

Ghép chữ với tường (`pairing`) chỉ bắt được chữ nằm sát tường; bản vẽ căn hộ thật đặt chuỗi
kích thước ở ngoài căn, xa tường, nên tỉ lệ không bao giờ suy được (bench căn hộ 26/10/2026).
Ở đây đo thẳng trên ảnh: hàng mực phủ kín ngang chữ là đường kích thước, cột có nét đi ra một
phía (vạch giới hạn) hay nét xiên 45° cắt qua đường (vạch xiên CAD) là đầu đoạn. Hàm thuần,
tất định; không đọc chữ, không suy tỉ lệ: `infer_scale` quyết (K19).
"""

from collections.abc import Sequence
from typing import Final

import numpy as np
from numpy.typing import NDArray

from packages.domain.scale import ScaleSample
from packages.ml_contracts.artifacts import BoxPx

INK_DELTA: Final = 12
"""Mực = tối hơn màu nền phổ biến nhất ít nhất 12 mức: đường kích thước CAD xuất ảnh có khi chỉ nhạt hơn nền ~15."""
_LINE_COVER: Final = 0.85
"""Hàng là đường kích thước khi mực phủ >= 85 % đoạn từ (trái chữ - h) tới (phải chữ + h)."""
_SEARCH_ABOVE: Final = 0.8
_SEARCH_BELOW: Final = 1.6
"""Dò đường từ `y_min - 0,8 h` tới `y_max + 1,6 h` (chữ thường nằm trên đường, có khi dưới)."""
_BODY_MARGIN: Final = 0.15
"""Bỏ các hàng giữa thân chữ (trừ 15 % mép trên/dưới, nơi đường hay cắt qua hộp OCR)."""
_LINE_GAP_PX: Final = 3
"""Duỗi đường qua chỗ hở <= 3 px (nét nhoè, chấm giới hạn)."""
_TICK_MIN_PX: Final = 4
_TICK_HEIGHTS: Final = 0.6
"""Vạch giới hạn dài ít nhất `max(4, 0,6 h)` px kể từ đường."""
_TICK_HIT: Final = 0.7
"""Cột là vạch khi >= 70 % số hàng dò có mực."""
_THIN_TICK_PX: Final = 4
"""Nhóm cột vạch mảnh: nét 1 hay 2 px sau khi nở ±1 px còn <= 4 cột."""
_VERTICAL_RATIO: Final = 1.3
"""Hộp cao hơn 1,3 lần rộng là chữ dọc (chuỗi kích thước đứng)."""
_MIN_SPAN_WIDTHS: Final = 1.0
"""Chữ phải lọt trong đoạn của nó: đoạn ngắn hơn bề rộng chữ là vạch giả, hay số nhỏ (100, 220) ghi ra ngoài đoạn."""
_CENTRE_TOLERANCE: Final = 0.15
"""Chữ kích thước ghi giữa đoạn: tâm chữ lệch tâm đoạn <= 15 % đoạn; cặp vạch lệch hơn là vạch giả hay sót."""
CLUSTER_TOLERANCE: Final = 0.03
"""Mẫu cùng cụm khi tỉ số mm/px lệch tâm cụm <= 3 %; mẫu đúng tụ chặt, mẫu rác (vạch sót, chữ đọc sai) rải đều."""

Ink = NDArray[np.bool_]


def ink_mask(gray: NDArray[np.uint8]) -> Ink:
    """Mặt nạ mực: điểm tối hơn màu nền phổ biến nhất ít nhất `INK_DELTA` mức (chịu được nền xám/màu)."""
    background = int(np.argmax(np.bincount(gray.ravel(), minlength=256)))
    return np.asarray(gray <= background - INK_DELTA)


def _line_row(ink: Ink, box: tuple[float, float, float, float]) -> int | None:
    """Hàng của đường kích thước nằm ngang sát chữ; nhiều hàng đạt thì lấy hàng gần hộp chữ nhất, rồi phủ nhiều nhất.

    Gần trước phủ sau: mép tường đậm phủ kín hàng nhưng nằm xa chữ hơn đường kích thước nhạt.
    """
    x0, y0, x1, y1 = box
    height, width = ink.shape
    h = max(y1 - y0, 1.0)
    a, b = max(0, int(x0 - h)), min(width, int(x1 + h))
    if b <= a:
        return None
    best: tuple[float, float, int] | None = None
    for y in range(max(1, int(y0 - _SEARCH_ABOVE * h)), min(height - 1, int(y1 + _SEARCH_BELOW * h))):
        if y0 + _BODY_MARGIN * h < y < y1 - _BODY_MARGIN * h:
            continue
        cover = float(ink[y - 1 : y + 2, a:b].any(axis=0).mean())
        if cover >= _LINE_COVER:
            key = (-max(y0 - y, y - y1, 0.0), cover, y)
            best = key if best is None or key > best else best
    return None if best is None else best[2]


def _line_extent(ink: Ink, y: int, cx: int) -> tuple[int, int]:
    """Hai đầu của đường ở hàng `y`, duỗi từ `cx` sang hai phía qua chỗ hở <= `_LINE_GAP_PX`."""
    row = ink[y - 1 : y + 2].any(axis=0)
    width = row.shape[0]
    ends = []
    for step in (-1, 1):
        x, last, gap = cx, cx, 0
        while 0 <= x + step < width and gap <= _LINE_GAP_PX:
            x += step
            if row[x]:
                last, gap = x, 0
            else:
                gap += 1
        ends.append(last)
    return ends[0], ends[1]


def _near(ink: Ink) -> Ink:
    """Mặt nạ nở ±1 px theo chiều ngang (cửa sổ dò vạch); dựng một lần mỗi chiều cho cả trang."""
    padded = np.pad(ink, ((0, 0), (1, 1)))
    return padded[:, :-2] | padded[:, 1:-1] | padded[:, 2:]


def _ticks(near: Ink, y: int, extent: tuple[int, int], reach: int, text: tuple[float, float]) -> list[float]:
    """Toạ độ vạch giới hạn trên đường: nét đứng ra một phía, hay nét xiên 45° cắt qua đường.

    `near` là `_near` của mặt nạ dò vạch. Cột đạt khi >= `_TICK_HIT` số hàng `d = 2..reach` có mực trong
    cửa sổ ±1 px; cột liền nhau gộp về tâm.
    Cột nằm trong thân chữ `text = (x_min, x_max)` không bao giờ là vạch (nét chữ đứng sát đường).
    Nét đứng chỉ lấy ở phía có nhiều nhóm mảnh hơn: vạch giới hạn của một chuỗi cùng kéo về phía
    căn hộ, phía kia chỉ có nét chữ, đồ đạc, thành khối dày.
    """
    height, width = near.shape
    left, right = extent
    cols = np.arange(left - 2, right + 3)  # vạch ở đúng đầu đường: đủ cửa sổ ±1 px hai bên
    depths = range(2, reach + 1)

    def hits(dy: int, dx: int, d: int) -> NDArray[np.int64]:
        """1 nếu có mực tại hàng `y + dy·d`, cột `c + dx·d`, cho mọi cột `c`; ra ngoài ảnh = 0."""
        row, xs = y + dy * d, cols + dx * d
        ok = (0 <= row < height) & (xs >= 0) & (xs < width)
        return np.where(ok, near[min(max(row, 0), height - 1), np.clip(xs, 0, width - 1)], False).astype(np.int64)

    def count(parts: Sequence[NDArray[np.int64]]) -> NDArray[np.int64]:
        """Tổng theo cột của các mảng 0/1 (`reach` >= 4 nên luôn có ít nhất ba mảng)."""
        return np.sum(np.stack(parts), axis=0)

    hit = _TICK_HIT * len(depths)
    outside = (cols < text[0] - 1) | (cols > text[1] + 1)
    up = (count([hits(-1, 0, d) for d in depths]) >= hit) & outside
    down = (count([hits(1, 0, d) for d in depths]) >= hit) & outside
    rising = count([hits(-1, 1, d) & hits(1, -1, d) for d in depths])
    falling = count([hits(-1, -1, d) & hits(1, 1, d) for d in depths])
    slash = (np.maximum(rising, falling) >= hit) & outside
    side = up if _thin_count(cols[up]) > _thin_count(cols[down]) else down
    return [sum(g) / len(g) for g in _groups(cols[side | slash])]


def _groups(columns: NDArray[np.int64]) -> list[list[int]]:
    """Gom cột liền nhau (cách <= 2 px) thành nhóm, giữ thứ tự tăng dần."""
    groups: list[list[int]] = []
    for c in columns.tolist():
        if groups and c - groups[-1][-1] <= 2:
            groups[-1].append(c)
        else:
            groups.append([c])
    return groups


def _thin_count(columns: NDArray[np.int64]) -> int:
    """Số nhóm mảnh (<= `_THIN_TICK_PX` cột): nét vạch 1 hay 2 px nở ±1 px; nét chữ, mảng đồ đạc rộng hơn."""
    return sum(len(g) <= _THIN_TICK_PX for g in _groups(columns))


def _span(ink: Ink, near: Ink, box: tuple[float, float, float, float]) -> float | None:
    """Độ dài px của đoạn kích thước chứa tâm chữ (đã quy về chữ ngang), hay `None` khi không có đường/vạch.

    Đường dò trên `ink`; vạch dò trên `near` = `_near(bare)` (thân mọi chữ đã xoá) để nét chữ cạnh vạch
    không gộp vào vạch.
    Chọn cặp vạch ngắn nhất kẹp chữ mà tâm chữ lệch tâm đoạn <= `_CENTRE_TOLERANCE` đoạn.
    """
    x0, y0, x1, y1 = box
    y = _line_row(ink, box)
    if y is None:
        return None
    cx = (x0 + x1) / 2
    reach = int(max(_TICK_MIN_PX, _TICK_HEIGHTS * (y1 - y0)))
    ticks = _ticks(near, y, _line_extent(ink, y, int(cx)), reach, (x0, x1))
    shortest = _MIN_SPAN_WIDTHS * (x1 - x0)
    pairs = sorted((b - a, a, b) for a in ticks for b in ticks if a < x0 - 1 and b > x1 + 1 and b - a >= shortest)
    for span, a, b in pairs:
        if abs(cx - (a + b) / 2) <= _CENTRE_TOLERANCE * span:
            return span
    return None


def dimension_spans(gray: NDArray[np.uint8], boxes: Sequence[BoxPx]) -> tuple[float | None, ...]:
    """Đoạn kích thước (px) mà mỗi hộp chữ ghi, cùng thứ tự `boxes`; chữ không nằm trên đường kích thước: `None`.

    Chữ dọc (cao > 1,3 rộng) đo trên ảnh chuyển vị. `gray` là ảnh xám `(H, W)` của trang đã nắn.
    """
    ink = ink_mask(gray)
    vertical = [(b.y_max - b.y_min) > _VERTICAL_RATIO * (b.x_max - b.x_min) for b in boxes]
    bare = ink.copy()
    for box, upright in zip(boxes, vertical, strict=True):
        if upright:  # chữ dọc: "chiều cao" chữ nằm theo x
            m = _BODY_MARGIN * (box.x_max - box.x_min)
            bare[int(box.y_min) : int(box.y_max) + 1, int(box.x_min + m) : int(box.x_max - m) + 1] = False
        else:
            m = _BODY_MARGIN * (box.y_max - box.y_min)
            bare[int(box.y_min + m) : int(box.y_max - m) + 1, int(box.x_min) : int(box.x_max) + 1] = False
    near = _near(bare) if not all(vertical) else bare
    near_t = _near(bare.T) if any(vertical) else bare.T
    spans: list[float | None] = []
    for box, upright in zip(boxes, vertical, strict=True):
        if upright:
            spans.append(_span(ink.T, near_t, (box.y_min, box.x_min, box.y_max, box.x_max)))
        else:
            spans.append(_span(ink, near, (box.x_min, box.y_min, box.x_max, box.y_max)))
    return tuple(spans)


def densest_cluster(samples: Sequence[ScaleSample]) -> tuple[ScaleSample, ...]:
    """Mẫu thuộc cụm tỉ số đông nhất (lệch tâm <= `CLUSTER_TOLERANCE`); hoà mà không quyết được thì rỗng.

    Tâm thử là từng tỉ số của mẫu; O(n²) với n <= vài trăm chữ một trang. Thứ tự đầu vào giữ nguyên.
    Luật hoà (K19, không đoán): các cụm đông nhất từng đôi có chung mẫu là một tỉ lệ nhìn từ tâm thử
    kề nhau → cụm có tâm nhỏ nhất; có hai cụm đông nhất rời nhau (vd. mặt bằng 1:100 và chi tiết 1:50
    cùng số mẫu) → `()`, để bước dựng rơi về ghép tường hay `project_default`.
    """
    ratios = [sample.real_length_mm / sample.pixel_length for sample in samples]
    best: list[set[int]] = []
    for centre in sorted(ratios):
        members = {k for k, r in enumerate(ratios) if abs(r - centre) <= CLUSTER_TOLERANCE * centre}
        if not best or len(members) > len(best[0]):
            best = [members]
        elif len(members) == len(best[0]):
            best.append(members)
    if not best or any(a.isdisjoint(b) for a in best for b in best):
        return ()
    return tuple(samples[k] for k in sorted(best[0]))
