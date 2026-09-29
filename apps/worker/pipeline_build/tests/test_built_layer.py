"""`BuiltLayer.to_json`/`from_json` (B5-05 [2], "Dây"): khứ hồi đúng, byte tất định, khoá lạ → lỗi."""

import json
from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest

from apps.worker.pipeline_build.build import BuiltLayer
from apps.worker.pipeline_build.constants import DROPPED_KEYS
from packages.domain.spatial import Dimension, Point, Segment, SpatialLayer, Wall


def _built() -> BuiltLayer:
    """Một `BuiltLayer` nhỏ nhưng đủ hình dạng: một tường, một kích thước, `dropped` đủ khoá."""
    wall = Wall(
        id="W-0000000000000000000000001",
        level_id="L-0000000000000000000000001",
        centreline=Segment(start=Point(x=0, y=0), end=Point(x=5000, y=0)),
        thickness_mm=100,
        height_mm=3600,
        kind="partition",
        opening_ids=(),
        confidence=0.9,
        source="ai",
        reviewed=False,
    )
    dimension = Dimension(
        id="M-0000000000000000000000001",
        level_id=wall.level_id,
        kind="linear",
        reference_ids=(wall.id,),
        line=wall.centreline,
        value_mm=5000,
        confidence=0.7,
        source="ai",
        reviewed=False,
    )
    return BuiltLayer(
        layer=SpatialLayer(walls=(wall,), openings=(), rooms=(), furniture=()),
        dimensions=(dimension,),
        scale_mm_per_px=Decimal("5.000000"),
        scale_source="pipeline",
        dropped=dict.fromkeys(DROPPED_KEYS, 0),
    )


def test_built_layer__json_round_trip() -> None:
    """`from_json(b.to_json()) == b` (bất biến [6]) và byte lặp lại y hệt giữa hai lần gọi."""
    built = _built()
    assert BuiltLayer.from_json(built.to_json()) == built
    assert built.to_json() == built.to_json()


def test_built_layer__dropped_always_twelve_keys() -> None:
    """`dropped` ghi ra luôn đủ 12 khoá `DROPPED_KEYS`, đúng thứ tự dây."""
    payload = json.loads(_built().to_json())
    assert list(payload["dropped"]) == list(DROPPED_KEYS)
    assert payload["scaleMmPerPx"] == "5.000000"


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (lambda p: p.update(extra=1), "bộ khoá gốc"),
        (lambda p: p.pop("scaleSource"), "bộ khoá gốc"),
        (lambda p: p.update(schemaVersion=2), "schemaVersion"),
        (lambda p: p["dropped"].update(mystery=1), "bộ khoá dropped"),
        (lambda p: p["dropped"].pop("outOfImage"), "bộ khoá dropped"),
    ],
)
def test_built_layer__from_json_rejects(mutate: Callable[[dict[str, Any]], object], reason: str) -> None:
    """Mọi lệch bộ khoá hay số hiệu bản đều là `ValueError`, không đọc nửa vời."""
    payload = json.loads(_built().to_json())
    mutate(payload)
    with pytest.raises(ValueError, match=reason):
        BuiltLayer.from_json(json.dumps(payload).encode())


def test_built_layer__from_json_rejects_broken_json() -> None:
    """Byte không phải JSON → `ValueError` (task đổi thành `PIPELINE_ARTIFACT_INVALID`)."""
    with pytest.raises(ValueError, match="JSON"):
        BuiltLayer.from_json(b"{khong-phai-json")


def test_built_layer__from_json_rejects_unknown_scale_source() -> None:
    """`scaleSource` ngoài hai giá trị đã khai → `ValueError` (B5-06b đọc file này qua `from_json`)."""
    payload = json.loads(_built().to_json())
    payload["scaleSource"] = "banana"
    with pytest.raises(ValueError, match="scaleSource"):
        BuiltLayer.from_json(json.dumps(payload).encode())
