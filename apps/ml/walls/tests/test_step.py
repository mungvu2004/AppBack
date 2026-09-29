"""Lõi bước tách tường: chọn nhánh, kiểm khổ mặt nạ, trần `MAX_WALLS`, kẹp độ tin cổ điển.

Chạy `segment_page` trần — không kho, không broker, không vòng sự kiện — nên mỗi luật một
test ngắn. Bộ tách ONNX chạy `onnxruntime` **thật** trên model tí hon của `onnx_fixtures`;
chỉ hai chỗ thay bộ tách bằng một `WallSegmenter` dựng tay (mặt nạ sai khổ, mặt nạ nhiều
đoạn) vì không mặt nạ thật nào dựng được hai cảnh ấy — đó là fake ở đúng tầng cổng (K23).
"""

import asyncio
import logging

import numpy as np
import onnxruntime as ort  # type: ignore[import-untyped]  # onnxruntime 1.30 không có py.typed
import pytest
from numpy.typing import NDArray

from apps.ml.walls import step as step_module
from apps.ml.walls.step import CLASSIC_CONFIDENCE_CAP, segment_page, to_wall_px
from apps.ml.walls.tasks import MODEL_VERSION_FAMILY_MISMATCH, _prepare
from apps.ml.walls.tests.helpers import classic_ref, infer_payload, storage_ref
from apps.ml.walls.tests.onnx_fixtures import make_threshold_segformer
from packages.messaging.tasks import PermanentError
from packages.ml_contracts.artifacts import MAX_WALLS, decode_mask, walls_from_json
from packages.ml_contracts.synthetic import render_plan
from packages.vision.walls.types import WallSegment

PLAN = render_plan(101)
PAGE_H, PAGE_W = PLAN.walls_mask.shape


def walls_of(output: step_module.WallsStepOutput) -> tuple[object, ...]:
    """Các tường trong `walls.json` của một lượt chạy."""
    return walls_from_json(output.artifacts["walls.json"]).walls


class _FixedSegmenter:
    """`WallSegmenter` trả đúng một mặt nạ dựng sẵn, bất kể ảnh vào."""

    def __init__(self, mask: NDArray[np.bool_]) -> None:
        """`mask` là thứ `segment` trả về mỗi lần gọi."""
        self.mask = mask

    def segment(self, image: NDArray[np.uint8]) -> NDArray[np.bool_]:
        """Mặt nạ dựng sẵn; cố ý **không** theo khổ `image`."""
        return self.mask


def use_segmenter(monkeypatch: pytest.MonkeyPatch, mask: NDArray[np.bool_]) -> None:
    """Thay bộ tách của nhánh `fake` bằng một bộ trả `mask`."""
    monkeypatch.setattr(step_module, "FakeWallSegmenter", lambda: _FixedSegmenter(mask))


def test_segment_page_uses_the_fake_segmenter_on_fake_backend() -> None:
    """`ML_BACKEND=fake`: `used="fake"` và mặt nạ ghi ra là đúng đáp án của trang."""
    output = segment_page(PLAN.pixels, classic_ref(), backend="fake", session=None)
    assert output.used == "fake"
    mask = decode_mask(output.artifacts["walls.png"], width_px=PAGE_W, height_px=PAGE_H)
    assert np.array_equal(mask, PLAN.walls_mask)
    assert walls_of(output)


def test_segment_page_falls_back_to_classic_for_an_inactive_model() -> None:
    """`ModelRef` cổ điển ở backend `onnx`: `used="classic"` và vẫn thấy tường."""
    output = segment_page(PLAN.pixels, classic_ref(), backend="onnx", session=None)
    assert output.used == "classic"
    assert walls_of(output)


def test_segment_page_caps_confidence_on_the_classic_branch() -> None:
    """Đường lùi hình thái không được trông chắc bằng model: mọi `confidence` ≤ 0,5."""
    output = segment_page(PLAN.pixels, classic_ref(), backend="onnx", session=None)
    walls = walls_from_json(output.artifacts["walls.json"]).walls
    assert walls
    assert max(wall.confidence for wall in walls) <= CLASSIC_CONFIDENCE_CAP


