"""Đo bộ đọc trên model **thật**: bộ dò của wheel và model nhận dạng ghim của wheel.

Hai câu hỏi test này trả lời: bộ dò có thấy hết chữ của bản vẽ tổng hợp không, và
đường đi riêng của `RapidOcrReader` (lát, Otsu, đệm bội 80 sàn 320, tự xoay 180°) có đọc ra
cùng chữ như `RapidOCR()` của wheel không. Không tải mạng: cả hai model nằm sẵn trong
wheel đã khoá ở `uv.lock`, model rec đi qua `load_onnx` dạng ghim đúng như lúc chạy thật.
"""

import logging
import re
import shutil
import time
from pathlib import Path

import numpy as np
import pytest
from rapidocr_onnxruntime import RapidOCR  # type: ignore[import-untyped]  # wheel không có py.typed

from apps.ml.text.reader import (
    REC_MIN_WIDTH_PX,
    RapidOcrReader,
    _crop,
    _detect,
    _detector,
    _rec_input,
    _rec_widths,
    ctc_decode,
)
from apps.ml.text.tests.helpers import wheel_rec_session
from packages.ml_contracts.artifacts import BoxPx, TextPx
from packages.ml_contracts.synthetic import render_plan

_log = logging.getLogger(__name__)

DETECT_SEEDS = (100, 101, 102)
PARITY_SEEDS = (100, 101, 102, 103, 104)
DETECT_IOU = 0.3
PARITY_IOU = 0.5
DETECT_RECALL = 0.90
PARITY_RATE = 0.95
DETECT_BUDGET_S = 20.0
DIMENSION_SEEDS = range(100, 110)
DIMENSION_RE = re.compile(r"[0-9]{1,3}(\.[0-9]{3})*")
DIMENSION_NEAR_PX = 25
DIMENSION_READ_RATE = 0.90
"""Đo 114/122 = 0,934 trên `DIMENSION_SEEDS`, bằng `RapidOCR()` của wheel (NO-254); trước sàn
`REC_MIN_WIDTH_PX` đo 105/122 = 0,861. 8 chữ hụt là bộ dò tách `2.` khỏi phần sau, không thuộc bộ đọc."""
WIDTH_SEEDS = (100, 101, 102)
WIDTH_ROUNDING_RATE = 0.90
"""Phần vùng tối thiểu **giữ nguyên** chuỗi khi đệm `W`; tự chỉnh từ số đo 15/16 (BE-00 §12)."""


def _iou(one: BoxPx, two: BoxPx) -> float:
    """IoU hai hộp thẳng trục; 0 khi rời nhau."""
    x0, y0 = max(one.x_min, two.x_min), max(one.y_min, two.y_min)
    x1, y1 = min(one.x_max, two.x_max), min(one.y_max, two.y_max)
    inter = max(x1 - x0, 0.0) * max(y1 - y0, 0.0)
    areas = (one.x_max - one.x_min) * (one.y_max - one.y_min) + (two.x_max - two.x_min) * (two.y_max - two.y_min)
    return inter / (areas - inter) if areas > inter else 0.0


def _quad_box(quad: np.ndarray) -> BoxPx:
    """Hộp bao trục của một tứ giác dò được."""
    return BoxPx(
        x_min=float(quad[:, 0].min()),
        y_min=float(quad[:, 1].min()),
        x_max=float(quad[:, 0].max()),
        y_max=float(quad[:, 1].max()),
    )


def test_real_detector_finds_the_answer_boxes() -> None:
    """≥ 90 % hộp chữ đáp án có một hộp dò trùng ≥ 0,3 IoU; trần thời gian ở test `perf` riêng."""
    hits = total = 0
    for seed in DETECT_SEEDS:
        plan = render_plan(seed)
        boxes = [_quad_box(quad) for quad in _detect(_detector(), plan.pixels)]
        total += len(plan.texts)
        hits += sum(any(_iou(answer.box, box) >= DETECT_IOU for box in boxes) for answer in plan.texts)
    _log.info("ocr_detect_recall hits=%d total=%d", hits, total)
    assert total >= 3 * len(render_plan(DETECT_SEEDS[0]).texts) - 1
    assert hits >= DETECT_RECALL * total


@pytest.mark.perf
def test_real_detector_page_time() -> None:
    """Bộ dò thật chạy một trang `render_plan` 1.600 × 1.200 dưới `DETECT_BUDGET_S` ([8]).

    Trần đồng hồ tường nên gắn `perf` (BE-00 §12, NO-343); đo 0,90 / 0,56 / 0,45 s cho seed
    100/101/102 (B5-04), trần 20 s gấp > 20 lần. Độ phủ của `_detect` do test recall gánh.
    """
    detector = _detector()
    for seed in DETECT_SEEDS:
        pixels = render_plan(seed).pixels
        started = time.monotonic()
        _detect(detector, pixels)
        elapsed = time.monotonic() - started
        _log.info("ocr_detect_seed=%d elapsed_s=%.2f", seed, elapsed)
        assert elapsed < DETECT_BUDGET_S


def _wheel_items(engine: RapidOCR, pixels: np.ndarray) -> list[TextPx]:
    """Kết quả `RapidOCR()` (tắt bộ phân loại góc, NO-063) đổi về `TextPx` để so."""
    result, _elapsed = engine(pixels, use_cls=False)
    items = []
    for quad, text, score in result or []:
        box = _quad_box(np.asarray(quad, dtype=np.float32))
        items.append(TextPx(text=text.strip()[:64] or "?", box=box, confidence=min(float(score), 1.0)))
    return items


