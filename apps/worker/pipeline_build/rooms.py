"""Phòng và đồ đạc từ tường đã dựng (B5-05 [6] bước 5, 6).

Toạ độ vào của `build_rooms`/`build_furniture` đã là mm (`Wall`, `bridges`) trừ hộp/chữ của
`build_furniture`/tên phòng vẫn còn px, đổi bằng `scaling`. Toàn hàm thuần, không sửa đối số.
"""

import math
from collections import Counter
from collections.abc import Sequence

import numpy as np
import shapely
from shapely.geometry.base import BaseGeometry
from shapely.ops import split

from apps.worker.pipeline_build.constants import (
    MIN_ROOM_AREA_M2,
    ROOM_GAP_ALIGNED_COS,
    ROOM_GAP_CLOSE_MIN_COS,
    ROOM_GAP_CLOSE_MM,
    ROOM_GAP_EVIDENCE_MM,
    ROOM_SNAP_MM,
)
from apps.worker.pipeline_build.geometry import Geoms, RoomCloser, Scaling
from apps.worker.pipeline_build.ids import new_spatial_id
from packages.core.clock import Clock
from packages.domain.rules_ai import LOW_CONFIDENCE_CAP
from packages.domain.spatial import BoundingBox, Furniture, Point, Room, Wall, js_round, polygon_area_m2
from packages.ml_contracts.artifacts import DetectionPx, TextPx
from packages.ml_contracts.labels import LABEL_TARGETS
from packages.vision.dimensions.rooms import ROOM_USAGE_NAMES, RoomLabel, RoomUsage, match_room_label, name_rooms

_OPENING_LABELS = frozenset({"door", "double_door", "window"})
_SOFA_LONG_MM = 1400
_SOFA_SHORT_MM = (600, 1600)
"""Cạnh ngắn sofa tới 1600 mm: sofa góc chữ L (B10)."""
_BENCH_LONG_MM = 1000
_BENCH_SHORT_MM = 600
_BENCH_TABLE_GAP_MM = 900.0
"""Ghế dài ≥ 1000, cạnh ngắn < 600, cách bàn ≤ 900 mm → băng ghế (`variant="bench"`, B10)."""
_BED_SHORT_MM = (900, 2000)
_BED_LONG_MM = (1900, 2200)
"""U34: khung mm (cạnh ngắn, cạnh dài) để sửa nhãn YOLO `chair`/`other` theo kích thước thật."""
_NO_BED_USAGES = frozenset({"livingRoom", "kitchen", "bathroom", "corridor", "loggia"})
"""Phòng không đặt giường: bộ sofa + bàn trà ở phòng khách cũng cỡ giường (ch-13)."""
"""Nhãn ô mở: bỏ qua ở `build_furniture`, không đếm vào `dropped` (đã dựng ở bước 4)."""

_USAGE_PRIORITY: tuple[RoomUsage, ...] = (
    "other",
    "stairwell",
    "corridor",
    "utility",
    "loggia",
    "bathroom",
    "kitchen",
    "bedroom",
    "livingRoom",
)
"""Thứ tự tăng dần: công năng đứng sau thắng khi một phòng có nhiều nhãn (sảnh, kho, WC là phần phụ)."""

_DOOR_REACH_MM = 300.0
"""Khoảng lệch cho phép giữa hộp cửa và khe (cánh cửa vẽ cạnh tường, hộp không trùng tim tường)."""

_DOOR_SPAN_RATIO = (0.6, 1.8)
"""Khe cửa dài 0,6-1,8 lần cạnh dài hộp cửa (hộp chỉ ôm cánh, khe tính tới tim tường hai bên)."""

_PARALLEL_COS = 0.9
"""Tường gần song song khe (|cos| ≥ 0,9) bắn tia theo hướng ra của nó: đầu tường nằm trong hộp cửa sổ thì tâm hộp
có thể ở phía thân tường."""

_RIM_DEPTH_MM = 6000.0
"""Lô gia nằm trong 6 m tính từ biên bao: chỉ chia ô bằng đường trong dải đó."""

_RIM_M2 = (1.5, 15.0)
_RIM_FILL = 0.7
_RIM_WALLED = 0.5
"""Mảnh trống ở rìa thành lô gia khi 1,5-15 m², ≥ 70 % hộp bao, ≥ 3 cạnh hộp bao sát đường khép ≥ 50 %."""

_ENVELOPE_CLOSE_MM = 2000.0
"""Bán kính đóng hình thái của đường bao căn (`_envelope_outlines`): khép khe mặt ngoài ≤ 4 m."""

_ENVELOPE_MIN_M2 = 4.0
_ENVELOPE_WALLED = 2
_ENVELOPE_WRAP = 0.5
"""Ô mới của đường bao thành phòng khi ≥ 2 cạnh hộp bao sát đường khép, chứa nhãn chữ hay rộng ≥ 4 m², và bao lồi của
nó chồng phòng có sẵn ≤ 0,5 lần diện tích ô (bench-3d r3: vành giữa căn và khung ảnh 0,70; phòng thật ≤ 0,38)."""

_SEED_RAY_MM = 6000
"""Tia của phòng mọc từ nhãn dài nhất 6 m: xa hơn là chữ nằm ngoài căn hộ (tên bản vẽ, ghi chú)."""

_SEED_MAX_M2 = 40.0
"""Phòng mọc từ nhãn lớn hơn là hộp tràn qua chỗ thiếu tường, không dựng."""

_KITCHEN_RUN_MM = 2000
"""Dãy tủ bếp: cạnh dài hộp ≥ 2 m (bàn lavabo phòng tắm 0,6-1,2 m; bench: 1,5 m còn 2 phòng tắm thành bếp)."""

_WARDROBE_MIN_MM = 900
"""Tủ áo có cạnh dài ngắn hơn không làm phòng ngủ: kệ/tủ nhỏ ở lô gia, phòng tắm."""

_WET_LABELS = frozenset({"washing_machine", "sanitary_fixture", "shower"})
"""Phòng có máy giặt/thiết bị vệ sinh không thành phòng ngủ vì tủ áo."""

_OUTSIDE_SHARE = 0.3
_OUTSIDE_REACH_MM = 300.0
"""Đồ giao mọi phòng < 30 % hộp và tâm ngoài hợp phòng nới 300 mm là đồ ngoài căn (sơ đồ vị trí, ảnh minh hoạ)."""

_BATHROOM_MAX_M2 = 10.0
"""Phòng có thiết bị vệ sinh mà rộng hơn là phòng ngủ có WC riêng hay bếp có chậu rửa, không phải phòng tắm."""

_BEDROOM_MIN_M2 = 6.0
_BEDROOM_MAX_M2 = 25.0
_WARDROBE_BEDROOM_MIN_M2 = 8.0
"""Giường trong phòng 6-25 m² là phòng ngủ trước mọi luật khác: thiết bị vệ sinh dò nhầm (ghế, bàn học) không biến
phòng ngủ thành phòng tắm (H-08 ch-01: phòng ngủ 9,5 m² thành "phòng tắm 3"); lớn hơn là vùng gộp (bench-3d cn-19:
khách-bếp 40 m² có giường thành "phòng ngủ").

Tủ áo đơn lẻ chỉ làm phòng ngủ ở 8-25 m²: nhỏ hơn là kho / phòng thay đồ (bench-3d ch-06, cn-05: kho 6,7-7,6 m²),
lớn hơn là phòng khách có kệ tủ."""

_FACADE_MM = 3000.0
_FACADE_LOGGIA_M2 = (2.0, 15.0)
_NOT_LOGGIA = frozenset({"bed", "sanitary_fixture", "shower"})
"""Mặt ngoài nhà: cạnh phòng trong 2·`ROOM_SNAP_MM` quanh biên bao lồi của đường khép (tường kéo dài `ROOM_SNAP_MM`
nên biên bao cách tim tường mặt ngoài đúng `ROOM_SNAP_MM`).

Phòng chưa có tên (chữ, rìa, đồ đạc) 2-15 m², ≥ 3 m cạnh trên mặt ngoài, không giường/thiết bị vệ sinh → lô gia
(bench-3d r1: 18/21 phòng "khác" như thế là lô gia/ban công/giặt phơi), khi tầng có nhãn chữ. Nhánh thứ hai cho mọi
tầng đã đọc được (nhãn chữ hay tên suy từ đồ đạc; bản vẽ căn hộ VN hay không ghi tên phòng, bench-3d r2: 17 lô gia
thành "phòng khác"): phòng còn phải hẹp (cạnh ngắn hộp bao xoay ≤ `_LOGGIA_DEPTH_MM`), và mặt ngoài là phần lớn hơn
của cạnh trên biên bao lồi hay cạnh không giáp phòng nào (`_exposed_lengths`: lô gia lõm vào mặt nhà nằm xa biên bao
lồi, bench-3d r2 cn-07, cn-16). Rủi ro biết trước: cạnh không giáp phòng tính so với phòng đã khép, nên phòng hẹp
không tên giáp ô thang/giếng trời không khép thành phòng cũng thành lô gia. Tầng không đọc được gì (ảnh âm bản, OCR
và dò đồ hỏng) thì mọi phòng đều "khác", đoán lô gia là đoán mù. Máy giặt + ≥ 3 m mặt ngoài (không buồng tắm
đứng) → lô gia trước luật thiết bị vệ sinh: chậu giặt dò thành `sanitary_fixture`."""

