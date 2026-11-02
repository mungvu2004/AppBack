"""Bổ sung đồ còn thiếu bằng hình học thuần (shapely, Pillow; không I/O).

AI chỉ nói "món gì, cạnh tường nào, vị trí dọc cạnh 0-1"; mã ở đây dựng danh sách cạnh tường của
từng phòng (nhãn `R*`/`R*:E*` trùng với sơ đồ gửi AI), rồi tự đặt món: trong phòng lùi 85 mm,
không đè đồ đã có hay món vừa đặt, không chắn vùng mở cửa, dò dọc cạnh bước 50 mm, hết chỗ thì
thử cạnh kề rồi các cạnh khác của phòng. Đơn vị mm, y xuống, `rotationDeg` 0 = mặt trước nhìn +y,
vectơ mặt trước (-sin θ, cos θ) — như `Furniture` của `packages/domain/spatial/model.py`.
"""

from __future__ import annotations

import io
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon, box

from packages.domain.spatial.model import Furniture, Opening, Room, Wall

__all__ = [
    "ADD",
    "DEFAULT_SIZES",
    "Edge",
    "RoomEdges",
    "edge_summary",
    "edges_of",
    "label_rooms",
    "load_font",
    "place_additions",
    "schematic",
]

ADD: Final[Mapping[str, tuple[str, str | None]]] = {
    "toilet": ("sanitaryFixture", "wc"),
    "basin": ("sanitaryFixture", "basin"),
    "shower": ("shower", "shower"),
    "kitchenCabinet": ("kitchenCabinet", "baseRun"),
    "stove": ("kitchenCabinet", "hob"),
    "fridge": ("other", "fridge"),
    "washer": ("washingMachine", None),
    "tvStand": ("other", "cabinet"),
    "wardrobe": ("wardrobe", "wardrobe"),
    "plant": ("other", "planter"),
    "desk": ("table", "table"),
    "bed": ("bed", "bed"),
    "nightstand": ("other", "nightstand"),
    "sofa": ("chair", "sofa"),
    "armchair": ("chair", "armchair"),
    "coffeeTable": ("table", "sideTable"),
    "diningTable": ("table", "table"),
    "bookshelf": ("other", "shelves"),
}
"""Loại món AI được thêm → (`kind`, `variant`) của `Furniture`. Khoá trùng `type` hồ sơ mẫu khi có."""

DEFAULT_SIZES: Final[Mapping[str, tuple[int, int]]] = {
    "toilet": (400, 650),
    "basin": (500, 450),
    "shower": (900, 900),
    "kitchenCabinet": (1800, 600),
    "stove": (700, 600),
    "fridge": (650, 700),
    "washer": (600, 600),
    "tvStand": (1600, 400),
    "wardrobe": (1200, 600),
    "plant": (400, 400),
    "desk": (1200, 600),
    "bed": (1600, 2000),
    "nightstand": (450, 400),
    "sofa": (2000, 900),
    "armchair": (800, 800),
    "coffeeTable": (1000, 550),
    "diningTable": (1400, 800),
    "bookshelf": (800, 350),
}
"""(rộng, sâu) mm khi thư viện không có mẫu cùng loại; FE tự chọn mẫu theo vai trò (`modelId=None`)."""

AWAY_MM: Final[Mapping[str, int]] = {"coffeeTable": 1150, "diningTable": 600}
"""Món đứng giữa phòng: khoảng lùi thêm khỏi cạnh AI chọn (bàn trà trước sofa dựa cùng cạnh; bàn ăn chừa ghế)."""

WALL_GAP: Final = 85
"""Nửa tường 75 + khe 10 mm: đường bao phòng là tim tường."""
STEP_MM: Final = 50
MIN_EDGE_MM: Final = 400
OVERLAP_MM2: Final = 1_000.0
"""Chồng lấn dưới 10 cm² coi như chạm mép (sai số làm tròn), không phải đè."""
DOOR_ON_EDGE_MM: Final = 250
SCHEMATIC_SIDE_PX: Final = 1100
_MARGIN_PX: Final = 40