def test_segment_page_runs_onnx_when_the_model_is_pinned_to_a_version() -> None:
    """`ModelRef` dạng storage: nhánh ONNX chạy thật trên phiên đã nạp, `used="onnx"`."""
    data = make_threshold_segformer()
    ref, _ = storage_ref(data)
    session = ort.InferenceSession(data, providers=["CPUExecutionProvider"])
    output = segment_page(PLAN.pixels, ref, backend="onnx", session=session)
    assert output.used == "onnx"
    mask = decode_mask(output.artifacts["walls.png"], width_px=PAGE_W, height_px=PAGE_H)
    assert mask.shape == (PAGE_H, PAGE_W)


def test_segment_page_rejects_a_mask_of_another_size(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mặt nạ khác khổ ảnh là model sai hợp đồng → `MODEL_FORMAT_UNSUPPORTED`."""
    use_segmenter(monkeypatch, np.zeros((PAGE_H // 2, PAGE_W), dtype=np.bool_))
    with pytest.raises(PermanentError) as caught:
        segment_page(PLAN.pixels, classic_ref(), backend="fake", session=None)
    assert caught.value.code == "MODEL_FORMAT_UNSUPPORTED"


def bar_grid(bands: int, columns: int) -> NDArray[np.bool_]:
    """Lưới `bands x columns` thanh ngang 15 x 3 px, rời nhau — không vòng theo điểm ảnh."""
    rows = np.arange(bands * 6) % 6 < 3
    cols = np.arange(columns * 19) % 19 < 15
    return np.logical_and(rows[:, None], cols[None, :])


def test_segment_page_keeps_the_longest_walls_over_the_contract_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Quá `MAX_WALLS` đoạn: giữ đúng trần và đếm phần bỏ vào `dropped["cap"]`."""
    mask = bar_grid(141, 150)
    use_segmenter(monkeypatch, mask)
    image = np.zeros((*mask.shape, 3), dtype=np.uint8)
    output = segment_page(image, classic_ref(), backend="fake", session=None)
    assert output.dropped["cap"] > 0
    assert len(walls_of(output)) == MAX_WALLS


def test_segment_page_counts_no_cap_when_under_the_limit() -> None:
    """Trang thường: `dropped` có khoá `cap` bằng 0, không phải thiếu khoá."""
    output = segment_page(PLAN.pixels, classic_ref(), backend="fake", session=None)
    assert output.dropped["cap"] == 0


def test_segment_page_logs_no_object_key(caplog: pytest.LogCaptureFixture) -> None:
    """Bản ghi `walls_segmented` mang số đo, **không** mang khoá object hay đường tệp."""
    caplog.set_level(logging.INFO, logger="apps.ml.walls.step")
    payload = infer_payload(width=PAGE_W, height=PAGE_H, model_ref=classic_ref())
    segment_page(PLAN.pixels, classic_ref(), backend="fake", session=None, run_id=payload.run_id)
    (record,) = [item for item in caplog.records if item.message == "walls_segmented"]
    assert record.__dict__["run_id"] == payload.run_id
    assert record.__dict__["used"] == "fake"
    assert {"mask_ms", "vectorize_ms", "encode_ms", "dropped", "walls"} <= set(record.__dict__)
    assert not {"page_key", "artifact_prefix"} & set(record.__dict__)


def test_to_wall_px_keeps_every_number() -> None:
    """Đổi kiểu sang hợp đồng không tính lại số nào (nếu không, J06 hỏng)."""
    seg = WallSegment((1.25, 2.5), (30.75, 2.5), 12.5, 0.875)
    wall = to_wall_px(seg)
    assert (wall.start.x, wall.start.y) == seg.start
    assert (wall.end.x, wall.end.y) == seg.end
    assert (wall.thickness_px, wall.confidence) == (seg.thickness_px, seg.confidence)


def test_prepare_rejects_a_payload_of_another_family() -> None:
    """Payload bước khác hỏng ngay ở `prepare`, trước khi đọc trang → không chạm kho."""
    payload = infer_payload(width=PAGE_W, height=PAGE_H, step="dimensionReading")
    with pytest.raises(PermanentError) as caught:
        asyncio.run(_prepare(payload))
    assert caught.value.code == MODEL_VERSION_FAMILY_MISMATCH