_LOGGIA_DEPTH_MM = 2000.0
"""Lô gia/ban công sâu ≤ 2 m (bench-3d r2: 0,99-1,91 m); phòng không tên rộng hơn ở mặt ngoài là kho, phòng phụ."""

_OPEN_SPACE_M2 = 18.0
"""Không gian mở khách-bếp-ăn: tầng chưa có phòng khách thì "bếp"/"hành lang" rộng hơn số này → phòng khách (bếp
riêng căn hộ ≤ 15 m²; bench-3d r2: 17/17 "bếp" 24-52 m² là khách + bếp + ăn, "hành lang" 27 m² ch-11 là phòng khách).
Còn chưa có phòng khách thì phòng không tên lớn nhất, rộng hơn số này, của tầng đã đọc được → phòng khách.

"Hành lang" và phòng không tên chỉ đổi khi không hẹp (chứa được hình tròn đường kính `_CORRIDOR_DEPTH_MM`): hành
lang căn hộ, hành lang chung tầng điển hình rộng 1,2-2 m dù dài trên 18 m² hay gấp chữ L/T (hộp bao sâu ~6 m) vẫn là
hành lang (BENCH3D-14)."""

_CORRIDOR_DEPTH_MM = 2500.0

_SHAFT_M2 = 2.5
_DOOR_LABELS = frozenset({"door", "double_door"})
"""Hộp kỹ thuật: phòng chưa có tên < 2,5 m² không hộp cửa đi nào chạm biên (nới `ROOM_SNAP_MM`) → `utility` tên
"hộp kỹ thuật" (bench-3d cn-01, cn-06, huge-ch03: ô 1-1,6 m² giữa tường thành "phòng 7")."""

_DINING_LABELS = frozenset({"table", "chair"})
"""Tủ bếp (kể cả ngắn) cùng bàn/ghế ăn trong phòng > 10 m² → bếp; tủ áo cạnh tủ bếp không làm phòng ngủ.

Dãy tủ đo ở tỉ lệ đoán (`project_default`) có thể ngắn hơn `_KITCHEN_RUN_MM`: H-08 ch-01 khu khách-bếp-ăn có
tủ bếp 2,1 m (1,8 m ở tỉ lệ đoán) và một kệ dò thành tủ áo nên thành "phòng ngủ"."""

_T_JUNCTION_COS = 0.1
"""Khe dài chĩa thẳng vào tường đích vuông góc (|cos| ≤ 0,1, ~84-90°) là chữ T thiếu đoạn tường (QT-ROOMS3, NO-435)."""

_CLOSER_TRIM_MM = 1.0
"""Cắt bớt mỗi đầu đoạn nối khe khi xét cắt tường: chạm đúng đầu mút (chân chữ T) không tính là cắt."""


def _extend(wall: Wall, amount: float) -> shapely.LineString:
    """Đường tim `wall` kéo dài `amount` mm về mỗi đầu, theo hướng tường (bước 5)."""
    start, end = wall.centreline.start, wall.centreline.end
    dx, dy = end.x - start.x, end.y - start.y
    length = math.hypot(dx, dy)
    ux, uy = dx / length, dy / length
    return shapely.LineString(
        [(start.x - ux * amount, start.y - uy * amount), (end.x + ux * amount, end.y + uy * amount)]
    )


def _gap_closers(
    walls: Sequence[Wall],
    bridges: Sequence[tuple[Point, Point]],
) -> list[shapely.LineString]:
    """Đoạn nối khe góc/chữ T (BUG-IT-008), để khép phòng; tường không đổi.

    Đầu tường tự do = không chạm tim tường khác hay `bridges` trong `ROOM_SNAP_MM`. Mỗi đầu tự do nối tới điểm gần nhất
    trên tim tường khác, lệch hướng ra của đầu tường không quá `ROOM_GAP_CLOSE_MIN_COS`; bỏ đoạn cắt tim tường/`bridges`
    khác, giữ đoạn ngắn nhất. Khe ≤ `ROOM_GAP_CLOSE_MM` luôn khép; dài hơn tới `ROOM_GAP_EVIDENCE_MM` chỉ khép khi có
    bằng chứng: đoạn nối dọc tường (`ROOM_GAP_ALIGNED_COS`), lệch ngang ≤ `ROOM_SNAP_MM` (vách so le hai bên khe
    cửa không tính, OPEN-ATTACH), và hoặc tường đích song song, chân đoạn ở đầu tường đích (thẳng hàng, QT-ROOMS2
    B9), hoặc tường đích vuông góc `_T_JUNCTION_COS` và chân đoạn không ở đầu tự do của nó (chữ T thiếu đoạn,
    QT-ROOMS3; góc chữ L hở hai đầu tự do không khép); không quá nửa đoạn sát tim tường khác. Khe có hộp ô mở đã do
    `_door_closers` khép. Ngưỡng mm cố định làm số phòng lệ thuộc tỉ lệ: ch-09 ở 14,32 mm/px khép 4 khe 1,1-1,2 m, ở
    tỉ lệ đúng 24,66 các khe đó thành 1,9-2,1 m (chữ T, NO-435). Tra theo lô bằng `STRtree` (không O(n²), trần
    B5-01 20 000 tường); đoạn chọn lố 1 mm qua tim đích để `unary_union` cắt nút.
    """
    if len(walls) < 2:
        return []
    starts = np.array([(w.centreline.start.x, w.centreline.start.y) for w in walls], dtype=float)
    ends = np.array([(w.centreline.end.x, w.centreline.end.y) for w in walls], dtype=float)
    centrelines: Geoms = np.asarray(shapely.linestrings(np.stack([starts, ends], axis=1)), dtype=object)
    bridge_lines = [shapely.LineString([(a.x, a.y), (b.x, b.y)]) for a, b in bridges]
    obstacles: Geoms = np.asarray([*centrelines.tolist(), *bridge_lines], dtype=object)
    obstacle_tree = shapely.STRtree(obstacles)
    tips: Geoms = np.asarray(shapely.points(np.concatenate([starts, ends])), dtype=object)
    owner = np.tile(np.arange(len(walls)), 2)
    tip_idx, near = obstacle_tree.query(tips, predicate="dwithin", distance=ROOM_SNAP_MM)
    touching = np.zeros(len(tips), dtype=np.bool_)
    touching[tip_idx[near != owner[tip_idx]]] = True
    free = np.flatnonzero(~touching)
    free_idx, target = shapely.STRtree(centrelines).query(
        tips[free], predicate="dwithin", distance=ROOM_GAP_EVIDENCE_MM
    )
    tip = free[free_idx]
    other = target != owner[tip]
    tip, target = tip[other], target[other]
    if tip.size == 0:
        return []
    coords = shapely.get_coordinates(shapely.shortest_line(tips[tip], centrelines[target])).reshape(-1, 2, 2)
    head, foot = coords[:, 0], coords[:, 1]
    length = np.hypot(*(foot - head).T)
    unit = (foot - head) / length[:, None]
    trimmed: Geoms = np.asarray(
        shapely.linestrings(np.stack([head + unit * _CLOSER_TRIM_MM, foot - unit * _CLOSER_TRIM_MM], axis=1)),
        dtype=object,
    )
    seg_idx, blocker = obstacle_tree.query(trimmed, predicate="intersects")
    outward = np.concatenate([starts - ends, ends - starts])[tip]
    outward /= np.hypot(*outward.T)[:, None]
    along = np.einsum("ij,ij->i", unit, outward)
    blocked = along < ROOM_GAP_CLOSE_MIN_COS
    blocked[seg_idx[blocker != target[seg_idx]]] = True
    direction = (ends - starts) / np.hypot(*(ends - starts).T)[:, None]
    parallel = np.abs(np.einsum("ij,ij->i", direction[owner[tip]], direction[target])) >= ROOM_GAP_ALIGNED_COS
    at_start = np.hypot(*(foot - starts[target]).T) <= ROOM_SNAP_MM
    at_end = np.hypot(*(foot - ends[target]).T) <= ROOM_SNAP_MM
    foot_at_end = at_start | at_end
    foot_at_free = (at_start & ~touching[target]) | (at_end & ~touching[target + len(walls)])
    own = direction[owner[tip]]
    lateral = np.abs(own[:, 0] * (foot - head)[:, 1] - own[:, 1] * (foot - head)[:, 0]) <= ROOM_SNAP_MM
    square = np.abs(np.einsum("ij,ij->i", direction[owner[tip]], direction[target])) <= _T_JUNCTION_COS
    square &= ~foot_at_free
    evidence = (along >= ROOM_GAP_ALIGNED_COS) & lateral & ((parallel & foot_at_end) | square)
    long_gap = length > ROOM_GAP_CLOSE_MM
    blocked |= long_gap & ~evidence
    for k in np.flatnonzero(long_gap & ~blocked):  # khe dài chạy dọc tường khác quá nửa: mép vách, không phải khe
        near = obstacle_tree.query(trimmed[k], predicate="dwithin", distance=ROOM_SNAP_MM)
        walled = shapely.union_all(obstacles[near[near != owner[tip[k]]]]).buffer(ROOM_SNAP_MM)
        blocked[k] = trimmed[k].intersection(walled).length > length[k] / 2
    valid = np.flatnonzero(~blocked)
    order = valid[np.lexsort((length[valid], tip[valid]))]
    _, first = np.unique(tip[order], return_index=True)
    chosen = order[first]
    tails = foot[chosen] + unit[chosen] * _CLOSER_TRIM_MM
    closers: Geoms = np.asarray(shapely.linestrings(np.stack([head[chosen], tails], axis=1)), dtype=object)
    return [shapely.LineString(line) for line in closers.tolist()]