Vec = tuple[float, float]


@dataclass(frozen=True, slots=True)
class Edge:
    """Một cạnh tường của phòng, hướng chuẩn `a → b` (trái→phải / trên→dưới), `n` = pháp tuyến hướng vào phòng."""

    id: str
    room_id: str
    level_id: str
    a: Vec
    b: Vec
    length: float
    dir: Vec
    n: Vec
    doors: tuple[tuple[str, float, float], ...]
    """(`door`|`window`, vị trí dọc cạnh mm, rộng mm)."""


@dataclass(frozen=True, slots=True)
class RoomEdges:
    """Phòng đã gắn nhãn `R<n>` cùng đa giác và các cạnh của nó."""

    label: str
    room: Room
    poly: Polygon
    edges: tuple[Edge, ...]


def label_rooms(rooms: Iterable[Room]) -> dict[str, str]:
    """Nhãn `R1, R2…` theo thứ tự (tầng, id) — tất định, duy nhất trên mọi tầng của dự án."""
    ordered = sorted(rooms, key=lambda r: (r.level_id, r.id))
    return {room.id: f"R{i + 1}" for i, room in enumerate(ordered)}


def _door_points(openings: Iterable[Opening], walls: Mapping[str, Wall]) -> list[tuple[str, Vec, float]]:
    """Tâm mỗi ô mở trên tim tường của nó; ô mở trỏ tường lạ bị bỏ."""
    out: list[tuple[str, Vec, float]] = []
    for o in openings:
        wall = walls.get(o.wall_id)
        if wall is None:
            continue
        s, e = wall.centreline.start, wall.centreline.end
        length = math.hypot(e.x - s.x, e.y - s.y) or 1.0
        t = (o.offset_mm + o.width_mm / 2) / length
        out.append((o.kind, (s.x + t * (e.x - s.x), s.y + t * (e.y - s.y)), float(o.width_mm)))
    return out


def edges_of(room: Room, label: str, openings: Iterable[Opening], walls: Iterable[Wall]) -> RoomEdges:
    """Cạnh ≥ 400 mm của phòng, pháp tuyến vào trong, cửa/cửa sổ nằm trên cạnh (lệch < 250 mm)."""
    pts = [(float(p.x), float(p.y)) for p in room.outline]
    poly = Polygon(pts)
    doors = _door_points(openings, {w.id: w for w in walls})
    edges: list[Edge] = []
    for i, start in enumerate(pts):
        a, b = sorted((start, pts[(i + 1) % len(pts)]))
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        if length < MIN_EDGE_MM:
            continue
        d = ((b[0] - a[0]) / length, (b[1] - a[1]) / length)
        n = (-d[1], d[0])
        probe = ShapelyPoint((a[0] + b[0]) / 2 + n[0] * 50, (a[1] + b[1]) / 2 + n[1] * 50)
        if not poly.contains(probe):
            n = (-n[0], -n[1])
        on_edge = []
        for kind, (px, py), width in doors:
            t = (px - a[0]) * d[0] + (py - a[1]) * d[1]
            off = abs((px - a[0]) * n[0] + (py - a[1]) * n[1])
            if -100 <= t <= length + 100 and off < DOOR_ON_EDGE_MM:
                on_edge.append((kind, t, width))
        edges.append(Edge(f"{label}:E{len(edges) + 1}", room.id, room.level_id, a, b, length, d, n, tuple(on_edge)))
    return RoomEdges(label, room, poly, tuple(edges))


def edge_summary(rooms: Sequence[RoomEdges]) -> list[dict[str, Any]]:
    """Danh sách cạnh cho prompt bổ sung đồ: id, phòng, công năng, dài, loại ô mở trên cạnh."""
    return [
        {
            "edge": e.id,
            "room": r.label,
            "usage": r.room.usage,
            "len": round(e.length),
            "doors": [kind for kind, _, _ in e.doors],
        }
        for r in rooms
        for e in r.edges
    ]


