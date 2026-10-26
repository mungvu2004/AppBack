"""`merge_dimensions` (B3-06, H3 Phase 0): mục người đụng tới còn nguyên, mục AI thường được thay."""

from typing import Any

from packages.domain.rules_ai.dimensions import merge_dimensions
from packages.domain.rules_ai.tests.builders import LEVEL, eid, review, wid
from packages.domain.spatial import Dimension, Point, Segment


def _dim(
    number: int,
    start: tuple[int, int],
    end: tuple[int, int],
    *,
    refs: tuple[str, ...] = (),
    override: int | None = None,
    edited: bool = False,
    **flags: Any,
) -> Dimension:
    """Kích thước thẳng `M-T<number>` từ `start` tới `end`; `flags` đi vào `review`."""
    return Dimension(
        id=eid("M", number),
        level_id=LEVEL,
        kind="linear",
        reference_ids=refs,
        line=Segment(start=Point(x=start[0], y=start[1]), end=Point(x=end[0], y=end[1])),
        value_mm=max(abs(end[0] - start[0]), abs(end[1] - start[1])) or 1,
        override_value_mm=override,
        **review(edited=edited, **flags),
    )


def _ids(dimensions: tuple[Dimension, ...]) -> list[str]:
    """Id theo thứ tự kết quả."""
    return [dimension.id for dimension in dimensions]


def test_merge_dimensions_keeps_override() -> None:
    """Mục AI có `overrideValueMm` còn nguyên, giá trị nhập tay không mất."""
    overridden = _dim(1, (0, 0), (3000, 0), override=3050)

    merged = merge_dimensions([overridden], [], {})

    assert merged == (overridden,)


def test_merge_dimensions_keeps_human() -> None:
    """Mục người vẽ còn nguyên dù lượt AI không có mục nào giống."""
    drawn = _dim(1, (0, 0), (3000, 0), source="human")

    assert merge_dimensions([drawn], [_dim(2, (0, 5000), (4000, 5000))], {})[0] == drawn


def test_merge_dimensions_keeps_edited() -> None:
    """Mục AI người đã sửa (`edited`) mà chưa duyệt vẫn được giữ."""
    edited = _dim(1, (0, 0), (3000, 0), edited=True)

    assert _ids(merge_dimensions([edited], [], {})) == [eid("M", 1)]


def test_merge_dimensions_replaces_plain_ai() -> None:
    """Mục AI thường của lượt trước bị thay bằng mục của lượt mới."""
    old = _dim(1, (0, 0), (3000, 0))
    new = _dim(2, (0, 0), (3000, 0))

    assert merge_dimensions([old], [new], {}) == (new,)


def test_merge_dimensions_drops_new_ai_with_same_refs() -> None:
    """Mục AI mới cùng tập `referenceIds` (khác thứ tự) với mục giữ bị bỏ dù `line` ở xa."""
    kept = _dim(1, (0, 0), (3000, 0), refs=(wid(1), wid(2)), reviewed=True, source="human")
    twin = _dim(2, (0, 9000), (3000, 9000), refs=(wid(2), wid(1)))

    assert merge_dimensions([kept], [twin], {}) == (kept,)


def test_merge_dimensions_drops_new_ai_on_same_line() -> None:
    """Mục AI mới có hai đầu trong 50 mm (đảo chiều) của mục giữ bị bỏ; lệch 51 mm thì được thêm."""
    kept = _dim(1, (0, 0), (3000, 0), override=3010)
    reversed_twin = _dim(2, (3030, 40), (0, -30))
    beside = _dim(3, (0, 51), (3000, 51))

    assert _ids(merge_dimensions([kept], [reversed_twin, beside], {})) == [eid("M", 1), eid("M", 3)]


def test_merge_dimensions_maps_refs_through_id_map() -> None:
    """`reference_ids` AI đi qua `id_map` trước khi so và trong mục được thêm."""
    kept = _dim(1, (0, 0), (3000, 0), refs=(wid(1),), source="human")
    mapped_twin = _dim(2, (0, 9000), (3000, 9000), refs=(wid(7),))
    fresh = _dim(3, (0, 5000), (3000, 5000), refs=(wid(8), wid(9)))

    merged = merge_dimensions([kept], [mapped_twin, fresh], {wid(7): wid(1), wid(8): wid(2)})

    assert _ids(merged) == [eid("M", 1), eid("M", 3)]
    assert merged[1].reference_ids == (wid(2), wid(9))


def test_merge_dimensions_orders_kept_then_new_ai() -> None:
    """Thứ tự: mục giữ theo thứ tự cũ (bỏ mục AI cũ xen giữa), rồi mục AI mới theo thứ tự `ai`."""
    current = [
        _dim(1, (0, 0), (1000, 0), source="human"),
        _dim(2, (0, 2000), (1000, 2000)),
        _dim(3, (0, 4000), (1000, 4000), reviewed=True, source="human"),
    ]
    ai = [_dim(5, (0, 8000), (1000, 8000)), _dim(4, (0, 6000), (1000, 6000))]

    assert _ids(merge_dimensions(current, ai, {})) == [eid("M", n) for n in (1, 3, 5, 4)]
