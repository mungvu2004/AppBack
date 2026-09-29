"""`wall_mask`, `object_boxes` — vẽ nhãn thuần numpy/cv2, không I/O (BE-02 khối [8] "Vẽ")."""

from typing import Literal

import numpy as np

from apps.worker.datasets.render import object_boxes, wall_mask
from packages.domain.spatial.model import BoundingBox, Furniture, Opening, Point, Segment, SpatialLayer, Wall

MM_PER_PX = 10.0


def _wall(
    wall_id: str = "W-0000000001",
    *,
    start: tuple[int, int] = (0, 500),
    end: tuple[int, int] = (1000, 500),
    thickness: int = 200,
    kind: Literal["loadBearing", "partition", "envelope"] = "loadBearing",
    opening_ids: tuple[str, ...] = (),
) -> Wall:
    return Wall(
        id=wall_id,
        level_id="L-0000000001",
        centreline=Segment(start=Point(x=start[0], y=start[1]), end=Point(x=end[0], y=end[1])),
        thickness_mm=thickness,
        height_mm=2700,
        kind=kind,
        opening_ids=opening_ids,
        confidence=1.0,
        source="human",
        reviewed=True,
    )


def _opening(
    opening_id: str = "D-0000000001",
    *,
    wall_id: str = "W-0000000001",
    kind: Literal["door", "window"] = "door",
    offset: int = 50,
    width: int = 900,
    swing: Literal["left", "right", "double", "sliding", "fixed"] = "left",
) -> Opening:
    return Opening(
        id=opening_id,
        wall_id=wall_id,
        kind=kind,
        offset_mm=offset,
        width_mm=width,
        height_mm=2100,
        sill_height_mm=0,
        swing=swing,
        confidence=1.0,
        source="human",
        reviewed=True,
    )


