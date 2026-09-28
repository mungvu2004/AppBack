"""Test đơn vị của hàm thuần: `clean_label`, chuẩn hoá và dấu vân tay của phép đo (B2-07 [6])."""

import unicodedata

import pytest

from apps.api.measurements.schemas import MeasurementRecordIn
from apps.api.measurements.service import body_sha256, normalize
from apps.api.measurements.tests._helpers import point_body, record_body
from apps.api.measurements.text import clean_label


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("  Tường  ", "Tường"), (unicodedata.normalize("NFD", "Cửa"), "Cửa"), ("a" * 120, "a" * 120)],
)
def test_clean_label__trims_and_composes(raw: str, expected: str) -> None:
    """`nfc(strip)`: cắt khoảng trắng hai đầu, đưa về NFC, giữ đúng 120 ký tự."""
    assert clean_label(raw) == expected


@pytest.mark.parametrize("raw", ["", "  ", "a" * 121, "x‮y", "x⁩y", "x\ny"])
def test_clean_label__rejects(raw: str) -> None:
    """Rỗng, quá dài, ký tự đảo chiều hay điều khiển → `ValueError`."""
    with pytest.raises(ValueError, match=r"ký tự"):
        clean_label(raw)


def test_clean_label__custom_max_len() -> None:
    """`max_len` là tham số: 5 ký tự thì 6 ký tự bị từ chối."""
    assert clean_label("abcde", max_len=5) == "abcde"
    with pytest.raises(ValueError, match="1-5"):
        clean_label("abcdef", max_len=5)


def test_normalize__floats_negative_zero_and_absent_z() -> None:
    """Mọi số thành `float`, `-0.0` thành `0.0`, `z` vắng giữ vắng, thứ tự điểm giữ nguyên."""
    body = MeasurementRecordIn.model_validate(
        record_body(points=[point_body(-0.0, 2), point_body(3, -0.0, -0.0)], raw_value_mm=-0.0)
    )
    normalized = normalize(body)
    assert normalized["points"] == [{"x": 0.0, "y": 2.0}, {"x": 3.0, "y": 0.0, "z": 0.0}]
    assert normalized["rawValueMm"] == 0.0
    assert str(normalized["points"][0]["x"]) == "0.0"


def test_body_sha256__is_stable_and_body_sensitive() -> None:
    """Cùng thân → cùng SHA (bất kể thứ tự khoá vào); đổi một số hay thứ tự điểm → SHA khác."""
    first = MeasurementRecordIn.model_validate(record_body())
    shuffled = dict(reversed(list(record_body().items())))
    same = MeasurementRecordIn.model_validate(shuffled)
    assert body_sha256(normalize(first)) == body_sha256(normalize(same))
    moved = MeasurementRecordIn.model_validate(record_body(raw_value_mm=1.0))
    assert body_sha256(normalize(first)) != body_sha256(normalize(moved))
    reordered = MeasurementRecordIn.model_validate(record_body(points=list(reversed(record_body()["points"]))))
    assert body_sha256(normalize(first)) != body_sha256(normalize(reordered))
