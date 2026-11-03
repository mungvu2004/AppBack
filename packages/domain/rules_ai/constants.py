"""Hằng của luật hậu xử lý AI; mỗi hằng dẫn nguồn FE hoặc lý do.

Cố định trong mã, không đọc cấu hình luật dự án: gói chạy trước B3-05 và không có
ngữ cảnh dự án (B3-06 [6] luật 1).
"""

from typing import Final

WALL_HUGGING_KINDS: Final = ("sanitaryFixture", "kitchenCabinet")
"""Đồ phải áp tường vì nối ống: `WALL_HUGGING_FURNITURE`, `fitout/index.ts:87` (gồm cả tủ bếp)."""

WALL_HUGGING_TOLERANCE_MM: Final = 50
"""Khe còn tính là áp tường: `WALL_HUGGING_TOLERANCE_MM`, `fitout/index.ts:96` (chân tường + sai số vẽ tay)."""

FIXTURE_SNAP_REACH_MM: Final = 300
"""Xa hơn thế là sai phòng, không phải lệch vài cm: không dời, để QC báo cho người duyệt."""

EXTERIOR_PROBE_MM: Final = 150
"""Điểm dò ngoài mặt tường khi phân biệt tường ngoài/trong; vượt bề dày tường một khoảng đủ ra khỏi lớp trát."""

SLIDING_DOOR_MIN_WIDTH_MM: Final = 1400
"""Cửa sổ AI giữa một phòng và lô gia chưa có lối vào, rộng từ chừng này → cửa đi lùa (BENCH3D-12).

Bench r3: vách kính lùa ra lô gia bị dò thành cửa sổ rộng 1476 tới 3117 mm; cửa sổ thật phòng → lô gia 1027 tới 1200 mm.
"""

SLIDING_LOGGIA_MIN_DEPTH_MM: Final = 800
"""Lô gia phải còn là lô gia ở điểm cách tim tường chủ chừng này, ngay trước tâm ô kính, thì cửa sổ mới thành cửa lùa
(BENCH3D-23): người không bước ra dải hẹp hơn (lối đi tối thiểu ~0,8 m). Dải ảo giữa tường ngoài và nét khung bản vẽ
(tập F f-06: "lô gia" sâu 500 mm dọc 10,6 m) đổi nhầm 2 cửa sổ phòng ngủ thành cửa đi; lô gia thật trên bench A/C/E,
F sâu ≥ 830 mm (hộp bao xoay của đường bao, đo từ tim tường).

Đo ở tỉ lệ dựng như `SLIDING_DOOR_MIN_WIDTH_MM` (`apply_post_rules` chạy trước khi đổi về tỉ lệ ghi ra lớp): khi
`project_default` (tỉ lệ chưa tin, màn Đặt tỷ lệ đã báo) hai số này lệch theo `final / build`."""
# ponytail: ngưỡng mm luật 2 đo ở tỉ lệ dựng; truyền `final / build` vào `apply_post_rules` nếu project_default sai

SLIDING_DOOR_HEIGHT_MM: Final = 2200
"""Cao cửa lùa đổi từ cửa sổ (bệ 0): như cửa đi mặc định `LABEL_TARGETS["door"]` (`ml_contracts/labels.py`)."""

LOW_CONFIDENCE_CAP: Final = 0.5
"""Trần tin cậy của mục đã bị luật đụng vào; dưới 0,7 và 0,75 của màn QC nên rơi vào hàng "tin cậy thấp"."""

MATCH_TOLERANCE_MM: Final = 50
"""Dung sai đối chiếu đầu mút tường khi trộn: `JOINT_TOLERANCE_MM`, `rules/geometry/index.ts:80-86`."""

GRID_CELL_MM: Final = 1000
"""Cạnh ô lưới chỉ mục của luật 1-2: cỡ một phòng nhỏ, để mỗi ô chỉ chứa vài tường."""
