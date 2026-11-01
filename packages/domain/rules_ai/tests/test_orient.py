"""Luật 4 — hướng đồ (`orient.py`): ghế vào bàn, lưng tựa tường, chọn cạnh tựa, hoán hộp, không đụng đồ đã duyệt."""

from typing import Any

import pytest

from packages.domain.rules_ai import apply_post_rules
from packages.domain.rules_ai.tests.builders import furniture, layer, wall
from packages.domain.rules_ai.tests.reference import ref_apply_post_rules
from packages.domain.spatial import BoundingBox, Furniture, Point, Wall

# Góc phòng: tường ngang y = 0 và tường dọc x = 0, dày 100 (mặt ở 50); phòng nằm phía +x, +y.
TOP = wall(1, (0, 0), (6000, 0))
LEFT = wall(2, (0, 0), (0, 6000))


def _item(
    number: int, kind: str, box: tuple[int, int, int, int], variant: str | None = None, **flags: Any
) -> Furniture:
    """Đồ hộp `(x0, y0, x1, y1)`."""
    x0, y0, x1, y1 = box
    base = furniture(number, ((x0 + x1) // 2, (y0 + y1) // 2), kind=kind, **flags)
    return base.model_copy(
        update={"bounding_box": BoundingBox(min=Point(x=x0, y=y0), max=Point(x=x1, y=y1)), "variant": variant}
    )


def _run(*items: Furniture, walls: tuple[Wall, ...] = (TOP, LEFT)) -> tuple[Furniture, ...]:
    """Qua `apply_post_rules`, kiểm bằng bản quét hết và idempotent, trả đồ ra."""
    source = layer(walls=walls, furniture_items=items)
    result = apply_post_rules(source)
    assert result == ref_apply_post_rules(source)
    assert apply_post_rules(result) == result
    return result.furniture


def test_chair__faces_the_nearest_table_and_swaps_its_box() -> None:
    table = _item(1, "table", (3000, 3000, 4200, 3800))
    chair = _item(2, "chair", (2300, 3100, 2800, 3700))  # phía tây bàn, khe 200, hộp 500 x 600
    _, turned = _run(table, chair)
    assert turned.rotation_deg == 270  # nhìn sang E
    assert turned.bounding_box == BoundingBox(min=Point(x=2250, y=3150), max=Point(x=2850, y=3650))


def test_chair__without_a_table_backs_onto_the_near_wall() -> None:
    (chair,) = _run(_item(1, "chair", (3000, 4950, 3500, 5450)), walls=(wall(3, (0, 6000), (6000, 6000)),))
    assert chair.rotation_deg == 180  # tường phía S, mặt nhìn N


def test_bed__corner_backs_onto_the_short_side() -> None:
    (bed,) = _run(_item(1, "bed", (100, 100, 2100, 1700)))  # dài theo x: cạnh ngắn nằm dọc, tựa tường LEFT
    assert bed.rotation_deg == 270
    assert bed.bounding_box == BoundingBox(min=Point(x=300, y=-100), max=Point(x=1900, y=1900))


def test_wc__corner_backs_onto_the_short_side() -> None:
    (wc,) = _run(_item(1, "sanitaryFixture", (100, 100, 500, 800), variant="wc"))  # hẹp theo x: tựa TOP
    assert wc.rotation_deg == 0


@pytest.mark.parametrize(
    ("kind", "variant"),
    [("wardrobe", None), ("kitchenCabinet", None), ("chair", "sofa"), ("other", "tv"), ("sanitaryFixture", "basin")],
)
def test_long_items__corner_backs_onto_the_long_side(kind: str, variant: str | None) -> None:
    (item,) = _run(_item(1, kind, (100, 100, 700, 2000), variant=variant))  # cạnh dài nằm dọc, tựa LEFT
    assert item.rotation_deg == 270


def test_other_huggers__corner_take_the_nearer_wall() -> None:
    (fridge,) = _run(_item(1, "other", (300, 100, 1000, 800), variant="fridge"))  # TOP khe 50, LEFT khe 250
    assert fridge.rotation_deg == 0
    (machine,) = _run(_item(1, "washingMachine", (100, 300, 700, 900)))
    assert machine.rotation_deg == 270


def test_sofa__ignores_tables_and_backs_onto_the_wall() -> None:
    table = _item(1, "table", (5200, 5000, 5800, 5700))  # ghế thường sẽ quay E vào bàn này
    sofa = _item(2, "chair", (3000, 4950, 5000, 5800), variant="sofa")
    _, result = _run(table, sofa, walls=(wall(3, (0, 6000), (6000, 6000)),))
    assert result.rotation_deg == 180


def test_no_wall_in_reach__stays_at_zero() -> None:
    bed = _item(1, "bed", (2000, 2000, 3600, 4000))
    assert _run(bed) == (bed,)


@pytest.mark.parametrize("flags", [{"reviewed": True}, {"source": "human"}])
def test_reviewed_or_human__untouched(flags: dict[str, Any]) -> None:
    bed = _item(1, "bed", (100, 100, 2100, 1700), **flags)
    assert _run(bed) == (bed,)


def test_already_rotated__untouched() -> None:
    bed = _item(1, "bed", (100, 100, 2100, 1700)).model_copy(update={"rotation_deg": 90.0})
    assert _run(bed) == (bed,)


def test_table_and_rug__never_turn() -> None:
    items = (_item(1, "table", (100, 100, 900, 900)), _item(2, "other", (100, 1000, 900, 1800), variant="rug"))
    assert _run(*items) == items
