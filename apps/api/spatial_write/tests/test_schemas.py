"""Model dây #35 ở mức hàm: các nhánh của `_scale` và luật "`body` ≥ 1 khoá" (B3-03 [6]).

Test route đã đi qua đường thường và bốn dạng sai chính; ở đây là các nhánh mà một request
HTTP không dựng nổi hay không nên dựng lại (mỗi nhánh một lượt qua Postgres là phí): kiểu
sai, `Infinity`, làm tròn `ROUND_HALF_UP`, và trần dải.
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from apps.api.spatial_write.schemas import SCALE_MAX, FloorLayerWriteBodySchema, FloorLayerWriteSchema
from apps.api.spatial_write.tests._helpers import simple_layer
from apps.api.spatial_write.tests._route_helpers import wire

LEVEL = "L-SCHEMALEVEL"
"""Tầng giả — model dây không tra DB, chỉ cần id đúng mẫu W4."""


@pytest.mark.parametrize(
    ("sent", "stored"),
    [(10, Decimal("10.000000")), (12.7, Decimal("12.700000")), (0.1234565, Decimal("0.123457")), (SCALE_MAX, None)],
)
def test_scale_is_rounded_to_six_places(sent: float, stored: Decimal | None) -> None:
    """Số nguyên JSON cũng nhận; làm tròn nửa lên 6 chữ số; trần `999 999` vẫn đạt."""
    body = FloorLayerWriteBodySchema.model_validate({"scaleMillimetresPerPixel": sent})
    assert body.scale_millimetres_per_pixel == (stored if stored is not None else Decimal(SCALE_MAX))


@pytest.mark.parametrize(
    "sent",
    [True, "10", None, float("inf"), float("nan"), 0, -1, 0.0000004, SCALE_MAX + 1, 1e22, 10**30, 10**310],
)
def test_scale_rejects_everything_outside_the_contract(sent: object) -> None:
    """bool, chuỗi, `null`, vô hạn, `NaN`, 0, số âm, 0 sau khi làm tròn, quá trần, quá lớn → lỗi trường.

    Ba giá trị cuối là biên của hai cơ chế đổi kiểu khác nhau, cả hai ném `ArithmeticError` —
    thứ mà `BeforeValidator` **không** đổi thành 422: `1e22`/`10**30` làm `Decimal.quantize`
    ném `InvalidOperation` (cần hơn 28 chữ số), còn `10**310` làm `math.isfinite` ném
    `OverflowError` (số nguyên lớn hơn `float` max). Cả ba phải ra `ValidationError` như mọi
    giá trị ngoài dải khác, không phải 500.
    """
    with pytest.raises(ValidationError):
        FloorLayerWriteBodySchema.model_validate({"scaleMillimetresPerPixel": sent})


def test_body_needs_at_least_one_key() -> None:
    """`body: {}` → lỗi ở **mức model** nên `field` của 422 là `body`, không phải một trường con."""
    with pytest.raises(ValidationError) as caught:
        FloorLayerWriteBodySchema.model_validate({})
    assert caught.value.errors()[0]["loc"] == ()


@pytest.mark.parametrize("key", ["layer", "scaleMillimetresPerPixel"])
def test_body_accepts_either_key_alone(key: str) -> None:
    """Một khoá là đủ: F-04c gửi tầng chỉ có tỉ lệ, F-04b gửi tầng chỉ có lớp."""
    value = wire(simple_layer(LEVEL)) if key == "layer" else 10.0
    body = FloorLayerWriteBodySchema.model_validate({key: value})
    assert (body.layer is None) != (body.scale_millimetres_per_pixel is None)


def test_envelope_keeps_base_version_strict() -> None:
    """`baseVersion` là số nguyên chặt: `"0"` hay `0.5` không được lọt thành 0 (W3, K20)."""
    good = FloorLayerWriteSchema.model_validate({"baseVersion": 0, "body": {"scaleMillimetresPerPixel": 1}})
    assert good.base_version == 0
    with pytest.raises(ValidationError):
        FloorLayerWriteSchema.model_validate({"baseVersion": "0", "body": {"scaleMillimetresPerPixel": 1}})
