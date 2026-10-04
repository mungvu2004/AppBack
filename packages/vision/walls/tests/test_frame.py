"""Ca "Khung" của B5-02 [8]: trang tổng hợp không có khung bản vẽ nên `find_frame` trả `None`.

Bản vẽ tổng hợp không vẽ khung quanh tường; nhận nhầm tường bao làm khung thì bước nắn
phối cảnh cắt mất mép nhà. Phủ seed 0-9 (có seed 7 của e2e B5-07) và mọi `EVAL_SET_SEEDS`.
"""

import pytest

from packages.ml_contracts.synthetic import EVAL_SET_SEEDS, render_plan
from packages.vision.preprocess.geometry import find_frame
from packages.vision.preprocess.types import RgbImage

_SEEDS = (*range(10), *EVAL_SET_SEEDS)


@pytest.mark.parametrize("seed", _SEEDS)
def test_find_frame__none_on_synthetic_page(seed: int) -> None:
    """`find_frame(RgbImage(render_plan(seed).pixels))` là `None` trên từng seed."""
    assert find_frame(RgbImage(render_plan(seed).pixels)) is None
