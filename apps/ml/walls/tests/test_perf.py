"""Trần thời gian của nhánh cổ điển trên trang lớn nhất hợp đồng cho phép (K28, BE-00 §12).

7745 x 5164 = 39.995.180 điểm, sát `MASK_MAX_PIXELS`. Trần là đồng hồ tường nên test mang
marker `perf` và chạy riêng; mọi đường mã ở đây đã có test không-`perf` trong `test_step.py`
gánh phần độ phủ. Số đo in bằng `logging` (không `print`), kèm thời gian từng bước mà
`segment_page` tự ghi, để lượt cổng nào chậm cũng chỉ ra được bước nào chậm.
"""

import logging
import time
from typing import Final

import pytest

from apps.ml.walls.step import segment_page
from apps.ml.walls.tests.helpers import classic_ref
from packages.ml_contracts.artifacts import walls_from_json
from packages.ml_contracts.synthetic import render_plan

_log: Final = logging.getLogger(__name__)

BUDGET_S: Final = 30.0
BIG_W, BIG_H = 7745, 5164


@pytest.mark.perf
def test_segment_page_classic_stays_within_budget(caplog: pytest.LogCaptureFixture) -> None:
    """Nhánh cổ điển trên trang 7745 x 5164, sau một lượt khởi động, dưới 30 giây."""
    segment_page(render_plan(101).pixels, classic_ref(), backend="onnx", session=None)
    plan = render_plan(101, width_px=BIG_W, height_px=BIG_H)
    caplog.set_level(logging.INFO, logger="apps.ml.walls.step")
    started = time.monotonic()
    output = segment_page(plan.pixels, classic_ref(), backend="onnx", session=None)
    elapsed = time.monotonic() - started
    record = [item for item in caplog.records if item.message == "walls_segmented"][-1]
    steps = {key: record.__dict__[key] for key in ("mask_ms", "vectorize_ms", "encode_ms")}
    walls = walls_from_json(output.artifacts["walls.json"]).walls
    _log.info("perf walls classic %dx%d: %.2fs tổng, %s, %d tường", BIG_W, BIG_H, elapsed, steps, len(walls))
    assert elapsed < BUDGET_S
