"""Hình học bổ sung đồ: cạnh/pháp tuyến, đặt trong phòng, không đè, tránh cửa, lùi sang cạnh khác."""

import io
import math
from typing import Any

from PIL import Image
from shapely.geometry import Polygon, box

from apps.worker.design_director.fill import (
    WALL_GAP,
    edge_summary,
    edges_of,
    label_rooms,
    place_additions,
    schematic,
)
from apps.worker.design_director.sheets import contact_sheet
from packages.domain.design_director.profiles import Profile
from packages.domain.spatial.model import BoundingBox, Furniture, Opening, Point, Room, Segment, Wall


def pt(x: float, y: float) -> Point:
    """Điểm mm."""
    return Point.model_construct(x=round(x), y=round(y))


def room(rid: str, w: float, h: float, *, level: str = "L1", usage: str = "bathroom") -> Room:
    """Phòng chữ nhật (0,0)-(w,h)."""
    kw: dict[str, Any] = {"id": rid, "level_id": level, "usage": usage, "wall_ids": ()}
    return Room.model_construct(outline=(pt(0, 0), pt(w, 0), pt(w, h), pt(0, h)), **kw)


def wall(wid: str, a: tuple[float, float], b: tuple[float, float]) -> Wall:
    """Tường theo tim."""
    kw: dict[str, Any] = {"id": wid, "level_id": "L1"}
    return Wall.model_construct(centreline=Segment.model_construct(start=pt(*a), end=pt(*b)), **kw)


def door(oid: str, wid: str, offset: float, width: float = 800, kind: str = "door") -> Opening:
    """Ô mở trên tường."""
    kw: dict[str, Any] = {"id": oid, "wall_id": wid, "kind": kind, "offset_mm": offset, "width_mm": width}
    return Opening.model_construct(**kw)


def furn(x0: float, y0: float, x1: float, y1: float, level: str = "L1") -> Furniture:
    """Đồ đã có, hộp thẳng trục."""
    kw: dict[str, Any] = {"id": "f1", "level_id": level}
    return Furniture.model_construct(bounding_box=BoundingBox.model_construct(min=pt(x0, y0), max=pt(x1, y1)), **kw)


def poly_of(a: dict[str, Any]) -> Polygon:
    """Đa giác món đã đặt theo tâm/rộng/sâu/xoay."""
    th = math.radians(a["rotationDeg"])
    n = (-math.sin(th), math.cos(th))
    d = (n[1], -n[0])
    c, w, dep = (a["centre"]["x"], a["centre"]["y"]), a["widthMm"], a["depthMm"]
    return Polygon(
        [
            (c[0] + sx * d[0] * w / 2 + sy * n[0] * dep / 2, c[1] + sx * d[1] * w / 2 + sy * n[1] * dep / 2)
            for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))
        ]
    )


def test_edges_inward_normals_and_door_on_edge() -> None:
    """Bốn cạnh, pháp tuyến hướng vào tâm, cửa nằm trên cạnh trên (y=0)."""
    r = room("r1", 3000, 2000)
    walls = [wall("w1", (0, 0), (3000, 0))]
    re = edges_of(r, "R1", [door("o1", "w1", 1000), door("o2", "wX", 0)], walls)
    assert [e.id for e in re.edges] == ["R1:E1", "R1:E2", "R1:E3", "R1:E4"]
    for e in re.edges:
        mid = ((e.a[0] + e.b[0]) / 2 + e.n[0] * 100, (e.a[1] + e.b[1]) / 2 + e.n[1] * 100)
        assert re.poly.contains(Polygon([(mid[0], mid[1]), (mid[0] + 1, mid[1]), (mid[0], mid[1] + 1)]))
    top = re.edges[0]
    assert top.n == (0.0, 1.0)
    assert top.doors == (("door", 1400.0, 800.0),)
    assert edge_summary([re])[0] == {"edge": "R1:E1", "room": "R1", "usage": "bathroom", "len": 3000, "doors": ["door"]}


def test_short_edges_skipped_and_labels_deterministic() -> None:
    """Cạnh < 400 mm bị bỏ; nhãn R theo (tầng, id)."""
    r = room("b", 3000, 300)
    assert [e.id for e in edges_of(r, "R2", [], []).edges] == ["R2:E1", "R2:E2"]
    assert label_rooms([room("b", 1, 1, level="L2"), room("a", 1, 1, level="L2"), room("z", 1, 1)]) == {
        "z": "R1",
        "a": "R2",
        "b": "R3",
    }