def _furniture(
    furniture_id: str = "F-0000000001",
    *,
    kind: str = "table",
    box: tuple[int, int, int, int] = (0, 0, 800, 600),
) -> Furniture:
    x0, y0, x1, y1 = box
    return Furniture(
        id=furniture_id,
        level_id="L-0000000001",
        kind=kind,
        centre=Point(x=(x0 + x1) // 2, y=(y0 + y1) // 2),
        bounding_box=BoundingBox(min=Point(x=x0, y=y0), max=Point(x=x1, y=y1)),
        rotation_deg=0.0,
        confidence=1.0,
        source="human",
        reviewed=True,
    )


def test_wall_mask__horizontal_wall_region() -> None:
    # Tường dài 1.000mm (từ 100 đến 1.100), dày 200mm, mỗi đầu kéo dài nửa bề dày (100mm)
    # → vùng tô từ mm 0 đến 1.200, tỉ lệ 10 → 120x20 px, đặt gọn từ x=0 để không bị cắt.
    wall = _wall(start=(100, 500), end=(1100, 500), thickness=200)
    mask = wall_mask([wall], width_px=200, height_px=100, mm_per_px=MM_PER_PX)
    assert mask.shape == (100, 200)
    assert mask[40:60, 0:120].all()
    assert int(mask.sum()) == 120 * 20
    assert not mask[40:60, 121:200].any()


def test_wall_mask__door_gap_is_false() -> None:
    wall = _wall(start=(100, 500), end=(1100, 500), thickness=200, opening_ids=("D-0000000001",))
    door = _opening(offset=50, width=900, kind="door")
    mask = wall_mask([wall], width_px=200, height_px=100, mm_per_px=MM_PER_PX, openings=[door])
    assert not mask[40:60, 15:105].any()
    assert mask[40:60, 0:15].all()
    assert mask[40:60, 105:120].all()


def test_wall_mask__window_keeps_mask_solid() -> None:
    wall = _wall(start=(100, 500), end=(1100, 500), thickness=200)
    window = _opening(kind="window", offset=50, width=900)
    mask = wall_mask([wall], width_px=200, height_px=100, mm_per_px=MM_PER_PX, openings=[window])
    assert mask[40:60, 0:120].all()


def test_wall_mask__diagonal_wall() -> None:
    wall = _wall(start=(0, 0), end=(1000, 1000), thickness=100)
    mask = wall_mask([wall], width_px=150, height_px=150, mm_per_px=MM_PER_PX)
    assert mask[50, 50]
    assert not mask[5, 145]


def test_object_boxes__door_and_double_door_labels() -> None:
    wall = _wall(opening_ids=("D-0000000001", "D-0000000002"))
    single = _opening("D-0000000001", offset=50, width=900, swing="left")
    double = _opening("D-0000000002", offset=50, width=1800, swing="double")
    layer = SpatialLayer(walls=(wall,), openings=(single, double), rooms=(), furniture=())
    detections = object_boxes(layer, width_px=200, height_px=100, mm_per_px=MM_PER_PX)
    labels = {d.label for d in detections}
    assert labels == {"door", "double_door"}


def test_object_boxes__window_label() -> None:
    wall = _wall(opening_ids=("D-0000000001",))
    window = _opening(kind="window", offset=50, width=900)
    layer = SpatialLayer(walls=(wall,), openings=(window,), rooms=(), furniture=())
    detections = object_boxes(layer, width_px=200, height_px=100, mm_per_px=MM_PER_PX)
    assert detections[0].label == "window"


def test_object_boxes__box_clipped_to_frame() -> None:
    furniture = _furniture(box=(-500, -500, 500, 500))
    layer = SpatialLayer(walls=(), openings=(), rooms=(), furniture=(furniture,))
    detections = object_boxes(layer, width_px=30, height_px=30, mm_per_px=MM_PER_PX)
    assert len(detections) == 1
    box = detections[0].box
    assert box.x_min == 0.0
    assert box.y_min == 0.0
    assert box.x_max == 30.0
    assert box.y_max == 30.0


def test_object_boxes__box_entirely_outside_frame_dropped() -> None:
    furniture = _furniture(box=(10_000, 10_000, 11_000, 11_000))
    layer = SpatialLayer(walls=(), openings=(), rooms=(), furniture=(furniture,))
    detections = object_boxes(layer, width_px=30, height_px=30, mm_per_px=MM_PER_PX)
    assert detections == ()


def test_object_boxes__opening_box_entirely_outside_frame_dropped() -> None:
    wall = _wall(start=(10_000, 10_000), end=(11_000, 10_000), opening_ids=("D-0000000001",))
    door = _opening(offset=50, width=900)
    layer = SpatialLayer(walls=(wall,), openings=(door,), rooms=(), furniture=())
    detections = object_boxes(layer, width_px=30, height_px=30, mm_per_px=MM_PER_PX)
    assert detections == ()


def test_object_boxes__other_furniture_dropped() -> None:
    furniture = _furniture(kind="other")
    layer = SpatialLayer(walls=(), openings=(), rooms=(), furniture=(furniture,))
    detections = object_boxes(layer, width_px=200, height_px=100, mm_per_px=MM_PER_PX)
    assert detections == ()


def test_object_boxes__furniture_labels_mapped() -> None:
    kitchen = _furniture("F-0000000002", kind="kitchenCabinet", box=(0, 0, 400, 400))
    sanitary = _furniture("F-0000000003", kind="sanitaryFixture", box=(0, 0, 400, 400))
    layer = SpatialLayer(walls=(), openings=(), rooms=(), furniture=(kitchen, sanitary))
    detections = object_boxes(layer, width_px=200, height_px=100, mm_per_px=MM_PER_PX)
    labels = {d.label for d in detections}
    assert labels == {"kitchen_cabinet", "sanitary_fixture"}


def test_wall_mask__empty_walls_returns_false_canvas() -> None:
    mask = wall_mask([], width_px=50, height_px=40, mm_per_px=MM_PER_PX)
    assert mask.shape == (40, 50)
    assert mask.dtype == np.bool_
    assert not mask.any()


def test_wall_mask__orphan_door_is_skipped_and_the_rest_is_drawn() -> None:
    """Ô mở `door` trỏ tường không có trong `walls` → bỏ đúng ô đó, mặt nạ còn lại vẫn đúng (NO-274).

    Trước đây `walls_by_id[opening.wall_id]` ném `KeyError`, làm chết cả lượt dựng vì một tầng lẻ.
    """
    wall = _wall(start=(100, 500), end=(1100, 500), thickness=200, opening_ids=("D-0000000001",))
    real_door = _opening("D-0000000001", offset=50, width=900, kind="door")
    orphan = _opening("D-0000000009", wall_id="W-0000009999", offset=50, width=900, kind="door")

    mask = wall_mask([wall], width_px=200, height_px=100, mm_per_px=MM_PER_PX, openings=[orphan, real_door])

    # Giống hệt `test_wall_mask__door_gap_is_false`: ô mồ côi không thêm, không bớt pixel nào.
    assert not mask[40:60, 15:105].any()
    assert mask[40:60, 0:15].all()
    assert mask[40:60, 105:120].all()


def test_object_boxes__orphan_opening_is_skipped_and_the_rest_is_kept() -> None:
    """Ô mở mồ côi bị bỏ khỏi `detections`; tường, ô mở thật và đồ đạc vẫn ra hộp (NO-274)."""
    wall = _wall(opening_ids=("D-0000000001",))
    real_door = _opening("D-0000000001", offset=50, width=900, swing="left")
    orphan = _opening("D-0000000009", wall_id="W-0000009999", offset=50, width=900, swing="left")
    table = _furniture(box=(0, 0, 500, 500))
    layer = SpatialLayer(walls=(wall,), openings=(orphan, real_door), rooms=(), furniture=(table,))

    detections = object_boxes(layer, width_px=200, height_px=100, mm_per_px=MM_PER_PX)

    assert [d.label for d in detections] == ["door", "table"]


def test_object_boxes__every_opening_orphan_still_returns_furniture() -> None:
    """Không ô mở nào tìm được tường: hàm vẫn trả hộp của đồ đạc thay vì ném (NO-274, ca biên)."""
    orphan = _opening("D-0000000009", wall_id="W-0000009999", offset=50, width=900)
    table = _furniture(box=(0, 0, 500, 500))
    layer = SpatialLayer(walls=(), openings=(orphan,), rooms=(), furniture=(table,))

    detections = object_boxes(layer, width_px=200, height_px=100, mm_per_px=MM_PER_PX)

    assert [d.label for d in detections] == ["table"]
