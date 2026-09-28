"""Trần thời gian trên trang thật (B3-06 [8]): luật < 5 s ở 20.000 tường, trộn < 1 s ở 3.000 x 3.000 tường.

Đo bằng `time.perf_counter` **sau một lượt khởi động** ở bước 5b (không coverage, BE-00 §12); số đo in
bằng `logging`, không `print`. Dựng dữ liệu nằm ngoài phần đo. Không so với bản tham chiếu ở cỡ này (O(n·m)
sẽ chạy hàng chục giây): tính đúng đã được đối chiếu ở `test_random.py` và `test_post_rules.py`.
"""

import logging
import random
import time
from typing import Final

import pytest

from packages.domain.rules_ai import apply_post_rules, merge_pipeline_result
from packages.domain.rules_ai.tests.builders import box_room, furniture, layer, opening, wall
from packages.domain.spatial import Furniture, Opening, Room, SpatialLayer, Wall

_LOG = logging.getLogger(__name__)

RULES_BUDGET_S: Final = 5.0
MERGE_BUDGET_S: Final = 1.0
_COLUMNS: Final = 100
_CELL: Final = 4000
_MERGE_WALLS: Final = 3000
_MERGE_ROOM_SIDE: Final = 20
_SEED: Final = 20250928


def _rules_layer() -> SpatialLayer:
    """20.000 tường, 5.000 phòng (lưới 100 x 50 ô 4 x 4 m), 2.000 đồ áp tường khe 51..300, 1.000 cửa sổ AI."""
    walls: list[Wall] = []
    rooms: list[Room] = []
    openings: list[Opening] = []
    fixtures: list[Furniture] = []
    for index in range(5000):
        x0, y0 = (index % _COLUMNS) * _CELL, (index // _COLUMNS) * _CELL
        corners = [(x0, y0), (x0 + _CELL, y0), (x0 + _CELL, y0 + _CELL), (x0, y0 + _CELL)]
        window = index < 1000
        for side in range(4):
            number = index * 4 + side
            hosted = window and side == 0
            walls.append(
                wall(
                    number, corners[side], corners[(side + 1) % 4], opening_ids=(f"D-T{number:09d}",) if hosted else ()
                )
            )
            if hosted:
                openings.append(opening(number, number))
        rooms.append(box_room(index, (x0, y0), (x0 + _CELL, y0 + _CELL)))
        if index % 5 < 2:  # 2.000 đồ: áp tường tây (mặt ở x0 + 50) với khe 51..300
            gap = 51 + (index * 37) % 250
            kind = "sanitaryFixture" if index % 2 else "kitchenCabinet"
            fixtures.append(furniture(index, (x0 + 50 + gap + 300, y0 + _CELL // 2), kind=kind))
    return layer(walls=tuple(walls), openings=tuple(openings), rooms=tuple(rooms), furniture_items=tuple(fixtures))


@pytest.mark.perf
def test_perf_apply_post_rules_on_a_real_sized_page() -> None:
    """20.000 tường, 2.000 đồ, 1.000 cửa sổ AI, 5.000 phòng: `apply_post_rules` dưới 5 giây."""
    warm = _rules_layer_small()
    apply_post_rules(warm)
    source = _rules_layer()
    assert (len(source.walls), len(source.furniture), len(source.openings), len(source.rooms)) == (
        20000,
        2000,
        1000,
        5000,
    )
    start = time.perf_counter()
    result = apply_post_rules(source)
    seconds = time.perf_counter() - start
    _LOG.info(
        "apply_post_rules 20.000 tường/2.000 đồ/1.000 cửa sổ/5.000 phòng: %.2fs (trần %.0fs)", seconds, RULES_BUDGET_S
    )
    assert sum(a != b for a, b in zip(result.furniture, source.furniture, strict=True)) == 2000
    assert seconds < RULES_BUDGET_S


def _rules_layer_small() -> SpatialLayer:
    """Lớp nhỏ cho lượt khởi động (nạp module, cấp phát lần đầu)."""
    return layer(
        walls=(wall(1, (0, 0), (4000, 0)),),
        rooms=(box_room(1, (0, 0), (4000, 4000)),),
        furniture_items=(furniture(1, (3000, 500)),),
    )


def _merge_inputs() -> tuple[SpatialLayer, SpatialLayer]:
    """`current`: 3.000 tường người vẽ + 400 phòng đã duyệt; `ai`: cùng cỡ, một nửa trùng, một nửa lệch."""
    rng = random.Random(_SEED)  # noqa: S311 — dữ liệu thử tất định theo seed
    kept, fresh = [], []
    for index in range(_MERGE_WALLS):
        x0, y0 = (index % 60) * 5000 - 150_000, (index // 60) * 400
        kept.append(wall(index, (x0, y0), (x0 + 3000, y0), source="human", reviewed=True))
        shift = rng.randint(-30, 30) if index % 2 == 0 else 500  # chẵn: trùng (trong 50 mm); lẻ: xa
        fresh.append(wall(100_000 + index, (x0 + shift, y0), (x0 + 3000 + shift, y0)))
    kept_rooms, fresh_rooms = [], []
    for index in range(400):
        x0, y0 = (index % _MERGE_ROOM_SIDE) * _CELL, (index // _MERGE_ROOM_SIDE) * _CELL
        kept_rooms.append(box_room(index, (x0, y0), (x0 + _CELL, y0 + _CELL), source="human", reviewed=True))
        inset = 100 if index % 2 == 0 else 0
        offset = 0 if index % 2 == 0 else 100_000  # lẻ: dời xa khỏi mọi phòng `K`
        fresh_rooms.append(
            box_room(
                100_000 + index,
                (x0 + inset + offset, y0 + inset),
                (x0 + _CELL - inset + offset, y0 + _CELL - inset),
            )
        )
    return layer(walls=tuple(kept), rooms=tuple(kept_rooms)), layer(walls=tuple(fresh), rooms=tuple(fresh_rooms))


@pytest.mark.perf
def test_perf_merge_on_three_thousand_by_three_thousand_walls() -> None:
    """3.000 tường AI x 3.000 tường `K` + 400 phòng mỗi bên: `merge_pipeline_result` dưới 1 giây."""
    merge_pipeline_result(*_merge_inputs_small())
    current, ai = _merge_inputs()
    start = time.perf_counter()
    result = merge_pipeline_result(current, ai)
    seconds = time.perf_counter() - start
    _LOG.info(
        "merge_pipeline_result 3.000x3.000 tường + 400 phòng mỗi bên: %.2fs (trần %.0fs)", seconds, MERGE_BUDGET_S
    )
    matched_walls = sum(1 for key in result.id_map if key.startswith("W-"))
    matched_rooms = sum(1 for key in result.id_map if key.startswith("R-"))
    assert (matched_walls, matched_rooms) == (_MERGE_WALLS // 2, 200)
    assert seconds < MERGE_BUDGET_S


def _merge_inputs_small() -> tuple[SpatialLayer, SpatialLayer]:
    """Cặp nhỏ cho lượt khởi động của trộn."""
    return (
        layer(walls=(wall(1, (0, 0), (4000, 0), source="human", reviewed=True),)),
        layer(walls=(wall(9, (10, 0), (4010, 0)),)),
    )
