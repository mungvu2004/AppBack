"""Test lượt phóng thêm của `YoloOnnxDetector`: hệ số, đổi toạ độ, lọc chứa, giữ hộp gốc (B1 vật sót)."""

import numpy as np
import onnxruntime as ort  # type: ignore[import-untyped]  # onnxruntime 1.30 không có py.typed
import pytest
from numpy.typing import NDArray

from apps.ml.objects.detector import (
    CONTAIN_MAX,
    UPSCALE_FALLBACK,
    UPSCALE_MAX,
    YoloOnnxDetector,
    _add_new,
    _Candidates,
    _Detections,
    _to_page,
    merge_candidates,
    upscale_factor,
)
from apps.ml.objects.tests.onnx_models import make_const_yolo, yolo_output
from packages.ml_contracts.artifacts import MASK_MAX_PIXELS
from packages.ml_contracts.labels import DetectionLabel

_PAGE = 100_000


def _dets(rows: list[tuple[float, float, float, float, int]]) -> _Detections:
    """`_Detections` tay từ `(x1, y1, x2, y2, lớp)`, điểm 0,9."""
    arr = np.array(rows, dtype=np.float64).reshape(-1, 5)
    return _Detections(boxes=arr[:, :4], scores=np.full(len(rows), 0.9), classes=arr[:, 4].astype(np.int64))


@pytest.mark.parametrize(
    ("doors", "expected"),
    [
        ([], UPSCALE_FALLBACK),
        ([35.0], UPSCALE_FALLBACK),
        ([35.0, 35.0, 200.0], 2.0),
        ([10.0, 12.0], UPSCALE_MAX),
        ([100.0, 120.0], 1.0),
    ],
)
def test_upscale_factor__median_door_clamped_or_fallback(doors: list[float], expected: float) -> None:
    """`70 / trung vị cửa`, kẹp `[1, 2,6]`; < 2 cửa → 1,5."""
    assert upscale_factor(np.array(doors, dtype=np.float64), page_pixels=_PAGE) == pytest.approx(expected)


def test_upscale_factor__capped_by_page_pixel_limit() -> None:
    """Trang phóng không vượt `MASK_MAX_PIXELS`."""
    pixels = MASK_MAX_PIXELS // 2
    factor = upscale_factor(np.array([20.0, 20.0]), page_pixels=pixels)
    assert factor == pytest.approx(np.sqrt(2))


def test_to_page__divides_boxes_and_tiles_and_clips_to_page() -> None:
    """Hộp và lát của trang phóng 2x chia đôi; hộp tràn mép trang (do làm tròn) kẹp lại."""
    up = _Candidates(
        boxes=np.array([[20.0, 40.0, 60.0, 80.0], [150.0, 150.0, 201.0, 202.0]]),
        scores=np.array([0.9, 0.8]),
        classes=np.array([0, 1]),
        tiles=np.array([[0.0, 0.0, 128.0, 128.0], [72.0, 72.0, 128.0, 128.0]]),
    )
    page = _to_page(up, 2.0, 2.0, page_w=100, page_h=100)
    assert page.boxes.tolist() == [[10.0, 20.0, 30.0, 40.0], [75.0, 75.0, 100.0, 100.0]]
    assert page.tiles.tolist() == [[0.0, 0.0, 64.0, 64.0], [36.0, 36.0, 64.0, 64.0]]
    assert page.scores.tolist() == [0.9, 0.8]


def test_merge_candidates__mapped_tile_at_page_edge_is_not_a_cut() -> None:
    """Lát phóng đổi về gốc kết thúc ở `page_w` chỉ sai số làm tròn: hộp chạm mép trang không bị coi là mảnh."""
    right = 100.0 - 1e-12
    cands = _Candidates(
        boxes=np.array([[80.0, 10.0, right, 30.0], [60.0, 5.0, right, 40.0]]),
        scores=np.array([0.9, 0.95]),
        classes=np.array([0, 0]),
        tiles=np.array([[36.0, 0.0, 64.0 - 1e-12, 64.0], [36.0, 0.0, 64.0 - 1e-12, 64.0]]),
    )
    assert len(merge_candidates(cands, page_w=100, page_h=100)) == 2


