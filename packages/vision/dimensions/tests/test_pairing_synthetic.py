"""Ghép kích thước trên tập kiểm cố định `EVAL_SET_SEEDS`: đáp án `texts`/`walls` của `render_plan`.

Hai lượt: tường liền (đáp án nguyên văn) và tường bị cắt tại mọi hộp `door` (dạng B5-02 sẽ trả).
Mỗi lượt in tỉ lệ seed đạt (`pytest -s` để thấy); dưới 90 % là lỗi của `pair_dimension_lines`.
"""

from collections.abc import Sequence
from functools import cache

from packages.domain.scale import infer_scale
from packages.ml_contracts.artifacts import BoxPx, PointPx, WallPx
from packages.ml_contracts.synthetic import EVAL_SET_SEEDS, SyntheticPlan, render_plan
from packages.vision.dimensions import pair_dimension_lines

PASS_RATE = 0.9
TOLERANCE = 0.02


@cache
def _plans() -> tuple[SyntheticPlan, ...]:
    """Bốn mươi trang của tập kiểm, dựng một lần cho cả hai lượt."""
    return tuple(render_plan(seed) for seed in EVAL_SET_SEEDS)


def _pieces(lo: float, hi: float, gaps: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    """Các đoạn còn lại của `[lo, hi]` sau khi bỏ `gaps`, bỏ đoạn ngắn hơn 1 px."""
    pieces, cursor = [], lo
    for start, end in sorted(gaps):
        if start > cursor:
            pieces.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < hi:
        pieces.append((cursor, hi))
    return [piece for piece in pieces if piece[1] - piece[0] >= 1]


def _cut_wall(wall: WallPx, doors: Sequence[BoxPx]) -> list[WallPx]:
    """Cắt một tường thẳng trục tại mọi cửa mà đường tim đi qua."""
    horizontal = abs(wall.end.x - wall.start.x) >= abs(wall.end.y - wall.start.y)
    lo, hi = sorted((wall.start.x, wall.end.x) if horizontal else (wall.start.y, wall.end.y))
    centre = wall.start.y if horizontal else wall.start.x
    gaps = []
    for door in doors:
        a0, a1, c0, c1 = (
            (door.x_min, door.x_max, door.y_min, door.y_max)
            if horizontal
            else (door.y_min, door.y_max, door.x_min, door.x_max)
        )
        if c0 <= centre <= c1 and a1 > lo and a0 < hi:
            gaps.append((max(a0, lo), min(a1, hi)))
    return [_along(horizontal, centre, a, b, wall.thickness_px) for a, b in _pieces(lo, hi, gaps)]


def _along(horizontal: bool, centre: float, a: float, b: float, thickness: float) -> WallPx:
    """Tường từ `a` tới `b` dọc trục, tim ở `centre` ngang trục."""
    if horizontal:
        start, end = PointPx(x=a, y=centre), PointPx(x=b, y=centre)
    else:
        start, end = PointPx(x=centre, y=a), PointPx(x=centre, y=b)
    return WallPx(start=start, end=end, thickness_px=thickness, confidence=1.0)


def _cut_at_doors(plan: SyntheticPlan) -> tuple[WallPx, ...]:
    """Đáp án tường đứt ở mọi hộp `door` đáp án."""
    doors = [d.box for d in plan.detections if d.label == "door"]
    return tuple(piece for wall in plan.walls for piece in _cut_wall(wall, doors))


def _pass_rate(cut: bool) -> float:
    """Tỉ lệ seed có `infer_scale` lệch ≤ 2 % so với `mm_per_px` đáp án."""
    ok = 0
    for plan in _plans():
        walls = _cut_at_doors(plan) if cut else plan.walls
        found = infer_scale(pair_dimension_lines(plan.texts, walls)).mm_per_px
        ok += found is not None and abs(found - plan.mm_per_px) <= TOLERANCE * plan.mm_per_px
    return ok / len(_plans())


def test_cut_helper_removes_a_door_gap() -> None:
    """Hàm cắt của test bỏ đúng khe cửa: tường 0-1000 với cửa 400-500 → hai đoạn."""
    wall = WallPx(start=PointPx(x=0, y=50), end=PointPx(x=1000, y=50), thickness_px=10, confidence=1)
    door = BoxPx(x_min=400, y_min=40, x_max=500, y_max=60)
    pieces = _cut_wall(wall, [door])
    assert [(p.start.x, p.end.x) for p in pieces] == [(0, 400), (500, 1000)]
    assert _cut_wall(wall, [BoxPx(x_min=400, y_min=80, x_max=500, y_max=90)]) == [wall]


def test_synthetic_plans_whole_walls() -> None:
    """Tường liền: ≥ 90 % seed có tỉ lệ lệch ≤ 2 %."""
    rate = _pass_rate(cut=False)
    print(f"ti le seed dat (tuong lien): {rate:.3f}")
    assert rate >= PASS_RATE


def test_synthetic_plans_walls_cut_at_doors() -> None:
    """Tường đứt ở cửa đi (như B5-02): vẫn ≥ 90 % seed lệch ≤ 2 %."""
    rate = _pass_rate(cut=True)
    print(f"ti le seed dat (tuong cat tai cua): {rate:.3f}")
    assert rate >= PASS_RATE
