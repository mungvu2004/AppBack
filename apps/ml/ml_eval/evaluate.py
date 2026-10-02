"""`evaluate_family`: Chữ ký chung render→load_raster→adapter→số đo→làm tròn (khối [6]).

Gọi `synthetic.render_plan` qua thuộc tính module để spy M06 vá được
(`packages.ml_contracts.synthetic.render_plan`). Làm tròn ở một chỗ duy nhất (`js_round`);
lỗi adapter (`PermanentError`) đi thẳng ra, không bắt. Không ngẫu nhiên, không thời gian.
"""

from collections.abc import Sequence
from typing import cast

from apps.ml.ml_eval.metrics import cer, map50, mask_iou
from packages.domain.spatial.area import js_round
from packages.ml_contracts import synthetic
from packages.ml_contracts.families import FAMILY_METRIC, ModelFamily
from packages.ml_contracts.ports import ObjectDetector, TextReader, WallSegmenter
from packages.ml_contracts.synthetic import EVAL_SET_SEEDS
from packages.vision.preprocess import DEFAULT_MAX_PIXELS, load_raster

type Adapter = WallSegmenter | ObjectDetector | TextReader

__all__ = ["Adapter", "evaluate_family"]


def evaluate_family(
    family: ModelFamily, adapter: Adapter, *, seeds: Sequence[int] = EVAL_SET_SEEDS
) -> dict[str, float]:
    """Chạy `adapter` trên `seeds` tổng hợp theo thứ tự, trả dict đúng một khoá `FAMILY_METRIC[family]`."""
    wall_pairs = []
    det_pairs = []
    text_pairs = []
    for seed in seeds:
        plan = synthetic.render_plan(seed)
        image = load_raster(plan.image_png, max_pixels=DEFAULT_MAX_PIXELS).pixels
        if family == "wallSegmentation":
            wall_pairs.append((cast(WallSegmenter, adapter).segment(image), plan.walls_mask))
        elif family == "openingAndFurnitureDetection":
            det_pairs.append((cast(ObjectDetector, adapter).detect(image), plan.detections))
        else:
            text_pairs.append((cast(TextReader, adapter).read(image), plan.texts))
    if family == "wallSegmentation":
        value = mask_iou(wall_pairs)
    elif family == "openingAndFurnitureDetection":
        value = map50(det_pairs)
    else:
        value = cer(text_pairs)
    return {FAMILY_METRIC[family]: js_round(value * 1e6) / 1e6}
