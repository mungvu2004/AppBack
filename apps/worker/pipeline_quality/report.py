"""Báo cáo chất lượng thuần của một lượt (B5-07 [2], [6]): toàn vẹn + đếm mục AI tin cậy thấp.

Không chạm DB hay kho: `service` đọc lớp dưới session rồi gọi `build_report` ngoài mọi session.
`to_json_bytes` tất định (cùng tài liệu → cùng byte) để giao lặp ghi đè `quality.json` y hệt.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from packages.domain.spatial.integrity import IntegrityIssue
from packages.domain.spatial.model import SpatialLayer

QUALITY_REPORT_MAX_BYTES: Final = 8 * 1024 * 1024
"""Trần `quality.json` khi `put` (B5-07 [5]): 8 MiB."""


@dataclass(frozen=True)
class RunQualityReport:
    """Kết quả kiểm một lượt; `low_confidence` có đúng bốn khoá walls, openings, rooms, furniture."""

    run_id: str
    revision: int
    confidence_threshold: float
    issues: tuple[IntegrityIssue, ...]
    has_critical: bool
    low_confidence: Mapping[str, int]

    def to_json_bytes(self) -> bytes:
        """`quality.json` theo B5-07 [2]; chủ: việc A (prep chỉ dựng chữ ký)."""
        raise NotImplementedError


def build_report(
    *, run_id: str, revision: int, layer: SpatialLayer, level_id: str, threshold: Decimal
) -> RunQualityReport:
    """Dựng báo cáo theo B5-07 [6] `build_report`; chủ: việc A (prep chỉ dựng chữ ký)."""
    raise NotImplementedError