def _outline_points(polygon: shapely.Polygon) -> list[Point]:
    """Vành ngoài của `polygon` thành điểm mm `js_round`, bỏ điểm trùng liên tiếp và điểm khép."""
    points = [Point(x=js_round(x), y=js_round(y)) for x, y in polygon.exterior.coords[:-1]]
    deduped: list[Point] = []
    for point in points:
        if not deduped or deduped[-1] != point:
            deduped.append(point)
    if len(deduped) > 1 and deduped[0] == deduped[-1]:
        deduped.pop()
    return deduped


def _door_closers(
    walls: Sequence[Wall], detections: Sequence[DetectionPx], scaling: Scaling
) -> list[tuple[shapely.LineString, str]]:
    """Đoạn khép khe cửa đi và cửa sổ theo hộp dò được, kể cả khe giữa một góc tường và tường đối diện (đầu ở góc
    không là đầu tự do nên `_gap_closers` bỏ qua). Cửa sổ tính vì vách kính, cửa lô gia vẽ nét mảnh: model tường
    một lớp bỏ sót, phòng ngủ tràn ra lô gia (bench căn hộ ch-08).

    Mỗi ô mở: từ mọi đầu tường cách tâm hộp ≤ cạnh dài + `_DOOR_REACH_MM`, bắn tia dọc cạnh dài của hộp (về phía tâm,
    hay theo hướng ra của tường khi tường gần song song khe — `_PARALLEL_COS`) tới tim tường đầu tiên không chứa đầu
    đó. Giữ đoạn: dài `_DOOR_SPAN_RATIO` lần cạnh dài (cận dưới so với phần hộp còn phía trước đầu tường nằm trong
    hộp: hộp cửa sổ ôm cả mẩu tường đã dò); không nằm đè tường quá nửa; lệch ngang khỏi tâm hộp ≤
    min(`_DOOR_REACH_MM`, 1/4 cạnh dài) + nửa cạnh ngắn; đi qua gần tâm hộp (≤ nửa cạnh dài + `_DOOR_REACH_MM`).
    Lấy đoạn ngắn nhất, kèm nhãn hộp. Hộp lệch tim tường vài chục mm (cánh cửa vẽ cạnh
    tường) vẫn khép được, việc mà phép phủ hộp của 3b không làm được.
    """
    openings = [d for d in detections if d.label in _OPENING_LABELS]
    if not openings or len(walls) < 2:
        return []
    centrelines = [
        shapely.LineString([(w.centreline.start.x, w.centreline.start.y), (w.centreline.end.x, w.centreline.end.y)])
        for w in walls
    ]
    tree = shapely.STRtree(centrelines)
    tips = [(w.centreline.start, w.centreline.end, i) for i, w in enumerate(walls)]
    tips += [(w.centreline.end, w.centreline.start, i) for i, w in enumerate(walls)]
    tip_points = shapely.STRtree([shapely.Point(p.x, p.y) for p, _, _ in tips])
    closers: list[tuple[shapely.LineString, str]] = []
    for door in openings:
        low = scaling.point(door.box.x_min, door.box.y_min)
        high = scaling.point(door.box.x_max, door.box.y_max)
        width, height = high.x - low.x, high.y - low.y
        length, short = max(width, height), min(width, height)
        if length <= 0:
            continue
        axis = (1.0, 0.0) if width >= height else (0.0, 1.0)
        centre = shapely.Point((low.x + high.x) / 2, (low.y + high.y) / 2)
        best: shapely.LineString | None = None
        for slot in tip_points.query(centre.buffer(length + _DOOR_REACH_MM)):
            tip, base, owner = tips[int(slot)]
            run = math.hypot(tip.x - base.x, tip.y - base.y)
            along = ((tip.x - base.x) * axis[0] + (tip.y - base.y) * axis[1]) / run if run else 0.0
            if abs(along) >= _PARALLEL_COS:
                towards = 1.0 if along > 0 else -1.0
            else:
                towards = 1.0 if (centre.x - tip.x) * axis[0] + (centre.y - tip.y) * axis[1] >= 0 else -1.0
            far = (high.x if towards > 0 else low.x) if axis[0] else (high.y if towards > 0 else low.y)
            ahead = (far - (tip.x if axis[0] else tip.y)) * towards
            offset = abs((centre.y - tip.y) * axis[0] + (centre.x - tip.x) * axis[1])
            if ahead <= 0 or offset > min(_DOOR_REACH_MM, length / 4) + short / 2:
                continue
            gap = min(ahead, length)
            reach = length * _DOOR_SPAN_RATIO[1] + ROOM_SNAP_MM
            end = (tip.x + towards * axis[0] * reach, tip.y + towards * axis[1] * reach)
            ray = shapely.LineString([(tip.x, tip.y), end])
            origin = shapely.Point(tip.x, tip.y)
            hits = [
                origin.distance(ray.intersection(centrelines[int(i)]))
                for i in tree.query(ray, predicate="intersects")
                if int(i) != owner and centrelines[int(i)].distance(origin) > ROOM_SNAP_MM
            ]
            if not hits:
                continue
            span = min(hits)
            if not _DOOR_SPAN_RATIO[0] * gap <= span <= _DOOR_SPAN_RATIO[1] * length:
                continue
            foot = (tip.x + towards * axis[0] * (span + 1), tip.y + towards * axis[1] * (span + 1))
            segment = shapely.LineString([(tip.x, tip.y), foot])
            if segment.distance(centre) > length / 2 + _DOOR_REACH_MM:
                continue
            walled = shapely.union_all([centrelines[int(i)] for i in tree.query(segment.buffer(ROOM_SNAP_MM))])
            if segment.intersection(walled.buffer(ROOM_SNAP_MM)).length > segment.length / 2:
                continue
            if best is None or segment.length < best.length:
                best = segment
        if best is not None:
            closers.append((best, door.label))
    return closers


def _room_closer(line: shapely.LineString, label: str | None) -> RoomCloser:
    """Đoạn khép (shapely, mm) → `RoomCloser` với hai đầu `js_round`."""
    (x0, y0), (x1, y1) = line.coords
    return RoomCloser(Point(x=js_round(x0), y=js_round(y0)), Point(x=js_round(x1), y=js_round(y1)), label)


def _room_lines(walls: Sequence[Wall], bridges: Sequence[tuple[Point, Point]]) -> list[shapely.LineString]:
    """Tường kéo dài `ROOM_SNAP_MM` và `bridges`; `build_rooms` thêm `_gap_closers`, `_door_closers`."""
    lines: list[shapely.LineString] = [_extend(wall, ROOM_SNAP_MM) for wall in walls]
    lines.extend(shapely.LineString([(a.x, a.y), (b.x, b.y)]) for a, b in bridges)
    return lines


_SPLIT_OPEN_MAX_MM = 2500
"""Vết cắt tách phòng theo nhãn: phần không có tường (kéo dài vách cụt tới biên) dài tối đa 2,5 m."""


def _split_by_labels(
    outlines: Sequence[Sequence[Point]],
    walls: Sequence[Wall],
    parsed: Sequence[RoomLabel | None],
    centres: Sequence[Point],
) -> list[list[Point]]:
    """Phòng chứa ≥ 2 nhãn tên phòng → cắt dọc tường cụt kéo dài tới biên, vết cắt hở ngắn nhất tách được nhãn (UX-04).

    Không đủ hai nhãn thì không cắt; mỗi mảnh phải còn nhãn và ≥ `MIN_ROOM_AREA_M2`. Cắt lặp tới khi mỗi mảnh một nhãn.
    """
    labels = [shapely.Point(c.x, c.y) for c, label in zip(centres, parsed, strict=True) if label is not None]
    lines = [
        shapely.LineString([(w.centreline.start.x, w.centreline.start.y), (w.centreline.end.x, w.centreline.end.y)])
        for w in walls
    ]
    if len(labels) < 2:
        return [list(outline) for outline in outlines]
    label_tree = shapely.STRtree(labels)
    line_tree = shapely.STRtree(lines)
    result: list[list[Point]] = []
    stack: list[tuple[shapely.Polygon, list[Point] | None]] = []
    for outline in outlines:
        if len(outline) < 3:
            result.append(list(outline))
        else:
            stack.append((shapely.Polygon([(p.x, p.y) for p in outline]), list(outline)))
    while stack:
        polygon, original = stack.pop()
        inside = [labels[int(i)] for i in label_tree.query(polygon, predicate="contains")]
        if len(inside) < 2:
            best = None
        else:
            near = line_tree.query(polygon.buffer(ROOM_SNAP_MM), predicate="intersects")
            best = _best_cut(polygon, [lines[int(i)] for i in sorted(near)], inside)
        if best is None:
            result.append(original if original is not None else _outline_points(polygon))
        else:
            stack.extend((piece, None) for piece in best)
    return result


