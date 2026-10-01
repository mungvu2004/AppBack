"""Test thuần của `report.build_report`/`RunQualityReport.to_json_bytes` (B5-07 [8]).

Không DB, không kho: `build_report` chỉ nhận một `SpatialLayer` dựng tay trong bộ nhớ.
"""

import json
from decimal import Decimal

from apps.worker.pipeline_quality.report import build_report
from packages.domain.spatial.model import Opening, Point, Segment, SpatialLayer, Wall

_LEVEL = "L-LEVEL00000000001"
_AI = {"source": "ai", "reviewed": False}


def _wall(id_: str, *, confidence: float, extra: dict[str, object] | None = None) -> Wall:
    """Một tường tối thiểu hợp lệ, không ô mở, gắn `_LEVEL`."""
    return Wall(
        id=id_,
        level_id=_LEVEL,
        centreline=Segment(start=Point(x=0, y=0), end=Point(x=1000, y=0)),
        thickness_mm=100,
        height_mm=2500,
        kind="partition",
        opening_ids=(),
        confidence=confidence,
        **(extra or _AI),
    )


def test_build_report__ai_below_threshold_counts_as_low_confidence() -> None:
    """Ngưỡng 0,7: một tường AI chưa duyệt với `confidence < 0.7` → `lowConfidence.walls == 1`."""
    layer = SpatialLayer(walls=(_wall("W-WALL0000000001", confidence=0.5),), openings=(), rooms=(), furniture=())
    report = build_report(run_id="run_01", revision=1, layer=layer, level_id=_LEVEL, threshold=Decimal("0.7"))
    assert report.low_confidence == {"walls": 1, "openings": 0, "rooms": 0, "furniture": 0}


def test_build_report__confidence_equal_threshold_is_not_counted() -> None:
    """`confidence == threshold` không tính (luật ngặt `<`)."""
    layer = SpatialLayer(walls=(_wall("W-WALL0000000001", confidence=0.7),), openings=(), rooms=(), furniture=())
    report = build_report(run_id="run_01", revision=1, layer=layer, level_id=_LEVEL, threshold=Decimal("0.7"))
    assert report.low_confidence["walls"] == 0


def test_build_report__empty_layer_has_no_issues_and_zero_counts() -> None:
    """Lớp rỗng: không lỗi toàn vẹn, bốn khoá `lowConfidence` đều 0."""
    layer = SpatialLayer(walls=(), openings=(), rooms=(), furniture=())
    report = build_report(run_id="run_01", revision=1, layer=layer, level_id=_LEVEL, threshold=Decimal("0.7"))
    assert report.issues == ()
    assert report.low_confidence == {"walls": 0, "openings": 0, "rooms": 0, "furniture": 0}
    assert report.has_critical is False


def test_build_report__issue_order_preserved_and_ref_id_absent_on_wire() -> None:
    """Thứ tự `issues` giữ nguyên thứ tự `check_integrity`; `refId` vắng hẳn khoá khi `None`."""
    duplicated = _wall("W-WALL0000000001", confidence=0.9)
    layer = SpatialLayer(walls=(duplicated, duplicated), openings=(), rooms=(), furniture=())
    report = build_report(run_id="run_01", revision=1, layer=layer, level_id=_LEVEL, threshold=Decimal("0.7"))
    assert [issue.rule for issue in report.issues] == ["duplicateId", "duplicateId"]
    wire = json.loads(report.to_json_bytes())
    assert all("refId" not in item for item in wire["integrity"])


def test_build_report__to_json_bytes_is_deterministic_and_threshold_is_float() -> None:
    """Hai lần gọi cùng tài liệu ra cùng byte; `confidenceThreshold` là `float` trên dây."""
    layer = SpatialLayer(walls=(_wall("W-WALL0000000001", confidence=0.5),), openings=(), rooms=(), furniture=())
    report = build_report(run_id="run_01", revision=3, layer=layer, level_id=_LEVEL, threshold=Decimal("0.75"))
    first = report.to_json_bytes()
    second = report.to_json_bytes()
    assert first == second
    wire = json.loads(first)
    assert isinstance(wire["confidenceThreshold"], float)
    assert wire["confidenceThreshold"] == 0.75


def test_build_report__missing_reference_issue_marks_critical() -> None:
    """Ô mở trỏ tường không tồn tại → lỗi `critical`, `has_critical` true."""
    opening = Opening(
        id="D-OPEN000000000001",
        wall_id="W-NOPE000000000001",
        kind="door",
        offset_mm=0,
        width_mm=800,
        height_mm=2000,
        sill_height_mm=0,
        swing="left",
        confidence=0.9,
        **_AI,
    )
    layer = SpatialLayer(walls=(), openings=(opening,), rooms=(), furniture=())
    report = build_report(run_id="run_01", revision=1, layer=layer, level_id=_LEVEL, threshold=Decimal("0.7"))
    assert report.has_critical is True
    assert report.issues[0].rule == "missingReference"
