"""Artifact JSON của ba bước: khứ hồi, mỗi luật một ca hỏng, trần byte trước khi parse."""

from collections.abc import Callable
from typing import Any

import pytest
from pydantic import ValidationError

from packages.ml_contracts import artifacts
from packages.ml_contracts.artifacts import (
    ARTIFACT_JSON_MAX_BYTES,
    STEP_ARTIFACTS,
    BoxPx,
    DetectionPx,
    ObjectsResult,
    PointPx,
    TextPx,
    TextResult,
    WallPx,
    WallsResult,
    objects_from_json,
    objects_to_json,
    text_from_json,
    text_to_json,
    walls_from_json,
    walls_to_json,
)
from packages.ml_contracts.families import MODEL_FAMILIES

BOX = BoxPx(x_min=1, y_min=2, x_max=3.5, y_max=4)
WALL = WallPx(start=PointPx(x=0, y=0), end=PointPx(x=10, y=0), thickness_px=2.5, confidence=1)


def test_step_artifacts_cover_every_family() -> None:
    assert set(STEP_ARTIFACTS) == set(MODEL_FAMILIES)
    assert STEP_ARTIFACTS["wallSegmentation"] == ("walls.json", "walls.png")


def test_results_roundtrip_through_json() -> None:
    walls = WallsResult(walls=(WALL,))
    objects = ObjectsResult(detections=(DetectionPx(label="double_door", box=BOX, confidence=0.5),))
    texts = TextResult(items=(TextPx(text="3.600", box=BOX, confidence=0.25),))
    assert walls_from_json(walls_to_json(walls)) == walls
    assert objects_from_json(objects_to_json(objects)) == objects
    assert text_from_json(text_to_json(texts)) == texts
    assert b" " not in walls_to_json(walls)


@pytest.mark.parametrize(
    "build",
    [
        lambda: PointPx(x=-0.1, y=0),
        lambda: PointPx(x=100_000.1, y=0),
        lambda: PointPx(x=float("nan"), y=0),
        lambda: PointPx(x=float("inf"), y=0),
        lambda: BoxPx(x_min=3, y_min=0, x_max=3, y_max=1),
        lambda: BoxPx(x_min=0, y_min=2, x_max=1, y_max=1),
        lambda: WallPx(start=PointPx(x=1, y=1), end=PointPx(x=1, y=1), thickness_px=1, confidence=1),
        lambda: WallPx(start=PointPx(x=0, y=0), end=PointPx(x=1, y=0), thickness_px=0, confidence=1),
        lambda: WallPx(start=PointPx(x=0, y=0), end=PointPx(x=1, y=0), thickness_px=1, confidence=1.01),
        lambda: DetectionPx(label="sofa", box=BOX, confidence=0.5),
        lambda: DetectionPx(label="door", box=BOX, confidence=-0.01),
        lambda: TextPx(text="", box=BOX, confidence=1),
        lambda: TextPx(text="x" * 65, box=BOX, confidence=1),
        lambda: WallsResult(walls=(WALL,) * (artifacts.MAX_WALLS + 1)),
        lambda: ObjectsResult(detections=(DetectionPx(label="door", box=BOX, confidence=1),) * 5_001),
        lambda: TextResult(items=(TextPx(text="1", box=BOX, confidence=1),) * 5_001),
    ],
)
def test_artifact_rules_reject(build: Callable[[], Any]) -> None:
    with pytest.raises(ValidationError):
        build()


def test_artifact_bounds_accept_edges() -> None:
    PointPx(x=0, y=100_000)
    TextPx(text="x" * 64, box=BOX, confidence=0)
    WallsResult(walls=(WALL,) * artifacts.MAX_WALLS)


@pytest.mark.parametrize(
    ("parse", "data"),
    [
        (
            walls_from_json,
            b'{"schema_version":1,"walls":[{"start":{"x":0,"y":0,"z":1},"end":{"x":1,"y":0},'
            b'"thickness_px":1,"confidence":1}]}',
        ),
        (objects_from_json, b'{"schema_version":2,"detections":[]}'),
        (text_from_json, b'{"schema_version":1,"items":[],"extra":1}'),
        (text_from_json, b"not json"),
    ],
)
def test_from_json_rejects_contract_breaks(parse: Callable[[bytes], object], data: bytes) -> None:
    with pytest.raises(ValueError, match="validation error"):
        parse(data)


@pytest.mark.parametrize("parse", [walls_from_json, objects_from_json, text_from_json])
def test_from_json_rejects_oversize_before_parsing(parse: Callable[[bytes], object]) -> None:
    """Trần kiểm theo độ dài: thân quá trần hỏng dù là JSON hợp lệ (khoảng trắng)."""
    oversized = b" " * ARTIFACT_JSON_MAX_BYTES + b"{}"
    with pytest.raises(ValueError, match="trần"):
        parse(oversized)