def test_place_inside_no_overlap_facing_room() -> None:
    """Hai món cùng cạnh: cả hai trong phòng lùi 85 mm, không đè nhau, mặt trước nhìn vào phòng."""
    re = edges_of(room("r1", 3000, 2000), "R1", [], [])
    answers = [{"type": "toilet", "edge": "R1:E1", "pos": 0.5}, {"type": "toilet", "edge": "R1:E1", "pos": 0.5}]
    placed = place_additions([re], [], answers)
    assert len(placed) == 2
    inner = re.poly.buffer(-WALL_GAP)
    p0, p1 = poly_of(placed[0]), poly_of(placed[1])
    assert inner.contains(p0)
    assert inner.contains(p1)
    assert p0.intersection(p1).area < 1_000
    assert placed[0]["rotationDeg"] == 0  # cạnh trên, pháp tuyến +y
    assert placed[0] == {
        "levelId": "L1",
        "roomId": "r1",
        "kind": "sanitaryFixture",
        "variant": "wc",
        "centre": {"x": 1500, "y": 415},
        "widthMm": 400,
        "depthMm": 650,
        "rotationDeg": 0,
        "modelId": None,
    }
    assert place_additions([re], [], answers) == placed  # tất định


def test_door_zone_avoided() -> None:
    """Cửa giữa cạnh trên: món không nằm trong vùng cánh cửa quét."""
    walls = [wall("w1", (0, 0), (3000, 0))]
    re = edges_of(room("r1", 3000, 2000), "R1", [door("o1", "w1", 1100)], walls)
    placed = place_additions([re], [], [{"type": "basin", "edge": "R1:E1", "pos": 0.5}])
    assert len(placed) == 1
    assert poly_of(placed[0]).intersection(box(1050, 0, 1950, 800)).area < 1_000


def test_existing_furniture_and_fallback_edge() -> None:
    """Cạnh chọn bị đồ chiếm hết → món sang cạnh kề; kích thước + modelId lấy từ câu trả lời."""
    re = edges_of(room("r1", 3000, 2000), "R1", [], [])
    blocker = furn(0, 0, 3000, 900)
    ans = {"type": "wardrobe", "edge": "R1:E1", "pos": 0.0, "widthMm": 1000, "depthMm": 550, "modelId": "itm_w"}
    placed = place_additions([re], [blocker], [ans])
    assert len(placed) == 1
    assert placed[0]["modelId"] == "itm_w"
    assert placed[0]["rotationDeg"] in (90, 270)
    assert poly_of(placed[0]).intersection(box(0, 0, 3000, 900)).area < 1_000
    # đồ ở tầng khác không chắn
    other = place_additions([re], [furn(0, 0, 3000, 900, level="L2")], [ans])
    assert other[0]["rotationDeg"] == 0


def test_unknown_type_edge_and_no_room_dropped() -> None:
    """Loại/cạnh lạ bị bỏ; món quá to cho mọi cạnh bị bỏ."""
    re = edges_of(room("r1", 1200, 1000), "R1", [], [])
    answers = [
        {"type": "piano", "edge": "R1:E1", "pos": 0.5},
        {"type": "toilet", "edge": "R9:E1", "pos": 0.5},
        {"type": "kitchenCabinet", "edge": "R1:E1", "pos": 2},
    ]
    assert place_additions([re], [], answers) == []


def test_schematic_and_sheet_images() -> None:
    """Sơ đồ PNG và bảng ảnh JPEG mở được; ô hỏng/vắng ảnh vẫn vẽ."""
    walls = [wall("w1", (0, 0), (3000, 0))]
    re = edges_of(room("r1", 3000, 2000), "R1", [door("o1", "w1", 1000)], walls)
    png = schematic([re], [furn(100, 100, 500, 500)])
    assert Image.open(io.BytesIO(png)).format == "PNG"
    assert Image.open(io.BytesIO(schematic([], []))).size == (1180, 1180)
    thumb = io.BytesIO()
    Image.new("RGBA", (300, 200), (10, 20, 30, 128)).save(thumb, "PNG")
    cards = [
        Profile("a", 900, 600, 800, "sofa", lightness=70, warmth=3, pattern_std=5),
        Profile("b", 900, 600, 800, "sofa"),
        Profile("c", 900, 600, 800, "sofa"),
    ]
    jpg = contact_sheet(cards, {"a": thumb.getvalue(), "b": b"not an image"})
    im = Image.open(io.BytesIO(jpg))
    assert im.format == "JPEG"
    assert im.size == (660, 266)
    assert Image.open(io.BytesIO(contact_sheet([], {}))).size == (220, 266)
