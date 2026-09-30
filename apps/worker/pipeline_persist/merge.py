"""Hàm trộn mà `write_layer` gọi dưới khoá tầng (B5-06b [6] "make_merge").

Lớp AI dựng ở tỉ lệ `s_ai`; tỉ lệ đang hiệu lực của tầng chỉ biết được **dưới khoá**, nên
`write_layer` truyền nó vào lúc gọi lại thay vì người gọi tự đọc trước (sẽ hở một đua #35).
Trộn chỉ xảy ra ở đây: gọi `merge_pipeline_result` ngoài `write_layer` là ghi lớp AI ngoài
hợp đồng (K21). `RescaleError` (một `ValueError`) nổi lên cho `service.py` đổi thành
`PIPELINE_RESULT_INVALID`.
"""

from collections.abc import Callable
from decimal import Decimal

from packages.domain.rules_ai.merge import MergeResult, merge_pipeline_result
from packages.domain.scale.rescale import rescale_unreviewed
from packages.domain.spatial.model import SpatialLayer


def make_merge(ai: SpatialLayer, s_ai: Decimal) -> Callable[[SpatialLayer, Decimal | None], MergeResult]:
    """Gói lớp AI và tỉ lệ dựng của nó thành hàm trộn cho `write_layer(merge=…)`."""

    def merge(base: SpatialLayer, target: Decimal | None) -> MergeResult:
        """Trộn lớp AI vào `base`; `target` là tỉ lệ tầng giữ, `None` = tỉ lệ AI thắng.

        `target is None` khi tầng chưa có tỉ lệ hạng cao hơn hoặc tỉ lệ cũ thuộc trang khác
        (HOP-DONG-MOI §4): không `rescale` gì cả. Còn lại đưa lớp AI về đúng `target` trước
        khi trộn, để mục người đã duyệt ở tỉ lệ đó không phải đổi (K21).
        """
        if target is None:
            return merge_pipeline_result(base, ai)
        return merge_pipeline_result(base, rescale_unreviewed(ai, float(s_ai), float(target)))

    return merge