def _best_cut(
    polygon: shapely.Polygon, lines: Sequence[shapely.LineString], labels: Sequence[shapely.Point]
) -> list[shapely.Polygon] | None:
    """Hai mảnh của vết cắt (đường tim tường kéo dài trong `polygon`) có phần hở ngắn nhất, hoặc `None`.

    `lines` đã lọc sẵn: chỉ đường chạm `polygon` nới `ROOM_SNAP_MM`.
    """
    best: tuple[float, list[shapely.Polygon]] | None = None
    for line in lines:
        (x0, y0), (x1, y1) = line.coords
        if line.length == 0:
            continue
        ux, uy = (x1 - x0) / line.length, (y1 - y0) / line.length
        far = shapely.LineString([(x0 - ux * 1e6, y0 - uy * 1e6), (x1 + ux * 1e6, y1 + uy * 1e6)])
        crossing = polygon.intersection(far)
        for cut in getattr(crossing, "geoms", [crossing]):
            if not isinstance(cut, shapely.LineString) or cut.distance(line) > ROOM_SNAP_MM:
                continue
            open_mm = cut.length - cut.intersection(line.buffer(ROOM_SNAP_MM)).length
            if open_mm > _SPLIT_OPEN_MAX_MM or (best is not None and open_mm >= best[0]):
                continue
            pieces = [g for g in split(polygon, cut).geoms if isinstance(g, shapely.Polygon)]
            if len(pieces) != 2 or min(g.area for g in pieces) / 1e6 < MIN_ROOM_AREA_M2:
                continue
            if all(any(g.contains(label) for label in labels) for g in pieces):
                best = (open_mm, pieces)
    return None if best is None else best[1]


def _room_outlines(lines: Sequence[shapely.LineString]) -> list[list[Point]]:
    """Mọi vành ngoài khép được từ `lines` (`polygonize`)."""
    if not lines:
        return []
    merged = shapely.unary_union(lines)
    segments = list(merged.geoms) if hasattr(merged, "geoms") else [merged]
    polygons = shapely.polygonize(segments)
    return [_outline_points(polygon) for polygon in polygons.geoms]


def _seeded_outlines(
    lines: Sequence[shapely.LineString],
    rooms: Sequence[Sequence[Point]],
    labels: Sequence[RoomLabel | None],
    centres: Sequence[Point],
) -> list[list[Point]]:
    """Phòng mọc từ nhãn chữ nằm ngoài mọi phòng đã khép (lô gia biên ngoài là lan can, không gian mở hở cửa).

    Bốn tia ngang/dọc từ tâm chữ tới đường khép gần nhất hay biên bao lồi của tường (thay lan can), dài ≤
    `_SEED_RAY_MM`; đủ bốn phía mới dựng hộp, trừ các phòng đã có, giữ mảnh chứa tâm chữ. Nhãn đã nằm trong một
    phòng (kể cả phòng vừa mọc) bị bỏ qua. Phòng và đường tra bằng `STRtree` (K18: 5 000 chữ x 20 000 tường).
    """
    seeds = [centre for label, centre in zip(labels, centres, strict=True) if label is not None]
    if not lines or not seeds:
        return []
    hull = shapely.convex_hull(shapely.MultiLineString(list(lines)))
    if not isinstance(hull, shapely.Polygon):
        return []
    obstacles = shapely.STRtree([*lines, hull.exterior])
    closed = [shapely.Polygon([(p.x, p.y) for p in outline]) for outline in rooms if len(outline) >= 3]
    closed_tree = shapely.STRtree(closed)
    grown: list[shapely.Polygon] = []
    seeded: list[list[Point]] = []
    for centre in seeds:
        point = shapely.Point(centre.x, centre.y)
        if (
            not hull.contains(point)
            or len(closed_tree.query(point, predicate="within"))
            or any(g.contains(point) for g in grown)
        ):
            continue
        reach: list[float] = []
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ray = shapely.LineString(
                [(centre.x, centre.y), (centre.x + dx * _SEED_RAY_MM, centre.y + dy * _SEED_RAY_MM)]
            )
            near = obstacles.query(ray, predicate="intersects")
            if len(near):
                reach.append(
                    float(min(shapely.distance(point, ray.intersection(obstacles.geometries[i])) for i in near))
                )
        if len(reach) < 4:
            continue
        left, right, up, down = reach
        box = shapely.box(centre.x - left, centre.y - up, centre.x + right, centre.y + down)
        blockers = [closed[i] for i in closed_tree.query(box, predicate="intersects")] + grown
        free = box.difference(shapely.unary_union(blockers)) if blockers else box
        parts = list(free.geoms) if hasattr(free, "geoms") else [free]
        piece = next((part for part in parts if isinstance(part, shapely.Polygon) and part.intersects(point)), None)
        if piece is None or piece.area / 1e6 > _SEED_MAX_M2:
            continue
        seeded.append(_outline_points(shapely.Polygon(piece.exterior)))
        grown.append(piece)
    return seeded


def _rim_outlines(lines: Sequence[shapely.LineString], rooms: Sequence[Sequence[Point]]) -> list[list[Point]]:
    """Lô gia không có nhãn: ô do đường khép và biên bao lồi của chúng chia ra (mặt ngoài lan can thay bằng biên bao),
    chưa thuộc phòng nào, chạm biên bao, rộng `_RIM_M2`, gần chữ nhật (≥ `_RIM_FILL` hộp bao) và ≥ 3 cạnh hộp bao có
    ≥ `_RIM_WALLED` sát đường khép (phần lồi của biên bao ngoài căn hộ chỉ sát tường một hai mặt).

    Chỉ chia ô bằng đường trong `_RIM_DEPTH_MM` quanh biên bao, tra phòng và đường bằng `STRtree` (K18: trần
    20 000 tường không được gộp toàn bộ).
    """
    if not lines:
        return []
    hull = shapely.convex_hull(shapely.MultiLineString(list(lines)))
    if not isinstance(hull, shapely.Polygon):
        return []
    line_tree = shapely.STRtree(list(lines))
    near_rim = [lines[int(i)] for i in line_tree.query(hull.exterior.buffer(_RIM_DEPTH_MM), predicate="intersects")]
    polygons = [shapely.Polygon([(p.x, p.y) for p in o]) for o in rooms if len(o) >= 3]
    room_tree = shapely.STRtree(polygons)
    rim = hull.exterior.buffer(ROOM_SNAP_MM)
    merged = shapely.unary_union([*near_rim, hull.exterior])
    faces = shapely.polygonize(list(merged.geoms) if hasattr(merged, "geoms") else [merged])
    found: list[list[Point]] = []
    for face in faces.geoms:
        if not isinstance(face, shapely.Polygon):
            continue
        if not _RIM_M2[0] <= face.area / 1e6 <= _RIM_M2[1] or not face.intersects(rim):
            continue
        overlap = sum(face.intersection(polygons[int(i)]).area for i in room_tree.query(face, predicate="intersects"))
        if overlap > 0.5 * face.area:
            continue
        x0, y0, x1, y1 = face.bounds
        if face.area < _RIM_FILL * (x1 - x0) * (y1 - y0):
            continue
        if _walled_sides(face, _near_walls(face, lines, line_tree)) < 3:
            continue
        found.append(_outline_points(shapely.Polygon(face.exterior)))
    return found


def _near_walls(face: shapely.Polygon, lines: Sequence[shapely.LineString], line_tree: shapely.STRtree) -> BaseGeometry:
    """Đường khép quanh `face`, nới `ROOM_SNAP_MM` (tra `line_tree` của `lines`)."""
    near = line_tree.query(face.buffer(ROOM_SNAP_MM), predicate="intersects")
    return shapely.unary_union([lines[int(i)] for i in near]).buffer(ROOM_SNAP_MM)


def _walled_sides(face: shapely.Polygon, near_walls: BaseGeometry) -> int:
    """Số cạnh hộp bao của `face` có ≥ `_RIM_WALLED` chiều dài trong `near_walls` (`_near_walls`)."""
    x0, y0, x1, y1 = face.bounds
    sides = [
        shapely.LineString(side)
        for side in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0)))
    ]
    return sum(side.intersection(near_walls).length >= _RIM_WALLED * side.length for side in sides)


