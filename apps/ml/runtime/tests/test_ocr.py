"""Chữ kích thước của bản vẽ tổng hợp đọc được bằng OCR thật của wheel (`rapidocr_onnxruntime`).

Gọi `RapidOCR()` mặc định của wheel, **tắt** bộ phân loại góc ở lượt gọi: chữ trên bản
vẽ luôn thẳng trục, và bộ phân loại lật ngược chuỗi gần đối xứng (`8.000` → `000'8`). Đo
trên seed 100-109: bật phân loại 67/122, tắt 114/122 (2026-09-21).
"""

import logging

from rapidocr_onnxruntime import RapidOCR  # type: ignore[import-untyped]  # wheel không có py.typed

from packages.ml_contracts.synthetic import render_plan
from packages.testing.ocr_metrics import dimension_hits

_log = logging.getLogger(__name__)


def test_render_plan_ocr_readable() -> None:
    """≥ 80 % chữ kích thước trên seed 100-109 đọc ra đúng bằng đáp án, ở đúng chỗ."""
    engine = RapidOCR()
    hits = total = 0
    for seed in range(100, 110):
        plan = render_plan(seed)
        result, _elapsed = engine(plan.pixels, use_cls=False)
        found = []
        for box, text, _score in result or []:
            xs, ys = [point[0] for point in box], [point[1] for point in box]
            found.append(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, text))
        seed_hits, seed_total = dimension_hits(found, plan.texts)
        hits += seed_hits
        total += seed_total
    _log.info("ocr_dimension_hits=%d total=%d", hits, total)
    assert total >= 40
    assert hits >= 0.8 * total
