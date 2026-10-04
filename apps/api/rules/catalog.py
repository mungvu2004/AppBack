"""Danh mục luật (B3-05 [2]): 25 mã luật và 26 khoá ngưỡng, gương của AppFront.

Chỉ thư viện chuẩn — không nhập `fastapi`, `sqlalchemy` — để H4 (`tools.contract.check`) nhập được ngoài
app. H4 đọc đúng hai hằng `RULE_CODES` và `THRESHOLD_SPECS`; đổi tên chúng là hỏng cổng. Mỗi dòng dưới đây
dẫn dòng FE mà nó chép (`F:/App/AppFront/src/domain/rules/...`). Không thêm mã ngoài FE (kế hoạch P9: v2);
thu hẹp danh mục sau khi có dữ liệu là việc của FIX (FIX.md luật 8).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

GENERAL_CODE: Final = "GENERAL"
"""Mã giữ ngưỡng dùng chung (`config.ts:147-160`); chỉ mang `thresholds`, không bật/tắt được."""

RULE_CODES: Final[tuple[str, ...]] = (
    # 8 luật dựng sẵn — `registry.ts:702-711` (BUILT_IN_RULES); dòng khai `code:` ghi bên phải.
    "WALL-THICKNESS",  # registry.ts:443
    "WALL-LENGTH",  # registry.ts:477
    "OPENING-IN-WALL",  # registry.ts:507
    "DOOR-WIDTH",  # registry.ts:546
    "ROOM-MIN-AREA",  # registry.ts:574
    "ROOM-HAS-DOOR",  # registry.ts:602
    "ROOM-UNNAMED",  # registry.ts:641
    "LEVEL-ELEVATION",  # registry.ts:664
    # 7 luật hình học — `geometry/index.ts:1146-1154` (GEOMETRY_RULES).
    "WALL-OVERLAP",  # geometry/index.ts:1070
    "WALL-DANGLING-END",  # geometry/index.ts:1080
    "ROOM-NOT-CLOSED",  # geometry/index.ts:1090
    "DOOR-SWING-BLOCKED",  # geometry/index.ts:1100
    "OPENING-OVERLAP",  # geometry/index.ts:1110
    "WALL-UNSUPPORTED",  # geometry/index.ts:1120
    "STAIR-ALIGNMENT",  # geometry/index.ts:1130
    # 7 luật chức năng — `function/index.ts:1133-1141` (FUNCTION_RULES).
    "ROOM-NO-DOOR",  # function/index.ts:1063
    "CORRIDOR-WIDTH",  # function/index.ts:1073
    "ROOM-NO-WINDOW",  # function/index.ts:1083
    "ESCAPE-DISTANCE",  # function/index.ts:1093
    "DOOR-BLOCKS-PATH",  # function/index.ts:1103
    "ROOM-AREA-BELOW-MINIMUM",  # function/index.ts:1113
    "FURNITURE-CLASH",  # function/index.ts:1123
    # 3 luật hoàn thiện — `fitout/index.ts:419-423` (FITOUT_RULES).
    "ROOM-FURNITURE-MISMATCH",  # fitout/index.ts:389
    "FIXTURE-OFF-WALL",  # fitout/index.ts:399
    "WINDOW-ON-INNER-WALL",  # fitout/index.ts:409
)
"""25 mã đúng thứ tự `ALL_RULES` (`defaults.ts:47-52`); **không** có `GENERAL`."""


@dataclass(frozen=True)
class ThresholdSpec:
    """Một khoá ngưỡng: luật sở hữu và khoảng `[min, max]` (kiểm hữu hạn và khoảng, không kiểm `step`)."""

    rule_code: str
    min: float
    max: float


_ROOM_USAGES: Final = (
    "livingRoom",
    "bedroom",
    "kitchen",
    "bathroom",
    "corridor",
    "stairwell",
    "utility",
    "other",
)
"""Tám công năng phòng — khoá của `MIN_ROOM_AREA_M2` (`registry.ts:406-415`)."""

_SPECS: Final[dict[str, ThresholdSpec]] = {
    "general.parallelAngleDeg": ThresholdSpec(GENERAL_CODE, 0, 30),  # thresholdSpecs.ts:98,107-108
    "general.jointToleranceMm": ThresholdSpec(GENERAL_CODE, 0, 500),  # thresholdSpecs.ts:114,122-123
    "wall.minThicknessMm": ThresholdSpec("WALL-THICKNESS", 30, 200),  # thresholdSpecs.ts:130,137-138
    "wall.maxThicknessMm": ThresholdSpec("WALL-THICKNESS", 200, 1000),  # thresholdSpecs.ts:144,152-153
    "wall.minLengthMm": ThresholdSpec("WALL-LENGTH", 10, 1000),  # thresholdSpecs.ts:161,167-168
    "door.minWidthMm": ThresholdSpec("DOOR-WIDTH", 600, 1200),  # thresholdSpecs.ts:176,183-184
    # Tám khoá `room.minArea.<công năng>`: `thresholdSpecs.ts:75-92` (min 0, max 60, dưới ROOM-AREA-BELOW-MINIMUM).
    **{f"room.minArea.{usage}": ThresholdSpec("ROOM-AREA-BELOW-MINIMUM", 0, 60) for usage in _ROOM_USAGES},
    "wallOverlap.minOverlapMm": ThresholdSpec("WALL-OVERLAP", 1, 500),  # thresholdSpecs.ts:195,202-203
    "roomClosure.lateralToleranceMm": ThresholdSpec("ROOM-NOT-CLOSED", 0, 500),  # thresholdSpecs.ts:211,218-219
    "roomClosure.maxUncoveredEdgeMm": ThresholdSpec("ROOM-NOT-CLOSED", 0, 2000),  # thresholdSpecs.ts:225,231-232
    "wallSupport.minSupportShare": ThresholdSpec("WALL-UNSUPPORTED", 0.5, 1),  # thresholdSpecs.ts:240,254-255
    "stair.alignmentToleranceMm": ThresholdSpec("STAIR-ALIGNMENT", 0, 1000),  # thresholdSpecs.ts:263,270-271
    "corridor.minClearWidthMm": ThresholdSpec("CORRIDOR-WIDTH", 600, 3000),  # thresholdSpecs.ts:279,286-287
    "stairwell.minClearWidthMm": ThresholdSpec("CORRIDOR-WIDTH", 600, 3000),  # thresholdSpecs.ts:293,300-301
    "escape.openingOnOutlineToleranceMm": ThresholdSpec("ESCAPE-DISTANCE", 0, 1000),  # thresholdSpecs.ts:309,319-320
    "escape.maxDistanceMm": ThresholdSpec("ESCAPE-DISTANCE", 5000, 100000),  # thresholdSpecs.ts:326,334-335
    "door.minClearPassageMm": ThresholdSpec("DOOR-BLOCKS-PATH", 500, 1500),  # thresholdSpecs.ts:343,349-350
    "furniture.minClashMm": ThresholdSpec("FURNITURE-CLASH", 1, 200),  # thresholdSpecs.ts:358,365-366
    "fixture.wallHuggingToleranceMm": ThresholdSpec("FIXTURE-OFF-WALL", 0, 500),  # thresholdSpecs.ts:374,381-382
}

THRESHOLD_SPECS: Final[Mapping[str, ThresholdSpec]] = MappingProxyType(_SPECS)
"""26 khoá ngưỡng (`RULE_THRESHOLD_SPECS`, `thresholdSpecs.ts:95-387`), chỉ đọc."""
