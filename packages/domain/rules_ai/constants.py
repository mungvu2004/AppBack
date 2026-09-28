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

LOW_CONFIDENCE_CAP: Final = 0.5
"""Trần tin cậy của mục đã bị luật đụng vào; dưới 0,7 và 0,75 của màn QC nên rơi vào hàng "tin cậy thấp"."""

MATCH_TOLERANCE_MM: Final = 50
"""Dung sai đối chiếu đầu mút tường khi trộn: `JOINT_TOLERANCE_MM`, `rules/geometry/index.ts:80-86`."""

GRID_CELL_MM: Final = 1000
"""Cạnh ô lưới chỉ mục của luật 1-2: cỡ một phòng nhỏ, để mỗi ô chỉ chứa vài tường."""
