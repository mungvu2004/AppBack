"""Hằng nghiệp vụ của bước dựng lớp không gian (B5-05 [5]); mỗi hằng ghi nguồn."""

from typing import Final

STANDARD_THICKNESSES_MM: Final = (100, 150, 200, 220, 300, 400)
"""Bề dày chuẩn FE bắt tường về (`src/domain/walls/cleanup.ts:70`); hoà lấy số nhỏ hơn."""

DEFAULT_WALL_HEIGHT_MM: Final = 3600
"""Chiều cao tường mặc định của bộ mẫu FE (`src/domain/spatial/__fixtures__/sampleBuilding.ts:49-56`)."""

OPENING_WALL_REACH_MM: Final = 150
"""Tâm hộp ô mở được xa đường tim tối đa `thicknessMm / 2 + 150` (B5-05 [6] bước 4)."""

OPENING_GAP_MAX_MM: Final = 2400
"""Khe tường dài nhất còn coi là chỗ khoét ô mở (B5-05 [6] bước 3b)."""

WALL_JOIN_MM: Final = 150
"""Khối ngắn cách tường khác ≤ 150 mm là tường thật, xa hơn là khối cô lập (B5-05 [6] bước 3)."""

ROOM_SNAP_MM: Final = 150
"""Kéo dài đường tim khi khép phòng và ngưỡng gán `wallIds` (B5-05 [6] bước 5)."""

MIN_ROOM_AREA_M2: Final = 1.0
"""Mảnh polygonize nhỏ hơn 1 m² là rác hình học, không phải phòng (B5-05 [6] bước 5)."""

DROPPED_KEYS: Final = (
    "wallZeroLength",
    "isolatedBlock",
    "wallGapBridged",
    "outOfImage",
    "unknownLabel",
    "openingUnattached",
    "openingTooWide",
    "openingOverlap",
    "furnitureEmpty",
    "roomTooSmall",
    "dimensionUnpaired",
    "scaleOutOfRange",
)
"""Khoá của `BuiltLayer.dropped`, luôn đủ cả 12 (0 mặc định, B5-05 [5]); thứ tự là thứ tự dây."""
