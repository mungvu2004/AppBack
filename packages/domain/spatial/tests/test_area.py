"""Diện tích dây giày: đối chiếu từng con số với `src/domain/rooms/__tests__/area.test.ts`."""

from decimal import Decimal

import pytest

from packages.domain.spatial import (
    Point,
    js_round,
    polygon_area_m2,
    sample_building,
    signed_area_mm2,
    total_area_m2,
)
from packages.domain.spatial.samples import SAMPLE_TOTAL_AREA_M2


def rectangle(width: int, depth: int, left: int = 0) -> tuple[Point, ...]:
    """Hình chữ nhật ngược chiều kim đồng hồ, góc dưới trái ở `(left, 0)`."""
    corners = ((left, 0), (left + width, 0), (left + width, depth), (left, depth))
    return tuple(Point(x=x, y=y) for x, y in corners)


def outline(*corners: tuple[int, int]) -> tuple[Point, ...]:
    """Đường bao từ các cặp toạ độ."""
    return tuple(Point(x=x, y=y) for x, y in corners)


SLIVER = rectangle(125, 100)


def test_quarter_rounds_down() -> None:
    """125 x 100 mm = 0,0125 m²; x 100 = 1,25 (không phải nửa) → 0,01 (`area.test.ts:199-201`)."""
    assert polygon_area_m2(SLIVER) == Decimal("0.01")


def test_total_rounds_once() -> None:
    """Ba mảnh: làm tròn từng mảnh rồi cộng ra 0,03; `total_area_m2` cộng mm² rồi làm tròn → 0,04."""
    assert sum(polygon_area_m2(piece) for piece in (SLIVER, SLIVER, SLIVER)) == Decimal("0.03")
    assert total_area_m2([SLIVER, SLIVER, SLIVER]) == Decimal("0.04")


def test_collinear_points_give_positive_zero() -> None:
    """Ba điểm thẳng hàng → 0,00, không bao giờ `-0.00`."""
    area = polygon_area_m2(outline((0, 0), (1000, 0), (2000, 0)))
    assert (area, str(area), area.is_signed()) == (Decimal("0.00"), "0.00", False)


def test_winding_does_not_change_the_area() -> None:
    """Đổi chiều đường bao: dấu đổi, diện tích giữ."""
    forward = rectangle(5000, 4000)
    backward = tuple(reversed(forward))
    assert signed_area_mm2(forward) == 20_000_000
    assert signed_area_mm2(backward) == -20_000_000
    assert polygon_area_m2(backward) == polygon_area_m2(forward) == Decimal("20.00")


def test_concave_outlines() -> None:
    """Hình L và hình U của FE: 21,00 và 18,00 m² (hộp bao cho sai)."""
    l_shape = outline((0, 0), (6000, 0), (6000, 2500), (4000, 2500), (4000, 4000), (0, 4000))
    u_shape = outline(
        (0, 0), (6000, 0), (6000, 4000), (4000, 4000), (4000, 1000), (2000, 1000), (2000, 4000), (0, 4000)
    )
    assert polygon_area_m2(l_shape) == Decimal("21.00")
    assert polygon_area_m2(u_shape) == Decimal("18.00")


def test_fewer_than_three_points_enclose_nothing() -> None:
    """Dưới ba điểm → 0 (kiểu `Room` chặn, nhưng hàm vẫn nhận đường bao rời)."""
    assert signed_area_mm2(outline((0, 0), (1000, 0))) == 0.0
    assert signed_area_mm2(()) == 0.0
    assert total_area_m2([]) == Decimal("0.00")


def test_sum_beyond_safe_integer_is_refused() -> None:
    """Tổng chéo vượt 2^53 - 1 → `ValueError` như `RangeError` của FE (`area.test.ts:179-183`)."""
    with pytest.raises(ValueError, match="2\\^53"):
        polygon_area_m2(rectangle(10**9, 10**9))


def test_float_rounding_matches_fe_not_decimal_arithmetic() -> None:
    """1.005.000 mm² → 1,00, không 1,01.

    1,005 không biểu diễn đúng bằng số thực: `1005000 / 1e6 * 100` ra
    `100.49999999999999`, `Math.round` cho 100. FE hiện 1,00 nên BE cũng phải
    1,00; tính bằng `Decimal` (làm tròn nửa lên đúng toán) sẽ ra 1,01 và lệch FE.
    """
    assert 1_005_000 / 1_000_000 * 100 == 100.49999999999999
    assert polygon_area_m2(rectangle(1005, 1000)) == Decimal("1.00")


def test_fe_schedule_of_fourteen_rooms_totals_248_60() -> None:
    """Lịch 14 phòng của `area.test.ts:69-143`: rộng 4000 mm, sâu = diện tích khai / 4000 → 248,60."""
    rooms = sample_building().rooms
    schedule = []
    for index, room in enumerate(rooms):
        depth, remainder = divmod(js_round(room.area_m2 * 1_000_000), 4000)
        assert remainder == 0
        schedule.append(rectangle(4000, depth, left=index * 4000))
        assert polygon_area_m2(schedule[-1]) == Decimal(str(room.area_m2)).quantize(Decimal("0.01"))
    assert total_area_m2(schedule) == SAMPLE_TOTAL_AREA_M2 == Decimal("248.60")
    assert total_area_m2(reversed(schedule)) == SAMPLE_TOTAL_AREA_M2


def test_real_sample_outlines_total_238_not_248_60() -> None:
    """14 đường bao thật của mẫu A14 đo ra 17,00 mỗi phòng, tổng 238,00 ≠ 248,60.

    Hai nguồn lệch (FE CLAUDE.md A14): 248,60 là hằng khai tay (13 x 17,00 + 27,60),
    còn phòng cuối khai 27,60 nhưng đường bao vẫn là 4000 x 4250 như 13 phòng kia.
    FE chưa chốt số nào là chuẩn; test ghi lại độ lệch, không sửa cho khớp.
    """
    outlines = [room.outline for room in sample_building().rooms]
    assert {polygon_area_m2(each) for each in outlines} == {Decimal("17.00")}
    assert total_area_m2(outlines) == Decimal("238.00")
    assert total_area_m2(outlines) != SAMPLE_TOTAL_AREA_M2


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0.5, 1),
        (-0.5, 0),
        (2.5, 3),
        (-2.5, -2),
        (1.4999999999999998, 1),
        (0.49999999999999994, 0),
        (float(2**52 + 1), 2**52 + 1),
        (float(-(2**52) - 1), -(2**52) - 1),
        (123.0, 123),
    ],
)
def test_js_round_matches_math_round(value: float, expected: int) -> None:
    """`Math.round`: nửa về phía +∞; `0.49999999999999994` và `±(2^52+1)` là chỗ `floor(x + 0.5)` sai."""
    assert js_round(value) == expected


@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan")])
def test_js_round_refuses_non_finite(value: float) -> None:
    """Không làm tròn được số không hữu hạn."""
    with pytest.raises(ValueError, match="không hữu hạn"):
        js_round(value)
