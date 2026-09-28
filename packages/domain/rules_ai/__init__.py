"""Luật hậu xử lý AI và trộn kết quả pipeline (B3-06): gói miền thuần, không DB, mạng, tệp.

`apply_post_rules` sửa hai lỗi AI hay mắc (thiết bị áp tường đứng cách tường, cửa sổ trên
tường không phải tường bao); `merge_pipeline_result` trộn kết quả vào lớp hiện có mà không
bao giờ sửa hay xoá mục `reviewed=True` (K21). Chỉ đổi mục `source="ai"` chưa duyệt; không
đặt `reviewed`, không tạo id, không đoán tỉ lệ (K19). Lỗi tiền điều kiện là `ValueError`.
"""

from packages.domain.rules_ai.constants import (
    EXTERIOR_PROBE_MM,
    FIXTURE_SNAP_REACH_MM,
    LOW_CONFIDENCE_CAP,
    MATCH_TOLERANCE_MM,
    WALL_HUGGING_KINDS,
    WALL_HUGGING_TOLERANCE_MM,
)
from packages.domain.rules_ai.geometry import gap_to_wall_face, outline_contains, wall_side
from packages.domain.rules_ai.merge import MergeResult, merge_pipeline_result
from packages.domain.rules_ai.post_rules import apply_post_rules

__all__ = [
    "EXTERIOR_PROBE_MM",
    "FIXTURE_SNAP_REACH_MM",
    "LOW_CONFIDENCE_CAP",
    "MATCH_TOLERANCE_MM",
    "WALL_HUGGING_KINDS",
    "WALL_HUGGING_TOLERANCE_MM",
    "MergeResult",
    "apply_post_rules",
    "gap_to_wall_face",
    "merge_pipeline_result",
    "outline_contains",
    "wall_side",
]