def _rect(c: Vec, d: Vec, n: Vec, width: float, depth: float) -> Polygon:
    """Chữ nhật tâm `c`, cạnh rộng dọc `d`, cạnh sâu dọc `n`."""
    hx, hy = d[0] * width / 2, d[1] * width / 2
    nx, ny = n[0] * depth / 2, n[1] * depth / 2
    return Polygon(
        [
            (c[0] - hx - nx, c[1] - hy - ny),
            (c[0] + hx - nx, c[1] + hy - ny),
            (c[0] + hx + nx, c[1] + hy + ny),
            (c[0] - hx + nx, c[1] - hy + ny),
        ]
    )


def _door_zones(room: RoomEdges) -> list[Polygon]:
    """Vùng cánh cửa quét vào phòng: vuông cạnh = rộng cửa (+100 mm dọc tường). Cửa sổ không chắn."""
    zones = []
    for e in room.edges:
        for kind, t, width in e.doors:
            if kind != "door":
                continue
            c = (e.a[0] + e.dir[0] * t + e.n[0] * width / 2, e.a[1] + e.dir[1] * t + e.n[1] * width / 2)
            zones.append(_rect(c, e.dir, e.n, width + 100, width))
    return zones


def _place_on(
    e: Edge, width: float, depth: float, pos: float, inner: Polygon, blocked: Sequence[Polygon], away: float = 0
) -> tuple[Vec, Polygon] | None:
    """Dò dọc cạnh từ vị trí mong muốn, bước 50 mm; chỗ hợp lệ gần nhất (hoà → `t` nhỏ hơn)."""
    want = pos * e.length
    lo, hi = math.ceil(width / 2), math.floor(e.length - width / 2)
    offset = WALL_GAP + 5 + away + depth / 2
    for t in sorted(range(lo, hi + 1, STEP_MM), key=lambda t: (abs(t - want), t)):
        c = (e.a[0] + e.dir[0] * t + e.n[0] * offset, e.a[1] + e.dir[1] * t + e.n[1] * offset)
        p = _rect(c, e.dir, e.n, width, depth)
        if inner.contains(p) and not any(p.intersection(q).area > OVERLAP_MM2 for q in blocked):
            return c, p
    return None


def _touches(g: Edge, e0: Edge) -> bool:
    """Hai cạnh chung một đầu mút (lệch < 300 mm)."""
    return min(math.dist(p, q) for p in (g.a, g.b) for q in (e0.a, e0.b)) < 300


def _furniture_poly(f: Furniture) -> Polygon:
    """Khung bao của món đã có (hộp thẳng trục `boundingBox`)."""
    bb = f.bounding_box
    return box(bb.min.x, bb.min.y, bb.max.x, bb.max.y)


