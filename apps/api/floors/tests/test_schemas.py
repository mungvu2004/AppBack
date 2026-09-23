"""Test thân ghi #10, #34 (B2-03 [2]): bảng biên số mm/order, luật `name`, khoá lạ/nhận-bỏ.

`FloorCreateIn`, `FloorPatchIn` dùng chung `clean_name`/`clean_mm` với `view_parts.py`
(R-07); test ở đây phủ hai hàm thuần đó qua đường Pydantic.
"""

import math
from typing import Any

import pytest
from pydantic import ValidationError

from apps.api.floors.schemas import FloorCreateIn, FloorPatchIn, FloorReorderIn, clean_level_id, clean_mm, clean_name


def _body(**overrides: Any) -> dict[str, Any]:
    """Thân #10 hợp lệ như `floorWriteBodyOf` gửi."""
    return {"id": "L-0000000001", "name": "Tầng 1", "order": 0, "elevationMm": 0, "heightMm": 3000} | overrides


def _field_of(exc: ValidationError) -> str:
    return str(exc.errors()[0]["loc"][0])


def test_create_accepts_valid_fe_body() -> None:
    """Thân FE thật (kèm `drawings: []`, `areaM2`) là hợp lệ."""
    body = FloorCreateIn.model_validate(_body(drawings=[], areaM2=1.5))
    assert (body.id, body.name, body.order, body.elevation_mm, body.height_mm) == (
        "L-0000000001",
        "Tầng 1",
        0,
        0,
        3000,
    )


@pytest.mark.parametrize("key", ["drawings", "areaM2"])
def test_create_ignores_extra_contract_keys(key: str) -> None:
    """`drawings`, `areaM2` FE gửi thừa được nhận rồi bỏ (W18)."""
    body = FloorCreateIn.model_validate(_body(**{key: [1, 2]}))
    assert body.name == "Tầng 1"


def test_unknown_key_rejected_even_project_id() -> None:
    """Khoá lạ, kể cả `projectId`, → 422 (W21, `extra="forbid"` của `WireRequest`)."""
    with pytest.raises(ValidationError):
        FloorCreateIn.model_validate(_body(projectId="prj_x"))


@pytest.mark.parametrize(
    ("field", "value", "ok"),
    [
        ("id", "L-abc", False),
        ("id", "L-0123456789", True),
        ("id", "L-" + "A" * 64, True),
        ("id", "L-" + "A" * 65, False),
    ],
)
def test_id_must_match_is_spatial_id(field: str, value: str, ok: bool) -> None:
    """`id` sai `is_spatial_id("level", …)` → 422 `field:"id"`."""
    if ok:
        assert FloorCreateIn.model_validate(_body(**{field: value})).id == value
    else:
        with pytest.raises(ValidationError) as caught:
            FloorCreateIn.model_validate(_body(**{field: value}))
        assert _field_of(caught.value) == "id"


def test_create_missing_id_rejected() -> None:
    """Thiếu `id` → 422 `field:"id"`."""
    body = _body()
    del body["id"]
    with pytest.raises(ValidationError) as caught:
        FloorCreateIn.model_validate(body)
    assert _field_of(caught.value) == "id"


@pytest.mark.parametrize(
    ("length", "ok"),
    [(0, False), (1, True), (120, True), (121, False)],
)
def test_name_length_bounds(length: int, ok: bool) -> None:
    """`name` 1-120 ký tự sau chuẩn hoá (trim + NFC)."""
    value = "x" * length if length else "   "
    if ok:
        assert FloorCreateIn.model_validate(_body(name=value)).name == "x" * length
    else:
        with pytest.raises(ValidationError) as caught:
            FloorCreateIn.model_validate(_body(name=value))
        assert _field_of(caught.value) == "name"


def test_name_length_measured_after_trim() -> None:
    """`"  ab  "` là 2 ký tự sau trim, không phải 6."""
    assert FloorCreateIn.model_validate(_body(name="  ab  ")).name == "ab"


def test_name_normalized_to_nfc() -> None:
    """NFD người dùng dán vào được chuẩn hoá NFC (C16, K20)."""
    nfd_name = "Tầng" + "́"  # tổ hợp base + dấu rời, dựng chuỗi NFD giả lập
    result = FloorCreateIn.model_validate(_body(name=nfd_name)).name
    import unicodedata

    assert result == unicodedata.normalize("NFC", nfd_name)