def _envelope_outlines(
    lines: Sequence[shapely.LineString],
    bare: Sequence[shapely.LineString],
    rooms: Sequence[Sequence[Point]],
    labels: Sequence[RoomLabel | None],
    centres: Sequence[Point],
) -> list[tuple[list[Point], bool]]:
    """Phòng hở ra mặt ngoài: ô do đường khép `lines` và đường bao căn chia ra, kèm cờ lô gia.

    `polygonize` chỉ cho phòng có vòng kín, nên một khe mặt ngoài (vách kính, cửa lùa, lan can lô gia: model tường
    một lớp bỏ nét mảnh) làm mất cả phòng, kể cả khách-bếp lớn không có nhãn hay nhãn ở bảng bên (bench-3d r3: 19
    nhãn ở 11 ca không thuộc phòng nào). Đường bao là đóng hình thái của `bare` (như `lines` nhưng tường không kéo
    dài, để bao trùng tim tường mặt ngoài và đi qua đúng đầu tường ở khe): nới `_ENVELOPE_CLOSE_MM`, lấp lỗ, co lại.
    Nên bao chỉ nằm trong vùng có tường của căn, khép khe mặt ngoài ≤ 2·`_ENVELOPE_CLOSE_MM` theo thẳng tường hai bên,
    còn góc khuyết chữ L và sân hở rộng hơn vẫn ở ngoài bao (khác biên bao lồi của `_rim_outlines`).

    Mỗi ô lấy vòng ngoài (tính cả lỗ) trừ các phòng có sẵn; còn < 50 % thì bỏ (vòng ôm các phòng có sẵn là bao cả
    căn), không thì giữ mảnh lớn nhất. Mảnh thành phòng khi ≥ `_ENVELOPE_WALLED` cạnh hộp bao sát đường khép
    (`_walled_sides`: chặn chẻ thừa lô gia), chứa tâm nhãn chữ hay rộng ≥ `_ENVELOPE_MIN_M2`, và không ôm quanh các
    phòng có sẵn (`_ENVELOPE_WRAP`): vành giữa căn và mép bàn/khung ảnh dò thành tường bao lấy cả căn, không phải
    phòng (bench-3d photo-tilted-ch05). Cờ lô gia: không nhãn, trong `_RIM_M2`, nông
    (`_depth_mm` ≤ `_LOGGIA_DEPTH_MM`), cạnh dài ≤ 2·`_LOGGIA_DEPTH_MM` hoặc ≤ hai lần biên hở (xa đường khép): hành
    lang dài hở một đầu không thành lô gia, lô gia hẹp hở đầu ngắn vẫn là lô gia. Phòng, đường, nhãn tra `STRtree`
    (K18).
    """
    if not lines:
        return []
    grown = shapely.buffer(shapely.union_all(list(bare)), _ENVELOPE_CLOSE_MM, cap_style="square", join_style="mitre")
    filled = shapely.union_all([shapely.Polygon(part.exterior) for part in getattr(grown, "geoms", [grown])])
    footprint = shapely.buffer(filled, -_ENVELOPE_CLOSE_MM, join_style="mitre")
    rings = [part.exterior for part in getattr(footprint, "geoms", [footprint]) if isinstance(part, shapely.Polygon)]
    # Lưới 1 mm: đường bao trùng tim tường mặt ngoài phải nút chung, không để dải mảnh nối phòng hở với vòng bao.
    merged = shapely.set_precision(shapely.unary_union([*lines, *rings]), 1.0)
    faces = shapely.polygonize(list(getattr(merged, "geoms", [merged])))
    line_tree = shapely.STRtree(list(lines))
    taken = [shapely.Polygon([(p.x, p.y) for p in o]) for o in rooms if len(o) >= 3]
    room_tree = shapely.STRtree(taken)
    seeds = shapely.STRtree([shapely.Point(c.x, c.y) for label, c in zip(labels, centres, strict=True) if label])
    found: list[tuple[list[Point], bool]] = []
    for hollow in faces.geoms:
        shell = shapely.Polygon(hollow.exterior)
        near = [taken[int(i)] for i in room_tree.query(shell, predicate="intersects")]
        free = shell.difference(shapely.union_all(near)) if near else shell
        parts = [part for part in getattr(free, "geoms", [free]) if isinstance(part, shapely.Polygon)]
        if free.area <= 0.5 * shell.area or not parts:
            continue
        face = max(parts, key=lambda part: part.area)
        labelled = bool(seeds.query(face, predicate="contains").size)
        area_m2 = face.area / 1e6
        if not labelled and area_m2 < _ENVELOPE_MIN_M2:
            continue
        hull = shapely.convex_hull(face)
        wrapped = sum(hull.intersection(taken[int(i)]).area for i in room_tree.query(hull, predicate="intersects"))
        if wrapped > _ENVELOPE_WRAP * face.area:
            continue
        near_walls = _near_walls(face, lines, line_tree)
        if _walled_sides(face, near_walls) < _ENVELOPE_WALLED:
            continue
        outline = _outline_points(shapely.Polygon(face.exterior))
        depth = _depth_mm(outline)
        loggia = (
            not labelled
            and _RIM_M2[0] <= area_m2 <= _RIM_M2[1]
            and depth <= _LOGGIA_DEPTH_MM
            and face.area / depth <= max(2 * _LOGGIA_DEPTH_MM, 2 * face.exterior.difference(near_walls).length)
        )
        found.append((outline, loggia))
    return found


def _wall_id_lists(walls: Sequence[Wall], outlines: Sequence[Sequence[Point]]) -> list[tuple[str, ...]]:
    """`wallIds` của mỗi `outline`: tường có trung điểm cách biên ≤ `ROOM_SNAP_MM`, thứ tự `walls`.

    Một `STRtree` trên trung điểm tường, tra theo lô bằng biên các phòng (K18: không O(n²)).
    """
    if not walls or not outlines:
        return [() for _ in outlines]
    midpoints = [
        shapely.Point(
            (wall.centreline.start.x + wall.centreline.end.x) / 2,
            (wall.centreline.start.y + wall.centreline.end.y) / 2,
        )
        for wall in walls
    ]
    tree = shapely.STRtree(midpoints)
    boundaries = [shapely.LinearRing([(p.x, p.y) for p in outline]) for outline in outlines]
    room_idx, wall_idx = tree.query(boundaries, predicate="dwithin", distance=ROOM_SNAP_MM)
    buckets: list[list[int]] = [[] for _ in outlines]
    for room, wall in zip(room_idx, wall_idx, strict=True):
        buckets[room].append(wall)
    return [tuple(walls[i].id for i in sorted(bucket)) for bucket in buckets]


def _text_centres(texts: Sequence[TextPx], scaling: Scaling) -> list[Point]:
    """Tâm hộp chữ đổi sang mm (`scaling.point`), cùng thứ tự `texts`."""
    return [scaling.point((t.box.x_min + t.box.x_max) / 2, (t.box.y_min + t.box.y_max) / 2) for t in texts]


def _room_labels(
    outlines: Sequence[Sequence[Point]],
    texts: Sequence[TextPx],
    parsed: Sequence[RoomLabel | None],
    centres: Sequence[Point],
) -> list[RoomLabel | None]:
    """Nhãn phòng của mỗi `outline` từ chữ trong biên có `match_room_label`.

    Nhiều nhãn trong một phòng (không gian mở "khách + bếp + sảnh", phòng ngủ có WC riêng) → công năng chính theo
    `_USAGE_PRIORITY`, rồi `confidence` cao nhất, hoà thì chữ đứng trước.
    """
    tree = shapely.STRtree([shapely.Polygon([(p.x, p.y) for p in outline]) for outline in outlines])
    best: list[tuple[tuple[int, float], RoomLabel] | None] = [None for _ in outlines]
    for text, label, centre in zip(texts, parsed, centres, strict=True):
        if label is None:
            continue
        key = (_USAGE_PRIORITY.index(label.usage), text.confidence)
        for room in tree.query(shapely.Point(centre.x, centre.y), predicate="within"):
            current = best[int(room)]
            if current is None or key > current[0]:
                best[int(room)] = (key, label)
    return [None if item is None else item[1] for item in best]


def _facade_lengths(lines: Sequence[shapely.LineString], outlines: Sequence[Sequence[Point]]) -> list[float]:
    """Độ dài (mm) biên mỗi `outline` nằm trên mặt ngoài nhà (`_FACADE_MM`)."""
    if not outlines:
        return []
    hull = shapely.convex_hull(shapely.MultiLineString(list(lines)))
    rim = shapely.boundary(hull).buffer(2 * ROOM_SNAP_MM)
    return [float(shapely.LinearRing([(p.x, p.y) for p in o]).intersection(rim).length) for o in outlines]


def _exposed_lengths(outlines: Sequence[Sequence[Point]]) -> list[float]:
    """Độ dài (mm) biên mỗi `outline` không giáp phòng khác (xa biên phòng khác > 2·`ROOM_SNAP_MM`).

    Phòng kề tra bằng `STRtree` (K18: không O(n²)).
    """
    polygons = [shapely.Polygon([(p.x, p.y) for p in o]) for o in outlines]
    tree = shapely.STRtree(polygons)
    exposed: list[float] = []
    for i, polygon in enumerate(polygons):
        near = [polygons[int(j)] for j in tree.query(polygon, predicate="dwithin", distance=2 * ROOM_SNAP_MM) if j != i]
        ring = polygon.exterior
        free = ring.difference(shapely.union_all(near).buffer(2 * ROOM_SNAP_MM)) if near else ring
        exposed.append(float(free.length))
    return exposed


def _depth_mm(outline: Sequence[Point]) -> float:
    """Cạnh ngắn (mm) hộp bao xoay nhỏ nhất của `outline`."""
    corners = shapely.get_coordinates(shapely.minimum_rotated_rectangle(shapely.Polygon([(p.x, p.y) for p in outline])))
    return float(min(math.dist(corners[0], corners[1]), math.dist(corners[1], corners[2])))


