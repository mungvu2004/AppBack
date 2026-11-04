"""Test `furniture_dedup.dedupe_furniture` (BENCH3D-26): mỗi luật một ca, và các ca không được xoá nhầm."""

import itertools
import logging
from typing import Any

import pytest

from apps.worker.pipeline_build.furniture_dedup import dedupe_furniture
from apps.worker.pipeline_build.tests.helpers import build_wrapped
from packages.domain.spatial import BoundingBox, Furniture, Point, Room, SpatialLayer
from packages.ml_contracts.labels import LABEL_TARGETS
from packages.ml_contracts.synthetic import EVAL_SET_SEEDS, render_plan
from packages.testing.fixtures.clock import FakeClock

_LEVEL = "L-LEVEL00000000001"
_ROOMS = {"bathroom": "R-ROOM0000000001", "kitchen": "R-ROOM0000000002", "bedroom": "R-ROOM0000000003"}

Box = tuple[int, int, int, int]


def _item(index: int, kind: str, box: Box, confidence: float = 0.8, room: str | None = None, **extra: Any) -> Furniture:
    """Món AI chưa duyệt, hộp `box` = (x0, y0, x1, y1), tên `F-FURN…{index}` để so kết quả."""
    x0, y0, x1, y1 = box
    fields: dict[str, Any] = {
        "id": f"F-FURN{index:010d}",
        "level_id": _LEVEL,
        "room_id": None if room is None else _ROOMS[room],
        "kind": kind,
        "centre": Point(x=(x0 + x1) // 2, y=(y0 + y1) // 2),
        "bounding_box": BoundingBox(min=Point(x=x0, y=y0), max=Point(x=x1, y=y1)),
        "rotation_deg": 0.0,
        "confidence": confidence,
        "source": "ai",
        "reviewed": False,
    }
    return Furniture(**(fields | extra))


def _kept(*items: Furniture) -> list[int]:
    """Số thứ tự các món còn lại sau lọc."""
    return [int(item.id[-10:]) for item in _layer(*items).furniture]


def _layer(*items: Furniture) -> SpatialLayer:
    """Lớp sau lọc (phòng đủ ba công năng của `_ROOMS`)."""
    outline = (Point(x=0, y=0), Point(x=9000, y=0), Point(x=9000, y=9000))
    rooms = tuple(
        Room(
            id=room_id,
            level_id=_LEVEL,
            name="phòng",
            usage=usage,
            outline=outline,
            area_m2=40.0,
            wall_ids=(),
            confidence=0.9,
            source="ai",
            reviewed=False,
        )
        for usage, room_id in _ROOMS.items()
    )
    return dedupe_furniture(SpatialLayer(walls=(), openings=(), rooms=rooms, furniture=items))


def test_same_kind_high_iou_keeps_higher_confidence() -> None:
    """Luật 1: một cái giường nhận hai lần, IoU ≈ 0,9 → giữ độ tin cao hơn dù đứng sau."""
    assert _kept(_item(0, "bed", (0, 0, 2000, 1600), 0.6), _item(1, "bed", (0, 0, 2000, 1450), 0.9)) == [1]


def test_equal_confidence_keeps_first() -> None:
    """Hoà hoàn toàn: món đứng trước ở lại, để kết quả tất định."""
    assert _kept(_item(0, "bed", (0, 0, 2000, 1600)), _item(1, "bed", (0, 0, 2000, 1600))) == [0]


def test_same_kind_nested_drops_small_even_if_more_confident() -> None:
    """Luật 2: vòi độ tin cao trong bồn tắm độ tin thấp, cùng `sanitaryFixture` → giữ bồn."""
    tub = _item(0, "sanitaryFixture", (0, 0, 1700, 800), 0.37, "bathroom")
    assert _kept(tub, _item(1, "sanitaryFixture", (10, 200, 230, 600), 0.64, "bathroom")) == [0]


def test_cross_kind_same_place_prefers_room_then_confidence() -> None:
    """Luật 3: cùng chỗ hai nhãn (IoU ≥ 0,6): đúng công năng phòng thắng; không ai đúng thì độ tin."""
    box = (0, 0, 1000, 500)
    in_bath = _kept(_item(0, "kitchenCabinet", box, 0.9, "bathroom"), _item(1, "sanitaryFixture", box, 0.5, "bathroom"))
    assert in_bath == [1]
    assert _kept(_item(0, "chair", box, 0.3), _item(1, "table", box, 0.8)) == [1]


def test_small_fixed_in_big_fixed_is_dropped() -> None:
    """Luật 4 (f-22): gối nhận thành `sanitaryFixture` nằm trên giường → bỏ, giường ở lại dù IoU rất nhỏ."""
    bed = _item(0, "bed", (0, 0, 2800, 2000), 0.63, "bedroom")
    assert _kept(bed, _item(1, "sanitaryFixture", (2500, 300, 2790, 820), 0.37, "bedroom")) == [0]


def test_vanity_in_bathroom_keeps_the_fixture_inside() -> None:
    """Luật 4 (f-22): hộp "tủ bếp" bao chậu trong phòng tắm: chỉ chậu đúng công năng → bỏ tủ, không bỏ chậu."""
    vanity = _item(0, "kitchenCabinet", (0, 0, 830, 460), 0.66, "bathroom")
    assert _kept(vanity, _item(1, "sanitaryFixture", (150, 10, 660, 450), 0.66, "bathroom")) == [1]


def test_sink_in_kitchen_run_becomes_thin_sink() -> None:
    """Luật 5: chậu trong dãy tủ không dính phòng tắm: giữ cả hai, chậu thành dạng mỏng; tủ không đổi."""
    for usage in ("kitchen", None):
        run = _item(0, "kitchenCabinet", (0, 0, 3000, 600), 0.6, usage)
        sink = _item(1, "sanitaryFixture", (500, 50, 1000, 550), 0.9, usage)
        kept_run, kept_sink = _layer(run, sink).furniture
        assert kept_run is run
        assert (kept_sink.kind, kept_sink.variant, kept_sink.height_mm) == ("sanitaryFixture", "sink", 20)
        assert kept_sink.bounding_box == sink.bounding_box


def test_thin_sink_is_idempotent() -> None:
    """Chạy lại lớp đã lọc: chậu mỏng không còn là cặp trùng, kết quả y nguyên và trả đúng đối tượng cũ."""
    run = _item(0, "kitchenCabinet", (0, 0, 3000, 600), 0.6, "kitchen")
    bed = _item(2, "bed", (5000, 0, 7800, 2000), 0.6, "bedroom")
    pillow = _item(3, "sanitaryFixture", (7500, 300, 7790, 820), 0.3, "bedroom")
    once = _layer(run, _item(1, "sanitaryFixture", (500, 50, 1000, 550), 0.9, "kitchen"), bed, pillow)
    assert len(once.furniture) == 3
    assert dedupe_furniture(once) is once


def test_duplicate_of_a_sink_is_removed_before_it_turns_thin() -> None:
    """Hai hộp cùng một chậu trong dãy tủ: bỏ một, món còn lại mới thành chậu mỏng (không để hai chậu mỏng chồng)."""
    run = _item(0, "kitchenCabinet", (0, 0, 3000, 600), 0.6, "kitchen")
    first = _item(1, "sanitaryFixture", (500, 50, 1000, 550), 0.9, "kitchen")
    second = _item(2, "sanitaryFixture", (500, 50, 1000, 540), 0.5, "kitchen")
    assert [item.id for item in _layer(run, first, second).furniture] == [run.id, first.id]


def test_suggested_fixture_in_run_is_dropped_not_converted() -> None:
    """Gợi ý từ mực dư trong dãy tủ thật: luật gợi ý thua đồ thật đứng trước luật chậu."""
    run = _item(0, "kitchenCabinet", (0, 0, 3000, 600), 0.6, "kitchen")
    assert _kept(run, _item(1, "sanitaryFixture", (500, 50, 1000, 550), 0.9, "kitchen", suggested=True)) == [0]


def test_shower_in_run_follows_the_room() -> None:
    """Buồng tắm lồng trong dãy tủ không phải chậu: ở bếp bỏ buồng tắm, ở phòng tắm bỏ hộp tủ."""
    box, inner = (0, 0, 3000, 1200), (100, 100, 1000, 1000)
    assert _kept(_item(0, "kitchenCabinet", box, 0.6, "kitchen"), _item(1, "shower", inner, 0.9, "kitchen")) == [0]
    assert _kept(_item(0, "kitchenCabinet", box, 0.9, "bathroom"), _item(1, "shower", inner, 0.5, "bathroom")) == [1]


def test_washing_machine_in_run_is_kept() -> None:
    """Không xoá nhầm: máy giặt âm tủ là hai món thật, kể cả ở phòng không phải phòng tắm."""
    run = _item(0, "kitchenCabinet", (0, 0, 3000, 600), 0.9, "kitchen")
    assert _kept(run, _item(1, "washingMachine", (2300, 0, 2900, 600), 0.7, "kitchen")) == [0, 1]


def test_chairs_nested_in_a_long_seat_box_are_kept() -> None:
    """Không xoá nhầm (ch-10, cn-17): ghế thật trong hộp "ghế dài" cùng loại bao cả hàng: giữ cả, không đoán."""
    bench = _item(0, "chair", (0, 0, 325, 1608), 0.3, variant="bench")
    assert _kept(bench, _item(1, "chair", (0, 100, 324, 586), 0.81), _item(2, "chair", (0, 700, 324, 1186), 0.85)) == [
        0,
        1,
        2,
    ]


def test_same_chair_detected_twice_is_still_merged() -> None:
    """`chair` chỉ miễn luật lồng nhau; hai hộp cùng một ghế (IoU cao) vẫn gộp."""
    assert _kept(_item(0, "chair", (0, 0, 500, 500), 0.4), _item(1, "chair", (0, 0, 500, 480), 0.8)) == [1]


def test_result_does_not_depend_on_list_order() -> None:
    """Hoà độ tin và IoU: mọi hoán vị cho cùng nội dung (cn-15 từng đổi theo thứ tự danh sách)."""
    box = (0, 0, 1000, 500)
    items = [_item(0, "chair", box, 0.5), _item(1, "table", box, 0.5), _item(2, "other", box, 0.5)]
    contents = {
        tuple(sorted(item.kind for item in _layer(*order).furniture)) for order in itertools.permutations(items)
    }
    assert len(contents) == 1


def test_log_counts_changes(caplog: pytest.LogCaptureFixture) -> None:
    """Món bỏ và chậu đổi được đếm ở log của module."""
    run = _item(0, "kitchenCabinet", (0, 0, 3000, 600), 0.6, "kitchen")
    sink = _item(1, "sanitaryFixture", (500, 50, 1000, 550), 0.9, "kitchen")
    bed = _item(2, "bed", (5000, 0, 7000, 1600), 0.9)
    with caplog.at_level(logging.INFO, logger="apps.worker.pipeline_build.furniture_dedup"):
        _layer(run, sink, bed, _item(3, "bed", (5000, 0, 7000, 1600), 0.5))
    record = next(r for r in caplog.records if r.message == "pipeline_build_furniture_deduped")
    assert (record.__dict__["dropped"], record.__dict__["sinks"]) == (1, 1)


def test_suggested_loses_to_real_item() -> None:
    """Đồ thật thắng gợi ý từ mực dư dù gợi ý độ tin cao hơn."""
    box = (0, 0, 1000, 500)
    assert _kept(_item(0, "table", box, 0.9, suggested=True), _item(1, "table", box, 0.4)) == [1]


def test_small_item_on_big_item_is_kept() -> None:
    """Không xoá nhầm: đèn `other` trên bàn, gối `other` trên giường, ghế dưới bàn có IoM 1 nhưng là đồ thật."""
    table = _item(0, "table", (0, 0, 1800, 900))
    lamp = _item(1, "other", (100, 100, 400, 400))
    chair = _item(2, "chair", (700, 100, 1100, 500))
    bed = _item(3, "bed", (5000, 0, 7000, 1600))
    pillow = _item(4, "other", (5100, 100, 5500, 700))
    assert _kept(table, lamp, chair, bed, pillow) == [0, 1, 2, 3, 4]


def test_other_nested_in_other_is_kept() -> None:
    """Không xoá nhầm: `other` là nhóm hỗn tạp, lồng nhau không chứng minh trùng (cần IoU cao)."""
    assert _kept(_item(0, "other", (0, 0, 1000, 1000)), _item(1, "other", (100, 100, 300, 300))) == [0, 1]


def test_tall_cabinet_inside_l_run_box_is_kept() -> None:
    """Không xoá nhầm: tủ cao nhãn `wardrobe` trong hộp bao dãy tủ chữ L là hai món thật."""
    run = _item(0, "kitchenCabinet", (0, 0, 2700, 1900), 0.94, "kitchen")
    assert _kept(run, _item(1, "wardrobe", (2100, 1300, 2600, 1800), 0.92, "kitchen")) == [0, 1]


def test_light_overlap_is_kept() -> None:
    """Không xoá nhầm: hai ghế sát nhau chồng mép, tủ kề dãy bếp chồng ít: dưới mọi ngưỡng."""
    assert _kept(_item(0, "chair", (0, 0, 500, 500)), _item(1, "chair", (400, 0, 900, 500))) == [0, 1]
    assert _kept(_item(0, "wardrobe", (0, 0, 1000, 600)), _item(1, "bed", (800, 0, 2800, 1600))) == [0, 1]


def test_human_and_reviewed_items_are_untouched() -> None:
    """K21: thảm người đặt dưới giường AI, món đã duyệt trùng món khác: không bị xét, cả hai ở lại."""
    box = (0, 0, 2000, 1600)
    rug = _item(1, "bed", box, 1.0, source="human")
    assert _kept(_item(0, "bed", box, 0.7), rug) == [0, 1]
    assert _kept(_item(0, "bed", box, 0.7, reviewed=True), _item(1, "bed", box, 0.9)) == [0, 1]


def test_rotated_box_is_compared_in_world_frame() -> None:
    """Hộp quay 90° so bằng `world_box`: 2000x400 quay thành 400x2000 mới trùng hộp 400x2000 bên cạnh."""
    turned = _item(0, "bed", (200, 800, 2200, 1200), 0.9, rotation_deg=90.0)
    assert _kept(turned, _item(1, "bed", (1000, 0, 1400, 2000), 0.5)) == [0]


def test_chain_loses_one_at_a_time() -> None:
    """Chuỗi A-B-C: món đã bỏ không loại thêm món khác (A trùng B, B trùng C, A không trùng C → còn A và C)."""
    a = _item(0, "chair", (0, 0, 1000, 1000), 0.9)
    b = _item(1, "chair", (200, 0, 1200, 1000), 0.8)
    c = _item(2, "chair", (400, 0, 1400, 1000), 0.7)
    assert _kept(a, b, c) == [0, 2]


def test_nothing_to_do_returns_same_layer() -> None:
    """Dưới hai món hoặc không có cặp trùng: trả nguyên đối tượng."""
    empty = SpatialLayer(walls=(), openings=(), rooms=(), furniture=())
    assert dedupe_furniture(empty) is empty
    apart = SpatialLayer(
        walls=(),
        openings=(),
        rooms=(),
        furniture=(_item(0, "chair", (0, 0, 10, 10)), _item(1, "chair", (50, 50, 60, 60))),
    )
    assert dedupe_furniture(apart) is apart


def test_build_layer__one_object_detected_twice_is_one_item(fake_clock: FakeClock) -> None:
    """Đường dựng thật đi qua bộ lọc: nhân đôi một hộp đồ ở đầu vào, số đồ ở lớp ra không đổi."""
    plan = render_plan(EVAL_SET_SEEDS[0])
    shared: dict[str, Any] = {
        "walls": plan.walls,
        "texts": plan.texts,
        "width_px": plan.pixels.shape[1],
        "height_px": plan.pixels.shape[0],
    }
    twice = next(d for d in plan.detections if (t := LABEL_TARGETS.get(d.label)) and t.category == "furniture")
    once = build_wrapped(**shared, detections=plan.detections, clock=FakeClock(start=fake_clock.now()))
    doubled = build_wrapped(**shared, detections=(*plan.detections, twice), clock=FakeClock(start=fake_clock.now()))
    assert len(doubled.layer.furniture) == len(once.layer.furniture)
