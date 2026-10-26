"""Trộn chuỗi kích thước của lượt pipeline vào danh sách hiện có (B3-06, H3 Phase 0).

Trước đây lượt chạy thay cả danh sách, kể cả `overrideValueMm` người nhập. Luật giữ
giống `merge_pipeline_result`: mục đã duyệt, do người vẽ, người đã sửa hoặc có giá trị
nhập tay thì còn nguyên; mục AI cũ còn lại nhường chỗ cho mục AI mới. Hàm thuần (K18):
không đồng hồ, không id mới.
"""

from collections.abc import Mapping, Sequence

from packages.domain.rules_ai.merge import _near
from packages.domain.spatial import Dimension, Segment


def _kept(dimension: Dimension) -> bool:
    """Mục người đã đụng tới hoặc tự vẽ: lượt pipeline không được thay."""
    return (
        dimension.reviewed or dimension.source == "human" or dimension.edited or dimension.override_value_mm is not None
    )


def _same_line(first: Segment, second: Segment) -> bool:
    """Hai đầu `line` cách hai đầu đoạn kia ≤ `MATCH_TOLERANCE_MM`, xét cả hai chiều."""
    return (_near(first.start, second.start) and _near(first.end, second.end)) or (
        _near(first.start, second.end) and _near(first.end, second.start)
    )


def merge_dimensions(
    current: Sequence[Dimension], ai: Sequence[Dimension], id_map: Mapping[str, str]
) -> tuple[Dimension, ...]:
    """Mục giữ của `current` (thứ tự cũ) rồi mục AI mới không trùng mục giữ nào.

    `reference_ids` của mục AI được ánh xạ qua `id_map` (id tường/phòng AI bị bỏ vì trùng
    → id mục được giữ) trước khi so. Trùng là: cùng tập `reference_ids` khác rỗng, hoặc
    `line` khớp hai đầu trong dung sai. Mục AI cũ không được giữ thì bị bỏ.
    """
    kept = tuple(dimension for dimension in current if _kept(dimension))
    kept_refs = {frozenset(dimension.reference_ids) for dimension in kept if dimension.reference_ids}
    added: list[Dimension] = []
    for dimension in ai:
        refs = tuple(id_map.get(ref, ref) for ref in dimension.reference_ids)
        if refs and frozenset(refs) in kept_refs:
            continue
        # ponytail: so `line` với mọi mục giữ (O(n·m)); số kích thước người giữ nhỏ, dựng lưới ô nếu chậm.
        if any(_same_line(dimension.line, other.line) for other in kept):
            continue
        added.append(dimension.model_copy(update={"reference_ids": refs}))
    return (*kept, *added)