def test_add_new__keeps_native_and_drops_contained_or_matching() -> None:
    """Hộp gốc giữ nguyên; bỏ hộp gộp trùng (IoU ≥ 0,3) hay nằm ≥ 60% trong hộp gốc; giữ hộp mới thật."""
    native = _dets([(0, 0, 100, 100, 0), (200, 200, 260, 260, 1)])
    inside = 0.95 * CONTAIN_MAX
    merged = _dets(
        [
            (2, 2, 98, 98, 0),  # bản phóng của hộp gốc → trùng
            (10, 10, 40, 40, 2),  # lồng trong sofa → bỏ
            (300, 300, 340, 340, 2),  # mới thật → giữ
            (100 - 40 * inside, 50, 100 + 40 * (1 - inside), 90, 2),  # < 60% trong hộp gốc → giữ
        ]
    )
    out = _add_new(native, merged, np.array([], dtype=np.int64))
    boxes = out.boxes.tolist()
    for kept in ([0.0, 0.0, 100.0, 100.0], [200.0, 200.0, 260.0, 260.0], [300.0, 300.0, 340.0, 340.0]):
        assert kept in boxes
    for dropped in ([2.0, 2.0, 98.0, 98.0], [10.0, 10.0, 40.0, 40.0]):
        assert dropped not in boxes
    assert len(out) == 4


def test_add_new__empty_native_keeps_all_merged() -> None:
    """Lượt gốc rỗng: mọi hộp gộp đều mới."""
    assert len(_add_new(_dets([]), _dets([(0, 0, 10, 10, 0)]), np.array([], dtype=np.int64))) == 1


def test_add_new__drops_new_boxes_of_skipped_class_only() -> None:
    """Hộp mới lớp bị loại (`other`) bỏ; hộp gốc cùng lớp vẫn giữ."""
    native = _dets([(0, 0, 50, 50, 3)])
    merged = _dets([(0, 0, 50, 50, 3), (100, 100, 150, 150, 3), (200, 200, 250, 250, 1)])
    out = _add_new(native, merged, np.array([3], dtype=np.int64))
    assert out.boxes.tolist() == [[0.0, 0.0, 50.0, 50.0], [200.0, 200.0, 250.0, 250.0]]


def _detector(output: NDArray[np.float32], labels: tuple[DetectionLabel, ...], *, multiscale: bool) -> YoloOnnxDetector:
    """Detector trên model hằng 128 px (mọi lát trả cùng hộp tương đối)."""
    data = make_const_yolo(output, input_shape=(1, 3, 128, 128))
    session = ort.InferenceSession(data, providers=["CPUExecutionProvider"])
    return YoloOnnxDetector(session, labels, multiscale=multiscale)


def test_detect__upscale_pass_adds_boxes_and_keeps_every_native_box() -> None:
    """Hai cửa 35 px → phóng 2x: có hộp mới, và mọi hộp lượt gốc vẫn còn y nguyên."""
    output = yolo_output([(20, 20, 35, 10, 0, 0.9), (20, 60, 35, 10, 0, 0.9), (100, 100, 20, 20, 1, 0.9)], nc=2)
    image = np.zeros((128, 128, 3), dtype=np.uint8)
    native = _detector(output, ("door", "bed"), multiscale=False).detect(image)
    multi = _detector(output, ("door", "bed"), multiscale=True).detect(image)
    assert len(multi) > len(native)
    assert all(d in multi for d in native)


def test_detect__large_doors_skip_upscale_pass() -> None:
    """Cửa 80 px → hệ số 1 < 1,2: không lượt phóng, kết quả như lượt gốc."""
    output = yolo_output([(50, 20, 80, 10, 0, 0.9), (50, 60, 80, 10, 0, 0.9)], nc=1)
    image = np.zeros((128, 128, 3), dtype=np.uint8)
    native = _detector(output, ("door",), multiscale=False).detect(image)
    assert _detector(output, ("door",), multiscale=True).detect(image) == native


def test_detect__model_without_door_label_skips_upscale_pass() -> None:
    """Model không có nhãn `door` không ước được cỡ vật: không phóng."""
    output = yolo_output([(40, 40, 20, 20, 0, 0.9)], nc=1)
    image = np.zeros((128, 128, 3), dtype=np.uint8)
    native = _detector(output, ("bed",), multiscale=False).detect(image)
    assert _detector(output, ("bed",), multiscale=True).detect(image) == native
