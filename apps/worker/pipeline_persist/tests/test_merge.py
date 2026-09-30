"""`make_merge` tách khỏi DB (B5-06b [6] "make_merge", [8] "Tỉ lệ").

Hàm trộn chỉ được `write_layer` gọi dưới khoá, nên nhánh `target is None` không tới được qua
đường thật; ở đây gọi thẳng để cả hai nhánh có test. Không cần Postgres: đây là logic thuần.
"""

from decimal import Decimal
from typing import Final

from apps.worker.pipeline_persist.merge import make_merge
from apps.worker.pipeline_persist.tests.helpers import ai_layer
from packages.domain.rules_ai.merge import merge_pipeline_result
from packages.domain.spatial.model import SpatialLayer

LEVEL_ID: Final = "L-MERGE00000"
"""Tầng giả lập cho cả hai lớp; `merge_pipeline_result` từ chối hai lớp khác tầng."""


def _layers() -> tuple[SpatialLayer, SpatialLayer]:
    """Nền rỗng và lớp AI của cùng một tầng: mọi mục AI sống sót nên so sánh được từng trường."""
    return SpatialLayer(walls=(), openings=(), rooms=(), furniture=()), ai_layer(LEVEL_ID)


def test_make_merge_passes_ai_unchanged_when_target_is_none() -> None:
    """`target is None` → `merge_pipeline_result` nhận đúng lớp AI, không qua `rescale`."""
    base, ai = _layers()

    got = make_merge(ai, Decimal("12"))(base, None)

    assert got.layer == merge_pipeline_result(base, ai).layer


def test_make_merge_rescales_ai_to_target_scale() -> None:
    """`target` khác tỉ lệ dựng → lớp AI về đúng `target` trước khi trộn (tường co lại)."""
    base, ai = _layers()

    at_twelve = make_merge(ai, Decimal("12"))(base, Decimal("12"))
    at_six = make_merge(ai, Decimal("12"))(base, Decimal("6"))

    assert at_six.layer != at_twelve.layer
    assert len(at_six.layer.walls) == len(at_twelve.layer.walls)
