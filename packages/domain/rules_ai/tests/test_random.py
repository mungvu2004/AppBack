"""Ngẫu nhiên có hạt giống (BE-00 §9): 200 hạt giống, bốn bất biến của trộn, luật và trộn bằng bản tham chiếu."""

import logging
from collections import Counter
from typing import Final

from packages.domain.rules_ai import apply_post_rules, merge_pipeline_result
from packages.domain.rules_ai.tests.generators import Pair, random_pair, shares_ids
from packages.domain.rules_ai.tests.reference import ref_apply_post_rules, ref_merge
from packages.domain.spatial import SpatialLayer, ai_reviewed_ids, check_integrity, has_critical

_LOG = logging.getLogger(__name__)

SEEDS: Final = range(200)


def _check_rules(source: SpatialLayer, tally: Counter[str]) -> None:
    """`apply_post_rules` bằng bản quét hết, idempotent, và mục đã duyệt/người vẽ đi ra bằng hệt (K21)."""
    result = apply_post_rules(source)
    assert result == ref_apply_post_rules(source), "luật khác bản tham chiếu quét hết"
    tally["rules_equal_reference"] += 1
    assert apply_post_rules(result) == result, "luật không idempotent"
    tally["rules_idempotent"] += 1
    for before, after in zip(source.entities(), result.entities(), strict=True):
        assert before.id == after.id
        if before.reviewed or before.source == "human":
            assert before == after, f"luật đụng mục đã duyệt/người vẽ {before.id}"
    tally["rules_protect_reviewed"] += 1
    tally["rules_changed_something"] += result != source


def _check_merge(pair: Pair, tally: Counter[str]) -> None:
    """Bốn bất biến của [6] và `layer`, `id_map`, `dropped_ai_ids` bằng bản tham chiếu so mọi cặp."""
    current, ai = pair.current, pair.ai
    assert ai_reviewed_ids(current) == ()
    assert ai_reviewed_ids(ai) == ()
    assert not has_critical(check_integrity(current))
    assert not has_critical(check_integrity(ai))
    tally["generator_valid"] += 1
    result = merge_pipeline_result(current, ai)
    layer, dropped, id_map = ref_merge(current, ai)
    assert (result.layer, result.dropped_ai_ids, dict(result.id_map)) == (layer, dropped, id_map), "khác tham chiếu"
    tally["merge_equal_reference"] += 1
    kept = result.layer.entities()
    assert all(entity in kept for entity in current.entities() if entity.reviewed), "mục đã duyệt bị mất/sửa"
    tally["invariant_reviewed_intact"] += 1
    assert ai_reviewed_ids(result.layer) == (), "kết quả có mục ai + reviewed"
    tally["invariant_no_ai_reviewed"] += 1
    assert not has_critical(check_integrity(result.layer)), "kết quả có lỗi critical"
    tally["invariant_no_critical"] += 1
    assert merge_pipeline_result(result.layer, ai).layer == result.layer, "trộn lần hai đổi lớp"
    tally["invariant_idempotent"] += 1
    tally["merge_dropped_something"] += bool(result.dropped_ai_ids)
    tally["merge_mapped_ids"] += bool(result.id_map)


def test_random_pairs__invariants_and_reference_equality() -> None:
    """200 hạt giống: mỗi bất biến được kiểm 200 lần; hỏng thì thông báo mang hạt giống. In số lần bằng logging."""
    tally: Counter[str] = Counter()
    shared_seeds = 0
    for seed in SEEDS:
        pair = random_pair(seed)
        shared_seeds += pair.shared_ids
        try:
            _check_merge(pair, tally)
            _check_rules(pair.current, tally)
            _check_rules(pair.ai, tally)
        except AssertionError as error:
            error.add_note(f"hạt giống hỏng: seed={seed}")
            raise
    _LOG.info(
        "hạt giống đã chạy: %d, dùng chung id: %d, số lần kiểm mỗi bất biến: %s", len(SEEDS), shared_seeds, dict(tally)
    )
    for name in ("generator_valid", "merge_equal_reference", "invariant_reviewed_intact", "invariant_no_ai_reviewed"):
        assert tally[name] == len(SEEDS), name
    assert tally["invariant_no_critical"] == tally["invariant_idempotent"] == len(SEEDS)
    assert tally["rules_equal_reference"] == tally["rules_idempotent"] == 2 * len(SEEDS)
    # Bộ sinh phải thật sự đụng tới hai luật và cả nhánh bỏ/ánh xạ, không chỉ chạy suông.
    assert tally["rules_changed_something"] > len(SEEDS) // 2
    assert tally["merge_dropped_something"] > len(SEEDS) // 2
    assert tally["merge_mapped_ids"] > len(SEEDS) // 2


def test_generator__shares_ids_in_at_least_a_fifth_of_the_seeds_and_is_deterministic() -> None:
    """≥ 20 % hạt giống có id cùng loại chung giữa `current` và `ai`; cùng hạt giống cho cùng cặp."""
    shared = [seed for seed in SEEDS if shares_ids(seed)]
    assert len(shared) >= len(SEEDS) / 5
    for seed in shared:
        pair = random_pair(seed)
        ids = {e.id for e in pair.current.entities()} & {e.id for e in pair.ai.entities()}
        assert ids, f"seed={seed}: không id nào dùng chung"
    assert random_pair(7) == random_pair(7)