@pytest.mark.parametrize("bad", ["‮", "⁦", "\x07", "\x1b"])
def test_name_rejects_control_and_bidi_characters(bad: str) -> None:
    """Ký tự Cc và đảo chiều (U+202A-202E, U+2066-2069) bị chặn, kèm `field:"name"`."""
    with pytest.raises(ValidationError) as caught:
        FloorCreateIn.model_validate(_body(name=f"Tầng{bad}A"))
    assert _field_of(caught.value) == "name"


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("elevationMm", 1004.9999999999999, 1005),
        ("order", 0, 0),
        ("order", 999, 999),
        ("elevationMm", -30000, -30000),
        ("elevationMm", 300000, 300000),
        ("heightMm", 2000, 2000),
        ("heightMm", 10000, 10000),
    ],
)
def test_numeric_fields_accept_boundary_and_near_integer_values(field: str, value: float, expected: int) -> None:
    """Biên hợp lệ và làm tròn số lệch nguyên gần nhất <= 0.01."""
    body = FloorCreateIn.model_validate(_body(**{field: value}))
    attr = {"order": "order", "elevationMm": "elevation_mm", "heightMm": "height_mm"}[field]
    assert getattr(body, attr) == expected
    assert isinstance(getattr(body, attr), int)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("order", 1000),
        ("order", -1),
        ("elevationMm", -30001),
        ("elevationMm", 300001),
        ("heightMm", 1999),
        ("heightMm", 10001),
        ("elevationMm", 1004.5),
        ("elevationMm", True),
        ("elevationMm", "12"),
        ("elevationMm", math.inf),
        ("elevationMm", math.nan),
        ("elevationMm", None),
    ],
)
def test_numeric_fields_reject_out_of_range_or_wrong_type(field: str, value: object) -> None:
    """Ngoài dải, lệch quá 0.01, `bool`, chuỗi, `inf`/`nan`, `null` đều → 422 kèm đúng `field`."""
    with pytest.raises(ValidationError) as caught:
        FloorCreateIn.model_validate(_body(**{field: value}))
    assert _field_of(caught.value) == field


def test_patch_accepts_empty_body() -> None:
    """`{}` là thân hợp lệ của #34 (last-write-wins, không đổi gì)."""
    body = FloorPatchIn.model_validate({})
    assert body.model_fields_set == set()


@pytest.mark.parametrize("key", ["id", "name", "order", "elevationMm", "heightMm"])
def test_patch_rejects_explicit_null(key: str) -> None:
    """`null` tường minh cho một khoá tuỳ chọn → 422 kèm đúng `field`; vắng khoá mới là "không đổi"."""
    with pytest.raises(ValidationError) as caught:
        FloorPatchIn.model_validate({key: None})
    assert _field_of(caught.value) == key


def test_patch_accepts_partial_body() -> None:
    """Chỉ gửi một khoá vẫn hợp lệ; khoá vắng giữ `None`."""
    body = FloorPatchIn.model_validate({"heightMm": 3500})
    assert (body.height_mm, body.name, body.order) == (3500, None, None)


def test_clean_name_rejects_non_string_by_passthrough() -> None:
    """Giá trị không phải chuỗi đi thẳng cho Pydantic báo lỗi kiểu, không `AttributeError`."""
    with pytest.raises(ValidationError) as caught:
        FloorCreateIn.model_validate(_body(name=7))
    assert _field_of(caught.value) == "name"


def test_clean_name_pure_function_matches_schema_rule() -> None:
    """`clean_name` dùng lại được ngoài Pydantic (hook `project.create_floors`, R-07)."""
    assert clean_name("  Tầng 2  ") == "Tầng 2"
    with pytest.raises(ValueError, match="1-120"):
        clean_name("   ")


def test_clean_mm_pure_function_matches_schema_rule() -> None:
    """`clean_mm` dùng lại được ngoài Pydantic; cùng luật làm tròn/dải với schema."""
    assert clean_mm(1004.9999999999999, field="elevationMm", lo=-30_000, hi=300_000) == 1005
    with pytest.raises(ValueError, match="elevationMm"):
        clean_mm(1004.5, field="elevationMm", lo=-30_000, hi=300_000)
    with pytest.raises(ValueError, match="heightMm"):
        clean_mm(True, field="heightMm", lo=2_000, hi=10_000)


def test_clean_level_id_passes_through_non_string_for_pydantic_type_error() -> None:
    """`clean_level_id` không phải chuỗi thì trả nguyên, để Pydantic báo lỗi kiểu của chính nó."""
    assert clean_level_id(7) == 7


def test_floor_reorder_in_declares_floor_ids_field() -> None:
    """`FloorReorderIn` chỉ khai cho OpenAPI (resolver đọc thân thô, B2-03 [2])."""
    body = FloorReorderIn.model_validate({"floorIds": ["L-1", "L-2"]})
    assert body.floor_ids == ["L-1", "L-2"]
