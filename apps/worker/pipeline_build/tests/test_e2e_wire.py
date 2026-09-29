"""Test đầu-cuối `build_layer` trên bộ đáp án tổng hợp: dây hợp đồng và tính tất định (B5-05 việc E).

Không đọc DB, không nhập `apps.ml.*`; chỉ dùng `render_plan` (packages/ml_contracts/synthetic.py) làm đầu vào giả.
"""

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Final

import pytest

from apps.worker.pipeline_build.build import BuiltLayer, build_layer
from apps.worker.pipeline_build.ids import new_spatial_id
from packages.domain.spatial import ai_reviewed_ids
from packages.domain.spatial.integrity import check_integrity, has_critical
from packages.domain.spatial.model import SpatialLayer
from packages.ml_contracts.artifacts import ObjectsResult, TextResult, WallsResult
from packages.ml_contracts.synthetic import EVAL_SET_SEEDS, render_plan
from packages.testing.fixtures.clock import FakeClock

_FALLBACK_MM_PER_PX = Decimal("10")
_LEVEL_ID: Final = new_spatial_id("level", FakeClock(start=datetime(2026, 1, 1, tzinfo=UTC)))
"""Id tầng hợp mẫu W4 (`LevelIdStr`); test cần id thật, không phải chuỗi tuỳ ý."""


def _build_from_seed(seed: int, clock: FakeClock) -> BuiltLayer:
    """Dựng `BuiltLayer` từ đáp án tổng hợp `seed`, đầu vào đổi thẳng sang các `*Result`."""
    plan = render_plan(seed)
    return build_layer(
        level_id=_LEVEL_ID,
        walls=WallsResult(walls=plan.walls),
        objects=ObjectsResult(detections=plan.detections),
        text=TextResult(items=plan.texts),
        width_px=plan.pixels.shape[1],
        height_px=plan.pixels.shape[0],
        fallback_mm_per_px=_FALLBACK_MM_PER_PX,
        clock=clock,
    )


@pytest.mark.parametrize("seed", list(EVAL_SET_SEEDS))
def test_build_layer__wire_no_critical_issue(seed: int, fake_clock: FakeClock) -> None:
    """Mỗi hạt của `EVAL_SET_SEEDS`: không có vấn đề nghiêm trọng, có ít nhất 2 phòng."""
    built = _build_from_seed(seed, fake_clock)
    issues = check_integrity(built.layer, level_id=_LEVEL_ID)
    assert not has_critical(issues), f"seed {seed}: {issues}"
    assert len(built.layer.rooms) >= 2, f"seed {seed}: {len(built.layer.rooms)} phòng"


@pytest.mark.parametrize("seed", list(EVAL_SET_SEEDS))
def test_build_layer__wire_round_trips_spatial_layer(seed: int, fake_clock: FakeClock) -> None:
    """`to_json()` sinh JSON mà `SpatialLayer.model_validate` đọc lại đạt; `areaM2` là số JSON thật."""
    built = _build_from_seed(seed, fake_clock)
    payload = json.loads(built.to_json())
    layer_dump = payload["layer"]
    SpatialLayer.model_validate(layer_dump)
    for room in layer_dump["rooms"]:
        assert isinstance(room["areaM2"], float), f"seed {seed}: areaM2 không phải float JSON"


