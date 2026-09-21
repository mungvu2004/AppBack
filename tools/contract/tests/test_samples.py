"""Đọc mẫu golden và luật ngày giờ W3 (`tools/contract/samples.py`)."""

import json
from pathlib import Path

import pytest

from tools.contract.samples import EventSample, HttpSample, SampleError, bad_datetimes, load_samples


def _write(root: Path, rel: str, data: object) -> None:
    """Một file mẫu như bộ ghi viết."""
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_missing_directory_has_no_samples(tmp_path: Path) -> None:
    """Không đặt `CONTRACT_SAMPLES_DIR`, hay thư mục chưa tạo → không mẫu nào (không lỗi)."""
    assert load_samples(None) == ([], [])
    assert load_samples(tmp_path / "chua-co") == ([], [])


def test_loads_responses_and_frames_in_path_order(tmp_path: Path) -> None:
    """Mẫu response và khung SSE tách hai danh sách; file tạm `.part` bị bỏ qua."""
    _write(tmp_path, "op_b/C01-1.json", {"operationId": "op_b", "status": 200, "body": None, "context": {"k": [1]}})
    _write(
        tmp_path, "op_a/C01-1.json", {"operationId": "op_a", "status": 200, "body": {"x": 1}, "pathParams": {"id": "1"}}
    )
    _write(tmp_path, "op_s/S03-event-1.json", {"operationId": "op_s", "case": "S03", "event": {"id": "u"}})
    (tmp_path / "op_a" / ".tam.part").write_text("{dở", encoding="utf-8")
    http, events = load_samples(tmp_path)
    assert http == [
        HttpSample("op_a/C01-1.json", "op_a", 200, {"x": 1}, {"id": "1"}, {}),
        HttpSample("op_b/C01-1.json", "op_b", 200, None, {}, {"k": [1]}),
    ]
    assert events == [EventSample("op_s/S03-event-1.json", "op_s", {"id": "u"})]


@pytest.mark.parametrize(
    "content",
    [
        "{không phải json",
        json.dumps({"operationId": "op"}),
        json.dumps(["mảng"]),
        json.dumps({"operationId": "op", "status": "abc", "body": None}),
    ],
    ids=["json hỏng", "thiếu khoá", "không phải object", "status sai kiểu"],
)
def test_broken_sample_is_an_error(tmp_path: Path, content: str) -> None:
    """Mẫu không đọc được → `SampleError` có tên file, bước 7 hỏng thay vì bỏ qua."""
    (tmp_path / "op").mkdir()
    (tmp_path / "op" / "C01-1.json").write_text(content, encoding="utf-8")
    with pytest.raises(SampleError, match=r"op/C01-1\.json"):
        load_samples(tmp_path)


def test_w3_accepts_three_digit_utc() -> None:
    """Đúng W3, chuỗi thường và ngày không giờ đều qua."""
    assert bad_datetimes({"a": "2026-01-01T00:00:00.000Z", "b": "Tầng 2026-01-01T", "c": "2026-01-01", "d": 5}) == []


@pytest.mark.parametrize(
    "value",
    ["2026-01-01T00:00:00.000000Z", "2026-01-01T07:00:00.000+07:00", "2026-01-01T00:00:00Z", "2026-01-01T00:00"],
)
def test_w3_rejects_other_datetime_forms_at_any_depth(value: str) -> None:
    """6 chữ số, lệch múi giờ, không phần nghìn → hỏng, kèm đường tới chuỗi."""
    assert bad_datetimes({"items": [{"at": "2026-01-01T00:00:00.000Z"}, {"at": value}]}) == [
        f"body.items[1].at = {value!r} không kết thúc .sssZ (W3)"
    ]
