"""Hằng nghiệp vụ của bước dựng lớp không gian (B5-05 [5]); mỗi hằng ghi nguồn."""

from typing import Final

STANDARD_THICKNESSES_MM: Final = (100, 150, 200, 220, 300, 400)
"""Bề dày chuẩn FE bắt tường về (`src/domain/walls/cleanup.ts:70`); hoà lấy số nhỏ hơn."""

DEFAULT_WALL_HEIGHT_MM: Final = 3600
"""Chiều cao tường mặc định của bộ mẫu FE (`src/domain/spatial/__fixtures__/sampleBuilding.ts:49-56`)."""

OPENING_WALL_REACH_MM: Final = 150
"""Hộp ô mở (không phải tâm hộp) được xa đường tim tối đa `thicknessMm / 2 + 150` (B5-05 [6] bước 4).

Đo tới hộp vì bản vẽ xoay chéo cho hộp thẳng trục vuông lớn, tâm xa tim 250-670 mm (BUG-IT-003).
"""

OPENING_MIN_WIDTH_MM: Final = 300
"""Hình chiếu hộp cửa đi/cửa sổ lên tim hẹp hơn 300 mm là suy biến (hộp gần hết ra ngoài đầu
tường): dùng rộng mặc định của `LABEL_TARGETS` (BUG-IT-004); ô mở thật hẹp nhất ~400 mm."""

CORNER_OVERSHOOT_MM: Final = 150
"""Kéo đầu tường tới vách vuông góc (3b-b) khi chỗ giao lố ra ngoài đầu vách tối đa
`max(bề dày vách, 150)`; vách được kéo theo tới chân để góc khép (BUG-IT-001: G2 lố 29 mm)."""

DIAGONAL_ALIGN_DEG: Final = 5.0
"""Sai số góc của 3b (thẳng hàng, vuông góc) khi **cả hai** tường lệch trục > 5° (BUG-IT-007).

Bản vẽ xoay chéo (CubiCasa G5, 45°) cho tim tường nhiễu vài độ hai bên khe cửa: 2° của B5-05 [6] 3b
không gộp được, cửa gắn vào mẩu tường ngắn rồi rơi `openingTooWide`. Tường thẳng trục giữ 2°.
"""

OPENING_GAP_MAX_MM: Final = 2400
"""Khe tường dài nhất còn coi là chỗ khoét ô mở (B5-05 [6] bước 3b)."""

WALL_JOIN_MM: Final = 150
FAR_CLUSTER_LENGTH_SHARE: Final = 0.15
"""U57: cụm tường tách rời có tổng dài dưới tỉ lệ này của mọi tường mới là ứng viên bỏ."""
FAR_CLUSTER_AREA_SHARE: Final = 0.10
"""U57: ... và hộp bao dưới tỉ lệ này của hộp bao cụm chính."""
FAR_CLUSTER_GAP_MM: Final = 1500
"""U57: ... và khe giữa hộp bao của nó với hộp bao cụm chính lớn hơn số này (mm)."""
"""Khối ngắn cách tường khác ≤ 150 mm là tường thật, xa hơn là khối cô lập (B5-05 [6] bước 3)."""

ROOM_SNAP_MM: Final = 150
"""Kéo dài đường tim khi khép phòng và ngưỡng gán `wallIds` (B5-05 [6] bước 5)."""

MIN_ROOM_AREA_M2: Final = 1.0
"""Mảnh polygonize nhỏ hơn 1 m² là rác hình học, không phải phòng (B5-05 [6] bước 5)."""

ROOM_GAP_CLOSE_MM: Final = 1200
"""Đầu tường tự do (không chạm tường/`bridges` nào trong `ROOM_SNAP_MM`) được nối thẳng tới tim tường khác gần nhất
≤ 1200 mm khi khép phòng, nếu đoạn nối không cắt tường nào khác (BUG-IT-008: khe góc/chữ T không có hộp ô mở).

1200 = cửa đi 900 thông thuỷ + hai nửa tường tới tim. Bench căn hộ 27/10/2026 (14 bản): 1000 → 1200 thêm 4 phòng
tách đúng (cửa phòng, lô gia hở một khe), 1800 trở lên bắt đầu chẻ phòng giả."""

ROOM_GAP_CLOSE_MIN_COS: Final = 0.5
"""Đoạn nối khe phải lệch ≤ 60° so với hướng ra của đầu tường (cos ≥ 0,5): bỏ nối ngang từ vách cụt chẻ đôi phòng."""

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