def _roomy(outline: Sequence[Point]) -> bool:
    """`outline` chứa được hình tròn đường kính `_CORRIDOR_DEPTH_MM` (bề rộng thật, không phải hộp bao: hành lang chữ L
    có hộp bao sâu mà chỗ nào cũng hẹp)."""
    return not shapely.Polygon([(p.x, p.y) for p in outline]).buffer(-_CORRIDOR_DEPTH_MM / 2).is_empty


def _open_space_labels(
    labels: Sequence[RoomLabel | None],
    outlines: Sequence[Sequence[Point]],
    areas_m2: Sequence[float],
    *,
    read_level: bool,
) -> list[RoomLabel | None]:
    """Phòng khách cho tầng chưa có phòng khách (`_OPEN_SPACE_M2`).

    "Bếp" rộng, "hành lang" rộng và không hẹp (`_roomy`) → phòng khách; không có thì phòng không tên lớn nhất, không
    hẹp, khi tầng đã đọc được (`read_level`: nhãn chữ hay tên suy từ đồ đạc; lô gia rìa, hộp kỹ thuật chỉ suy từ hình
    học nên không tính).
    """
    named = list(labels)
    if any(label is not None and label.usage == "livingRoom" for label in named):
        return named
    living = RoomLabel("livingRoom", ROOM_USAGE_NAMES["livingRoom"])
    wide = [i for i, area in enumerate(areas_m2) if area > _OPEN_SPACE_M2]
    opened = [
        i
        for i in wide
        if (label := named[i]) is not None
        and (label.usage == "kitchen" or (label.usage == "corridor" and _roomy(outlines[i])))
    ]
    unnamed = [i for i in wide if named[i] is None and _roomy(outlines[i])]
    if not opened and unnamed and read_level:
        opened = [max(unnamed, key=lambda i: areas_m2[i])]
    for i in opened:
        named[i] = living
    return named


def _door_flags(outlines: Sequence[Sequence[Point]], detections: Sequence[DetectionPx], scaling: Scaling) -> list[bool]:
    """Mỗi `outline` có hộp cửa đi (`_DOOR_LABELS`) chạm biên nới `ROOM_SNAP_MM` không."""
    corners = [
        (scaling.point(d.box.x_min, d.box.y_min), scaling.point(d.box.x_max, d.box.y_max))
        for d in detections
        if d.label in _DOOR_LABELS
    ]
    boxes = [shapely.box(low.x, low.y, high.x, high.y) for low, high in corners]
    tree = shapely.STRtree(boxes)
    rings = [shapely.LinearRing([(p.x, p.y) for p in o]).buffer(ROOM_SNAP_MM) for o in outlines]
    return [bool(tree.query(ring, predicate="intersects").size) for ring in rings]


def _fixtures_in(
    outlines: Sequence[Sequence[Point]], detections: Sequence[DetectionPx], scaling: Scaling
) -> list[set[str]]:
    """Nhãn đồ đạc có tâm trong mỗi `outline`; tủ bếp dài ≥ `_KITCHEN_RUN_MM` → `kitchen_run`, tủ áo ngắn hơn
    `_WARDROBE_MIN_MM` → `wardrobe_short`."""
    found_in: list[set[str]] = [set() for _ in outlines]
    polygons = [shapely.Polygon([(p.x, p.y) for p in outline]) for outline in outlines]
    tree = shapely.STRtree(polygons)
    for d in detections:
        centre = scaling.point((d.box.x_min + d.box.x_max) / 2, (d.box.y_min + d.box.y_max) / 2)
        label: str = d.label
        if label == "kitchen_cabinet":
            long_side = scaling.mm(max(d.box.x_max - d.box.x_min, d.box.y_max - d.box.y_min))
            label = "kitchen_run" if long_side >= _KITCHEN_RUN_MM else label
        elif label == "wardrobe":
            long_side = scaling.mm(max(d.box.x_max - d.box.x_min, d.box.y_max - d.box.y_min))
            label = label if long_side >= _WARDROBE_MIN_MM else "wardrobe_short"
        for room in tree.query(shapely.Point(centre.x, centre.y), predicate="within"):
            found_in[int(room)].add(label)
    return found_in


def _fixture_labels(
    found_in: Sequence[set[str]], areas_m2: Sequence[float], facades_mm: Sequence[float]
) -> list[RoomLabel | None]:
    """Công năng suy từ đồ đạc trong phòng (`_fixtures_in`), cho phòng không có nhãn chữ (bản vẽ không ghi tên, chữ
    "WC" nhỏ OCR bỏ sót), theo thứ tự: giường và `_BEDROOM_MIN_M2`-`_BEDROOM_MAX_M2` → phòng ngủ; dãy tủ bếp dài
    ≥ `_KITCHEN_RUN_MM` → bếp; máy giặt, không buồng tắm đứng, ≤ `_BATHROOM_MAX_M2` và ≥ `_FACADE_MM` mặt ngoài hay
    không kèm thiết bị vệ sinh → lô-gia; thiết bị vệ sinh/buồng tắm đứng và ≤ `_BATHROOM_MAX_M2` → phòng tắm; tủ
    bếp + bàn/ghế ăn và > `_BATHROOM_MAX_M2` → bếp; tủ áo cạnh dài ≥ `_WARDROBE_MIN_MM` (không kèm tủ bếp, máy giặt,
    thiết bị vệ sinh) và `_WARDROBE_BEDROOM_MIN_M2`-`_BEDROOM_MAX_M2` → phòng ngủ; không có gì → `None`.

    Tủ bếp ngắn không tính: model hay dò bàn lavabo phòng tắm thành `kitchen_cabinet` (bench căn hộ 27/10/2026).
    """
    labels: list[RoomLabel | None] = []
    for found, area_m2, facade_mm in zip(found_in, areas_m2, facades_mm, strict=True):
        cabinet = bool(found & {"kitchen_cabinet", "kitchen_run"})
        if "bed" in found and _BEDROOM_MIN_M2 <= area_m2 <= _BEDROOM_MAX_M2:
            usage: RoomUsage | None = "bedroom"
        elif "kitchen_run" in found:
            usage = "kitchen"
        elif (
            "washing_machine" in found
            and "shower" not in found
            and (facade_mm >= _FACADE_MM or "sanitary_fixture" not in found)
            and area_m2 <= _BATHROOM_MAX_M2
        ):
            usage = "loggia"
        elif found & {"sanitary_fixture", "shower"} and area_m2 <= _BATHROOM_MAX_M2:
            usage = "bathroom"
        elif cabinet and found & _DINING_LABELS and area_m2 > _BATHROOM_MAX_M2:
            usage = "kitchen"
        elif (
            "wardrobe" in found
            and not cabinet
            and not found & _WET_LABELS
            and _WARDROBE_BEDROOM_MIN_M2 <= area_m2 <= _BEDROOM_MAX_M2
        ):
            usage = "bedroom"
        else:
            usage = None
        labels.append(None if usage is None else RoomLabel(usage, ROOM_USAGE_NAMES[usage]))
    return labels


_NAME_TRUST = {"text": 1.0, "inferred": 0.6, "none": 0.4}
"""B12: tên từ nhãn chữ 1,0; suy từ đồ đạc / lô gia rìa 0,6; không tên 0,4."""
_MIN_WALLED_FACTOR = 0.5
_UNTRUSTED_SCALE_FACTOR = 0.7


def room_confidence(source: str, gap_share: float, *, scale_trusted: bool) -> float:
    """Tin cậy phòng (B12) = tích nguồn tên, max(0,5; 1 - `gap_share`), 1 hay 0,7 theo tỉ lệ, làm tròn 2 số."""
    factor = max(_MIN_WALLED_FACTOR, 1.0 - gap_share)
    return round(_NAME_TRUST[source] * factor * (1.0 if scale_trusted else _UNTRUSTED_SCALE_FACTOR), 2)


def _wall_bodies(walls: Sequence[Wall]) -> np.ndarray:
    """Thân mỗi tường: tim nới nửa bề dày + `ROOM_SNAP_MM` (cạnh phòng trong thân là tường thật, ngoài: khe đã nối).

    Một lượt GEOS cho cả mảng; `quad_segs=16` là mặc định của `LineString.buffer`.
    """
    ends = np.array(
        [[(w.centreline.start.x, w.centreline.start.y), (w.centreline.end.x, w.centreline.end.y)] for w in walls],
        dtype=float,
    ).reshape(-1, 2, 2)
    return shapely.buffer(
        shapely.linestrings(ends), np.array([w.thickness_mm / 2 + ROOM_SNAP_MM for w in walls]), quad_segs=16
    )


_FRAGMENT_M2 = 3.5
_FRAGMENT_OPEN_MM = 300.0
_SLIVER_WIDTH_MM = 400.0
"""Mảnh vụn (QT-ROOMS3): phòng < 3,5 m² không chứa nhãn chữ tên phòng, gộp vào phòng kề khi chung với nó ≥ 300 mm
cạnh không có tường (vách ảo của đoạn nối khe), hoặc khi là dải hẹp (bề rộng 2·diện tích/chu vi < 400 mm) thì gộp
vào phòng kề có cạnh chung dài nhất."""