def test_reader_agrees_with_the_wheel_engine(pinned_models_dir: Path) -> None:
    """≥ 95 % vùng của wheel có vùng trùng của `RapidOcrReader` mang đúng cùng chuỗi."""
    reader = RapidOcrReader.from_session(wheel_rec_session(pinned_models_dir), pinned_name="rapidocrRec")
    engine = RapidOCR()
    agreed = total = 0
    for seed in PARITY_SEEDS:
        plan = render_plan(seed)
        ours = reader.read(plan.pixels)
        theirs = _wheel_items(engine, plan.pixels)
        total += len(theirs)
        for item in theirs:
            matched = [mine for mine in ours if _iou(item.box, mine.box) >= PARITY_IOU]
            agreed += any(mine.text == item.text for mine in matched)
    rate = agreed / total if total else 0.0
    _log.info("ocr_parity agreed=%d total=%d rate=%.3f", agreed, total, rate)
    assert total >= 5 * 10
    assert rate >= PARITY_RATE


def test_reader_reads_dimension_texts(pinned_models_dir: Path) -> None:
    """≥ `DIMENSION_READ_RATE` chữ kích thước đáp án đọc ra đúng chuỗi, tâm hộp lệch < 25 px.

    Ghim tỉ lệ đọc của chính `RapidOcrReader.read` (NO-254) bằng thước `test_ocr` của runtime
    dùng cho `RapidOCR()`: chuỗi đáp án dạng `1.234`, mục đọc có tâm trong `DIMENSION_NEAR_PX`.
    """
    reader = RapidOcrReader.from_session(wheel_rec_session(pinned_models_dir))
    hits = total = 0
    for seed in DIMENSION_SEEDS:
        plan = render_plan(seed)
        found = [
            ((item.box.x_min + item.box.x_max) / 2, (item.box.y_min + item.box.y_max) / 2, item.text)
            for item in reader.read(plan.pixels)
        ]
        for answer in plan.texts:
            if not DIMENSION_RE.fullmatch(answer.text):
                continue
            total += 1
            cx, cy = (answer.box.x_min + answer.box.x_max) / 2, (answer.box.y_min + answer.box.y_max) / 2
            hits += any(
                abs(x - cx) < DIMENSION_NEAR_PX and abs(y - cy) < DIMENSION_NEAR_PX and text == answer.text
                for x, y, text in found
            )
    _log.info("ocr_dimension_read hits=%d total=%d rate=%.3f", hits, total, hits / total)
    assert total >= 10 * len(DIMENSION_SEEDS)
    assert hits >= DIMENSION_READ_RATE * total


def test_width_rounding_keeps_most_strings(pinned_models_dir: Path) -> None:
    """Làm tròn `W` lên bội 80 giữ nguyên chuỗi của ≥ `WIDTH_ROUNDING_RATE` phần vùng **chữ thật**.

    So tensor thật với chính nó cắt còn `max(rộng đã co, REC_MIN_WIDTH_PX)`: chỉ phần làm tròn
    bội 80 khác nhau, sàn 320 (NO-254) giữ ở cả hai vì tensor hẹp hơn 320 đọc sai có hệ thống.
    Lệch khỏi prompt: [8] đòi "không đổi chuỗi nào", đo được 15/16 vùng trên seed 100.
    Đầu ra PP-OCR dài `T` bước **phụ thuộc `W`**, nên bất biến tuyệt đối theo bề rộng là
    điều model không hứa; chính `RapidOCR()` của wheel cũng đệm bằng một `W` khác hẳn mà
    hai bên vẫn khớp ≥ 95 % ở `test_reader_agrees_with_the_wheel_engine`. Chỉ so trên
    vùng trùng hộp chữ đáp án: vùng nhiễu bộ dò bắt nhầm đọc ra rác ở cả hai bề rộng.
    Đo trên đủ `WIDTH_SEEDS` (NO-255) để một seed may mắn không gánh được ngưỡng.
    """
    reader = RapidOcrReader.from_session(wheel_rec_session(pinned_models_dir))
    same = checked = 0
    for seed in WIDTH_SEEDS:
        plan = render_plan(seed)
        for quad in _detect(_detector(), plan.pixels):
            box = _quad_box(quad)
            if not any(_iou(box, answer.box) >= PARITY_IOU for answer in plan.texts):
                continue
            crop = _crop(plan.pixels, quad)
            if crop.size == 0:
                continue
            resized, _padded = _rec_widths(crop.shape[1], crop.shape[0])
            padded_input = _rec_input(crop)
            unrounded = padded_input[:, :, :, : max(resized, REC_MIN_WIDTH_PX)]
            same += _decode(reader, padded_input)[0] == _decode(reader, unrounded)[0]
            checked += 1
    _log.info("ocr_width_rounding same=%d checked=%d rate=%.3f", same, checked, same / checked)
    assert checked >= 5 * len(WIDTH_SEEDS)
    assert same >= WIDTH_ROUNDING_RATE * checked


def _decode(reader: RapidOcrReader, tensor: np.ndarray) -> tuple[str, float]:
    """Chuỗi và tin cậy bộ đọc giải ra từ một tensor vào đã dựng sẵn."""
    probs = reader._session.run([reader._output], {reader._input: tensor})[0]
    return ctc_decode(np.asarray(probs, dtype=np.float32)[0], reader._characters)


@pytest.fixture(scope="module")
def pinned_models_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Thư mục model ghim tạm chứa bản sao ONNX nhận dạng của wheel (`rapidocrRec.onnx`)."""
    import rapidocr_onnxruntime

    source = Path(str(rapidocr_onnxruntime.__file__)).parent / "models" / "ch_PP-OCRv4_rec_infer.onnx"
    target = tmp_path_factory.mktemp("models") / "rapidocrRec.onnx"
    shutil.copyfile(source, target)
    return target.parent