def _remap_ids(payload: dict[str, Any]) -> dict[str, Any]:
    """Đổi mọi id trong `payload` (JSON `to_json()` camelCase) sang `"<loại>#<n>"` theo thứ tự xuất hiện.

    Ánh xạ được áp cho `id`, `wallId`, `openingIds`, `wallIds`, `roomId`, `referenceIds` của
    `layer.{walls,openings,rooms,furniture}` và `dimensions` để so sánh hai lượt dựng bất kể id
    ULID ngẫu nhiên (thời gian, ngẫu nhiên riêng của `new_spatial_id`). Kiểu `Any`: JSON lồng nhau
    động, không đáng mô hình hoá riêng cho một hàm so sánh trong test.
    """
    layer_dump = payload["layer"]
    mapping: dict[str, str] = {}
    counters: dict[str, int] = {}

    def _alloc(kind: str, entity_id: str) -> str:
        """Gán (hoặc lấy lại) nhãn `"<kind>#<n>"` cho `entity_id`, `n` tăng theo thứ tự gặp."""
        if entity_id not in mapping:
            counters[kind] = counters.get(kind, 0) + 1
            mapping[entity_id] = f"{kind}#{counters[kind]}"
        return mapping[entity_id]

    for wall in layer_dump["walls"]:
        _alloc("wall", wall["id"])
    for opening in layer_dump["openings"]:
        _alloc("opening", opening["id"])
    for room in layer_dump["rooms"]:
        _alloc("room", room["id"])
    for furniture in layer_dump["furniture"]:
        _alloc("furniture", furniture["id"])
    for dimension in payload["dimensions"]:
        _alloc("dimension", dimension["id"])

    def _remapped(value: str) -> str:
        """Tra id ULID ra nhãn đã gán; id lạ (ngoài bốn danh sách) giữ nguyên."""
        return mapping.get(value, value)

    return {
        "walls": [
            {**w, "id": _remapped(w["id"]), "openingIds": [_remapped(o) for o in w["openingIds"]]}
            for w in layer_dump["walls"]
        ],
        "openings": [{**o, "id": _remapped(o["id"]), "wallId": _remapped(o["wallId"])} for o in layer_dump["openings"]],
        "rooms": [
            {**r, "id": _remapped(r["id"]), "wallIds": [_remapped(w) for w in r["wallIds"]]}
            for r in layer_dump["rooms"]
        ],
        "furniture": [
            {
                **f,
                "id": _remapped(f["id"]),
                "roomId": _remapped(f["roomId"]) if f.get("roomId") is not None else None,
            }
            for f in layer_dump["furniture"]
        ],
        "dimensions": [
            {**d, "id": _remapped(d["id"]), "referenceIds": [_remapped(r) for r in d["referenceIds"]]}
            for d in payload["dimensions"]
        ],
    }


def test_build_layer__deterministic_after_id_remap(fake_clock: FakeClock) -> None:
    """Hai lượt dựng cùng đầu vào (seed 100): bằng nhau sau khi thay id ULID bằng số thứ tự theo loại."""
    seed = next(iter(EVAL_SET_SEEDS))
    first = json.loads(_build_from_seed(seed, FakeClock(start=fake_clock.now())).to_json())
    second = json.loads(_build_from_seed(seed, FakeClock(start=fake_clock.now())).to_json())
    assert _remap_ids(first) == _remap_ids(second)


@pytest.mark.parametrize("seed", [100, 101, 102])
def test_build_layer__no_ai_reviewed_ids(seed: int, fake_clock: FakeClock) -> None:
    """`ai_reviewed_ids` rỗng: đầu ra AI thuần không có thực thể `reviewed=True` sai luật (A5)."""
    built = _build_from_seed(seed, fake_clock)
    assert ai_reviewed_ids(built.layer) == ()


def _millimetre_values(node: Any, path: str = "") -> list[tuple[str, Any]]:
    """Mọi cặp `(đường dẫn, giá trị)` của khoá đo bằng mm: `…Mm`, `x`, `y` (bất biến [6])."""
    if isinstance(node, dict):
        found: list[tuple[str, Any]] = []
        for key, value in node.items():
            here = f"{path}.{key}"
            if key.endswith("Mm") or key in {"x", "y"}:
                found.append((here, value))
            else:
                found += _millimetre_values(value, here)
        return found
    if isinstance(node, list):
        return [pair for i, item in enumerate(node) for pair in _millimetre_values(item, f"{path}[{i}]")]
    return []


def test_build_layer__every_millimetre_is_int(fake_clock: FakeClock) -> None:
    """Bất biến [6] "mọi mm là `int`": duyệt cả `layer` lẫn `dimensions` của seed 100 sau `to_json`."""
    payload = json.loads(_build_from_seed(100, fake_clock).to_json())
    values = _millimetre_values(payload["layer"]) + _millimetre_values(payload["dimensions"])
    assert values, "không tìm thấy khoá mm nào — bài test mất ý nghĩa"
    wrong = [(path, value) for path, value in values if not isinstance(value, int) or isinstance(value, bool)]
    assert wrong == [], f"khoá mm không phải int: {wrong[:5]}"