def _merge_fragments(
    kept: Sequence[tuple[list[Point], float]],
    bodies: np.ndarray,
    doors: Sequence[shapely.LineString],
    long_closers: Sequence[shapely.LineString],
    labels: Sequence[Point],
) -> list[tuple[list[Point], float]]:
    """Gộp phòng không nhãn chữ vào phòng kề qua vách ảo, từ phòng nhỏ nhất (QT-ROOMS3).

    Phòng có nhãn chữ (WC, kho, hộp kỹ thuật ghi tên) giữ nguyên dù nhỏ. Phòng không nhãn gộp vào phòng kề khi:
    chung ≥ `_FRAGMENT_OPEN_MM` đoạn nối khe dài (`long_closers`, > `ROOM_GAP_CLOSE_MM`: khép để kín vùng hở, không để
    chia phòng mở — chia theo nhãn là việc của `_split_by_labels`), mọi cỡ; hoặc nhỏ hơn `_FRAGMENT_M2` và chung
    ≥ `_FRAGMENT_OPEN_MM` cạnh ngoài thân tường (`_wall_bodies`) và ngoài `doors` (khe ô mở: ở lớp là tường mang
    cửa); hoặc nhỏ và là dải hẹp (`_SLIVER_WIDTH_MM`) → phòng kề có cạnh chung dài nhất. Đích là phòng kề có cạnh
    thoả dài nhất. Phòng nhỏ không nhãn kín tường (lô gia, WC không ghi tên) giữ nguyên. Hợp không thành một đa giác
    đặc thì bỏ qua. Phòng kề tra bằng `STRtree` trên đa giác gốc; nhãn và thân tường quanh phòng cũng tra `STRtree`
    (K18: không O(n²), không hợp cả nghìn thân tường một lượt).
    """
    originals = [shapely.Polygon([(p.x, p.y) for p in o]) for o, _ in kept]
    tree = shapely.STRtree(originals)
    alive = dict(enumerate(originals))
    bodies = np.array([*bodies, *(door.buffer(ROOM_SNAP_MM) for door in doors)], dtype=object)
    body_tree = shapely.STRtree(bodies)
    weak = shapely.union_all([line.buffer(1.0) for line in long_closers])
    shapely.prepare(weak)
    points = shapely.STRtree([shapely.Point(p.x, p.y) for p in labels])
    owner = list(range(len(kept)))

    def find(i: int) -> int:
        while owner[i] != i:
            i = owner[i]
        return i

    for i in sorted(range(len(kept)), key=lambda k: kept[k][1]):
        polygon = alive[i]
        small = polygon.area / 1e6 < _FRAGMENT_M2
        sliver = small and 2 * polygon.area / polygon.length < _SLIVER_WIDTH_MM
        if points.query(polygon, predicate="contains").size or not (small or polygon.intersects(weak)):
            continue
        best: tuple[float, int] | None = None
        near: shapely.Geometry | None = None
        for j in {find(int(k)) for k in tree.query(polygon, predicate="intersects")} - {i}:
            shared = polygon.exterior.intersection(alive[j].exterior)
            score = shared.intersection(weak).length
            if score < _FRAGMENT_OPEN_MM and small and sliver:
                score = shared.length
            elif score < _FRAGMENT_OPEN_MM and small:
                if near is None:
                    near = shapely.union_all(bodies[body_tree.query(polygon, predicate="intersects")])
                score = shared.difference(near).length
            if score >= (1.0 if sliver else _FRAGMENT_OPEN_MM) and (best is None or score > best[0]):
                best = (score, j)
        if best is None:
            continue
        union = shapely.union_all([polygon, alive[best[1]]])
        if not isinstance(union, shapely.Polygon) or union.interiors:
            continue
        alive[best[1]], owner[i] = union, best[1]
        del alive[i]
    return [
        (list(kept[i][0]), kept[i][1]) if polygon is originals[i] else _with_area(_outline_points(polygon))
        for i, polygon in alive.items()
    ]


def _with_area(outline: list[Point]) -> tuple[list[Point], float]:
    """`(outline, diện tích m²)` cho phòng vừa gộp."""
    return outline, float(polygon_area_m2(outline))


def _walled_shares(bodies: np.ndarray, outlines: Sequence[Sequence[Point]]) -> list[float]:
    """Phần chu vi mỗi `outline` nằm sát tường (≤ nửa bề dày + `ROOM_SNAP_MM` quanh tim); phần còn lại là khe đã nối.

    Thân tường tra bằng `STRtree` theo từng phòng (K18: không O(n²)).
    """
    tree = shapely.STRtree(bodies)
    shares: list[float] = []
    for outline in outlines:
        ring = shapely.LinearRing([(p.x, p.y) for p in outline]) if len(outline) >= 3 else None
        if ring is None or ring.length == 0:
            shares.append(0.0)
            continue
        near = bodies[tree.query(ring, predicate="intersects")]
        covered = ring.intersection(shapely.union_all(near)).length if near.size else 0.0
        shares.append(min(1.0, covered / ring.length))
    return shares


def build_rooms(
    walls: Sequence[Wall],
    bridges: Sequence[tuple[Point, Point]],
    texts: Sequence[TextPx],
    *,
    detections: Sequence[DetectionPx] = (),
    level_id: str,
    scaling: Scaling,
    clock: Clock,
    dropped: Counter[str],
    scale_trusted: bool | None = None,
    closers_out: list[RoomCloser] | None = None,
) -> tuple[Room, ...]:
    """Phòng từ khép kín của tường + `bridges` + đoạn nối khe `_gap_closers` (B5-05 [6] bước 5, lệch BUG-IT-008).

    Thêm phòng mọc từ nhãn, ô của đường bao căn (`_envelope_outlines`: vòng hở ở mặt ngoài), lô gia rìa.
    Tên: nhãn chữ trong phòng, không có thì lô gia rìa, suy từ đồ đạc (`_fixture_labels`), lô gia nông của đường bao,
    lô gia mặt ngoài (`_FACADE_MM`), hộp kỹ thuật (`_SHAFT_M2`); cuối cùng phòng khách cho không gian mở
    (`_open_space_labels`).
    Mảnh dưới `MIN_ROOM_AREA_M2` → `roomTooSmall`. Cạnh phòng khép bằng
    đoạn nối khe không có tường thật, nên luật FE `ROOM-NOT-CLOSED` vẫn gắn cờ nó — đúng, vì tường ở đó thật sự thiếu.

    Tin cậy (B12): tích nguồn tên (`_NAME_TRUST`), 1 - phần chu vi không sát tường (kẹp ≥ `_MIN_WALLED_FACTOR`),
    (1 nếu tỉ lệ đáng tin, `_UNTRUSTED_SCALE_FACTOR` nếu không). `scale_trusted=None` → tin khi `scaling.build ==
    scaling.final` (tỉ lệ đoán `project_default` dựng ở tỉ lệ khác).

    `closers_out` (nếu có) nhận các đoạn khép không có tường cho `geometry.close_envelope_gaps` dựng tường vỏ (C5):
    `_door_closers` kèm nhãn hộp trước (khe có hộp mang ô mở, đoạn góc trùng khe sau đó bị bỏ vì chồng), rồi
    `_gap_closers`; phòng dựng ra không đổi.
    """
    parsed = [match_room_label(text.text) for text in texts]
    centres = _text_centres(texts, scaling)
    closers = _gap_closers(walls, bridges)
    labelled = _door_closers(walls, detections, scaling)
    doors = [line for line, _ in labelled]
    if closers_out is not None:
        closers_out.extend(_room_closer(line, label) for line, label in labelled)
        closers_out.extend(_room_closer(line, None) for line in closers)
    lines = [*_room_lines(walls, bridges), *closers, *doors]
    closed = _room_outlines(lines)
    seeded = _seeded_outlines(lines, closed, parsed, centres)
    bare = [*(_extend(wall, 0.0) for wall in walls), *lines[len(walls) :]]
    envelope = _envelope_outlines(lines, bare, [*closed, *seeded], parsed, centres)
    opened = [outline for outline, _ in envelope]
    rims = _rim_outlines(lines, [*closed, *seeded, *opened])
    rim_keys = {tuple(outline) for outline in rims}
    porch_keys = {tuple(outline) for outline, loggia in envelope if loggia}
    kept: list[tuple[list[Point], float]] = []
    for outline in _split_by_labels([*closed, *seeded, *opened, *rims], walls, parsed, centres):
        area_m2 = float(polygon_area_m2(outline)) if len(outline) >= 3 else 0.0
        if len(outline) < 3 or area_m2 < MIN_ROOM_AREA_M2:
            dropped["roomTooSmall"] += 1
            continue
        kept.append((outline, area_m2))
    bodies = _wall_bodies(walls)
    kept = _merge_fragments(
        kept,
        bodies,
        doors,
        [line for line in closers if line.length > ROOM_GAP_CLOSE_MM + 2 * _CLOSER_TRIM_MM],
        [centre for label, centre in zip(parsed, centres, strict=True) if label is not None],
    )
    kept.sort(key=lambda item: (min(p.y for p in item[0]), min(p.x for p in item[0])))
    outlines = [outline for outline, _ in kept]
    wall_ids = _wall_id_lists(walls, outlines)
    from_text = _room_labels(outlines, texts, parsed, centres)
    areas = [area for _, area in kept]
    found_in = _fixtures_in(outlines, detections, scaling)
    facades = _facade_lengths(lines, outlines)
    from_fixtures = _fixture_labels(found_in, areas, facades)
    loggia = RoomLabel("loggia", ROOM_USAGE_NAMES["loggia"])
    from_rim = [loggia if tuple(outline) in rim_keys else None for outline in outlines]
    from_porch = [loggia if tuple(outline) in porch_keys else None for outline in outlines]
    labelled_level = any(from_text)
    read_level = labelled_level or any(from_fixtures)
    from_facade = [
        loggia
        if _FACADE_LOGGIA_M2[0] <= area_m2 <= _FACADE_LOGGIA_M2[1]
        and not found & _NOT_LOGGIA
        and (
            (labelled_level and facade_mm >= _FACADE_MM)
            or (read_level and max(facade_mm, exposed_mm) >= _FACADE_MM and _depth_mm(outline) <= _LOGGIA_DEPTH_MM)
        )
        else None
        for outline, area_m2, facade_mm, exposed_mm, found in zip(
            outlines, areas, facades, _exposed_lengths(outlines), found_in, strict=True
        )
    ]
    shaft = RoomLabel("utility", "hộp kỹ thuật")
    doored = _door_flags(outlines, detections, scaling)
    from_shaft = [
        shaft if area_m2 < _SHAFT_M2 and not door else None for area_m2, door in zip(areas, doored, strict=True)
    ]
    guesses = [
        rim or fix or porch or facade or box
        for rim, fix, porch, facade, box in zip(
            from_rim, from_fixtures, from_porch, from_facade, from_shaft, strict=True
        )
    ]
    merged = _open_space_labels(
        [text or guess for text, guess in zip(from_text, guesses, strict=True)], outlines, areas, read_level=read_level
    )
    labels = name_rooms(merged)
    # Tên đổi khác nhãn chữ (bếp/sảnh rộng → phòng khách) là suy đoán, không mang tin cậy của chữ trên bản vẽ (B12).
    sources = [
        "text" if text is not None and text == label else "inferred" if label else "none"
        for text, label in zip(from_text, merged, strict=True)
    ]
    trusted = scaling.build == scaling.final if scale_trusted is None else scale_trusted
    walled = _walled_shares(bodies, outlines)
    rooms = []
    for (outline, area_m2), ids, label, source, share in zip(kept, wall_ids, labels, sources, walled, strict=True):
        confidence = room_confidence(source, 1.0 - share, scale_trusted=trusted) if ids else LOW_CONFIDENCE_CAP
        rooms.append(
            Room(
                id=new_spatial_id("room", clock),
                level_id=level_id,
                name=label.name,
                usage=label.usage,
                outline=tuple(outline),
                area_m2=area_m2,
                wall_ids=ids,
                confidence=confidence,
                source="ai",
                reviewed=False,
            )
        )
    return tuple(rooms)


