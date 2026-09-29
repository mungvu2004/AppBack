"""Hằng dùng chung của test registry model ML — một bản cho cả bảy file test (R-07).

Ba việc song song (P, B, C, D) mỗi việc tự khai `WALL`/`OPENING`/`DIMENSION`, đường N23/N25 và
id hai bản gốc; bảy bản chép là bảy chỗ phải sửa khi revision dữ liệu đổi id bản gốc. Ở đây chỉ
có **hằng**: helper dựng request khác nhau theo từng op nên vẫn nằm trong file test của op ấy.
"""

from typing import Final

FAMILIES_PATH: Final = "/api/admin/ml/model-families"
VERSIONS_PATH: Final = "/api/admin/ml/model-versions"
ML_QUEUE: Final = "ml.infer"
"""Hàng đợi của `ml.infer.*` (`packages/messaging/celery_app.py:31`) — test tự `DEL` trước khi đếm."""

WALL: Final = "wallSegmentation"
OPENING: Final = "openingAndFurnitureDetection"
DIMENSION: Final = "dimensionReading"

BASELINE_OPENING: Final = "mdl_01KB6010000000000000000001"
BASELINE_DIMENSION: Final = "mdl_01KB6010000000000000000002"
"""Id bản gốc do revision `r20260928_b6_01` ghi — hằng của hệ thống, không sinh ngẫu nhiên."""