def place_additions(
    rooms: Sequence[RoomEdges],
    existing_furniture: Iterable[Furniture],
    answers: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Đặt từng món AI đề xuất; món không có chỗ (hay cạnh/loại lạ) bị bỏ. Tất định theo thứ tự `answers`.

    Mỗi câu trả lời: `type` (khoá `ADD`), `edge` (`R*:E*`), `pos` 0-1, tuỳ chọn `widthMm`/`depthMm`
    (mẫu đã chọn; vắng → `DEFAULT_SIZES`) và `modelId`. Kết quả là phần tử `additions` của hợp đồng dây.
    """
    by_edge = {e.id: (r, e) for r in rooms for e in r.edges}
    taken_by_level: dict[str, list[Polygon]] = {}
    for f in existing_furniture:
        taken_by_level.setdefault(f.level_id, []).append(_furniture_poly(f))
    zones = {r.room.id: _door_zones(r) for r in rooms}
    placed: list[dict[str, Any]] = []
    for ans in answers:
        kind_variant = ADD.get(str(ans.get("type")))
        hit_edge = by_edge.get(str(ans.get("edge")))
        if kind_variant is None or hit_edge is None:
            continue
        room, e0 = hit_edge
        default_w, default_d = DEFAULT_SIZES[str(ans["type"])]
        width, depth = float(ans.get("widthMm") or default_w), float(ans.get("depthMm") or default_d)
        pos = min(1.0, max(0.0, float(ans.get("pos", 0.5))))
        taken = taken_by_level.setdefault(room.room.level_id, [])
        inner = room.poly.buffer(-WALL_GAP)
        others = [g for g in room.edges if g is not e0]
        tries = [e0, *sorted(others, key=lambda g: not _touches(g, e0))]
        for e in tries:
            if width > e.length - 100:
                continue
            away = AWAY_MM.get(str(ans["type"]), 0)
            hit = _place_on(e, width, depth, pos if e is e0 else 0.5, inner, taken + zones[room.room.id], away)
            if hit is None:
                continue
            centre, poly = hit
            taken.append(poly)
            placed.append(
                {
                    "levelId": room.room.level_id,
                    "roomId": room.room.id,
                    "kind": kind_variant[0],
                    "variant": kind_variant[1],
                    "centre": {"x": round(centre[0]), "y": round(centre[1])},
                    "widthMm": round(width),
                    "depthMm": round(depth),
                    "rotationDeg": round(math.degrees(math.atan2(-e.n[0], e.n[1]))) % 360,
                    "modelId": ans.get("modelId"),
                }
            )
            break
    return placed


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Phông có dấu tiếng Việt nếu máy có (DejaVu trong ảnh Debian), không thì phông mặc định của Pillow."""
    for name in ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def schematic(rooms: Sequence[RoomEdges], furniture: Iterable[Furniture]) -> bytes:
    """Sơ đồ PNG cùng hướng bản vẽ: phòng (nhãn xanh `R* usage`), cạnh (đỏ `E*`), cửa (chấm cam), đồ đã có (xám)."""
    xs = [x for r in rooms for x, _ in r.poly.exterior.coords]
    ys = [y for r in rooms for _, y in r.poly.exterior.coords]
    if not xs:
        xs, ys = [0.0, 1.0], [0.0, 1.0]
    x0, y0 = min(xs), min(ys)
    scale = SCHEMATIC_SIDE_PX / max(max(xs) - x0, max(ys) - y0, 1.0)

    def to_px(x: float, y: float) -> Vec:
        return ((x - x0) * scale + _MARGIN_PX, (y - y0) * scale + _MARGIN_PX)

    size = (int((max(xs) - x0) * scale) + 2 * _MARGIN_PX, int((max(ys) - y0) * scale) + 2 * _MARGIN_PX)
    im = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(im)
    font = load_font(15)
    for f in furniture:
        draw.polygon([to_px(x, y) for x, y in list(_furniture_poly(f).exterior.coords)[:4]], outline="gray")
    for r in rooms:
        draw.polygon([to_px(x, y) for x, y in list(r.poly.exterior.coords)[:-1]], outline="black", width=3)
        c = r.poly.representative_point()
        draw.text(to_px(c.x, c.y), f"{r.label} {r.room.usage}", font=font, fill="blue")
        for e in r.edges:
            mid = ((e.a[0] + e.b[0]) / 2 + e.n[0] * 180, (e.a[1] + e.b[1]) / 2 + e.n[1] * 180)
            draw.text(to_px(*mid), e.id.split(":")[1], font=font, fill="red")
            for _, t, _ in e.doors:
                px, py = to_px(e.a[0] + e.dir[0] * t, e.a[1] + e.dir[1] * t)
                draw.ellipse([px - 7, py - 7, px + 7, py + 7], fill="orange")
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()