def _room_of_box(
    tree: shapely.STRtree, polygons: Sequence[shapely.Polygon], box: shapely.Polygon
) -> tuple[int | None, float]:
    """Chỉ số phòng giao hộp đồ nhiều nhất (bằng nhau: phòng đứng trước) và tỉ lệ diện tích giao / hộp."""
    best: int | None = None
    best_area = 0.0
    for index in sorted(int(i) for i in tree.query(box)):
        area = polygons[index].intersection(box).area
        if area > best_area:
            best, best_area = index, area
    return best, best_area / box.area


def _xy(point: Point) -> tuple[float, float]:
    """Toạ độ `(x, y)` của điểm, cho `shapely.box`."""
    return point.x, point.y


def build_furniture(
    detections: Sequence[DetectionPx],
    rooms: Sequence[Room],
    *,
    level_id: str,
    scaling: Scaling,
    clock: Clock,
    dropped: Counter[str],
    scale_trusted: bool = True,
) -> tuple[Furniture, ...]:
    """Đồ đạc từ phát hiện (B5-05 [6] bước 6); ô mở bỏ qua không đếm, nhãn lạ → `unknownLabel`.

    Nhãn `chair`/`other` được sửa theo kích thước mm ở tỉ lệ `final` (`relabel_by_size`, U34) chỉ khi tỉ lệ đã tin
    (`scale_trusted`): tỉ lệ đoán sai thì cỡ sai, đổi loại theo cỡ thành đoán bừa (B10).
    Phòng của đồ: phòng giao hộp nhiều nhất (B8). Giao mọi phòng < `_OUTSIDE_SHARE` hộp và tâm ngoài hợp phòng nới
    `_OUTSIDE_REACH_MM` → `suggested=True` (đồ ngoài căn: sơ đồ vị trí, ảnh minh hoạ), không xoá.
    """
    polygons = [shapely.Polygon([(p.x, p.y) for p in room.outline]) for room in rooms]
    tree = shapely.STRtree(polygons)
    # Hợp phòng nới `_OUTSIDE_REACH_MM`: dựng khi lần đầu có đồ giao phòng ít (hợp cả nghìn phòng tốn giây).
    reach: BaseGeometry | None = None
    tables = [
        shapely.box(*_xy(scaling.point(d.box.x_min, d.box.y_min)), *_xy(scaling.point(d.box.x_max, d.box.y_max)))
        for d in detections
        if (target := LABEL_TARGETS.get(d.label)) is not None and target.domain_kind == "table"
    ]
    items = []
    for detection in detections:
        if detection.label in _OPENING_LABELS:
            continue
        target = LABEL_TARGETS.get(detection.label)
        if target is None or target.category != "furniture":
            dropped["unknownLabel"] += 1
            continue
        box_min = scaling.point(detection.box.x_min, detection.box.y_min)
        box_max = scaling.point(detection.box.x_max, detection.box.y_max)
        if box_max.x - box_min.x == 0 or box_max.y - box_min.y == 0:
            dropped["furnitureEmpty"] += 1
            continue
        centre = Point(x=js_round((box_min.x + box_max.x) / 2), y=js_round((box_min.y + box_max.y) / 2))
        footprint = shapely.box(box_min.x, box_min.y, box_max.x, box_max.y)
        room, share = _room_of_box(tree, polygons, footprint)
        outside = bool(rooms) and share < _OUTSIDE_SHARE
        if outside:
            if reach is None:
                reach = shapely.union_all(polygons).buffer(_OUTSIDE_REACH_MM)
                shapely.prepare(reach)
            outside = not reach.contains(shapely.Point(centre.x, centre.y))
        box = detection.box
        kind, variant = target.domain_kind, None
        if scale_trusted:
            kind, variant = relabel_by_size(
                target.domain_kind,
                (box.x_max - box.x_min) * scaling.final,
                (box.y_max - box.y_min) * scaling.final,
                room_usage=None if room is None else rooms[room].usage,
                near_table=any(footprint.distance(table) <= _BENCH_TABLE_GAP_MM for table in tables),
            )
        items.append(
            Furniture(
                id=new_spatial_id("furniture", clock),
                level_id=level_id,
                room_id=None if room is None else rooms[room].id,
                kind=kind,
                variant=variant,
                centre=centre,
                bounding_box=BoundingBox(min=box_min, max=box_max),
                rotation_deg=0.0,
                confidence=detection.confidence,
                source="ai",
                reviewed=False,
                suggested=outside,
            )
        )
    return tuple(items)


def relabel_by_size(
    kind: str, width_mm: float, height_mm: float, *, room_usage: str | None = None, near_table: bool = False
) -> tuple[str, str | None]:
    """`(kind, variant)` sau khi xét kích thước thật (U34); không đổi thì `variant=None`.

    `chair`/`other` cỡ giường (ngắn 900-2000, dài 1900-2200) → `bed`; `chair` dài ≥ 1400, ngắn
    600-1600 (sofa góc) → `chair` + `variant="sofa"` (hợp đồng không có `kind` sofa; thư viện xếp sofa vào nhóm
    ghế); `chair` dài ≥ 1000, ngắn < 600, cách bàn ≤ 900 mm (`near_table`) → `variant="bench"`.
    Xét giường trước: món 1043 x 2075 mm khớp cả hai khung; không thành giường trong phòng
    `_NO_BED_USAGES`. Nhãn khác (bàn, tủ bếp…) giữ nguyên; YOLO báo `bed` giữ là giường ở mọi phòng (B10).
    """
    short, long = sorted((width_mm, height_mm))
    bed_sized = _BED_SHORT_MM[0] <= short <= _BED_SHORT_MM[1] and _BED_LONG_MM[0] <= long <= _BED_LONG_MM[1]
    if bed_sized and kind in ("chair", "other") and room_usage not in _NO_BED_USAGES:
        return "bed", "bed"
    if kind == "chair" and long >= _SOFA_LONG_MM and _SOFA_SHORT_MM[0] <= short <= _SOFA_SHORT_MM[1]:
        return "chair", "sofa"
    if kind == "chair" and near_table and long >= _BENCH_LONG_MM and short < _BENCH_SHORT_MM:
        return "chair", "bench"
    return kind, None
