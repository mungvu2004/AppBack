"""Nhãn phát hiện ô mở và đồ đạc, và đích miền của từng nhãn (B5-03 dùng, B5-05 dựng).

`OBJECT_LABELS` theo **đúng thứ tự id lớp YOLO** của model huấn luyện: đổi thứ tự là
đọc sai mọi model đã huấn luyện. `other` chỉ có ở đầu ra (lớp COCO không có đích
riêng), không phải lớp huấn luyện.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Literal, get_args

ObjectLabel = Literal[
    "door",
    "double_door",
    "window",
    "table",
    "chair",
    "bed",
    "wardrobe",
    "kitchen_cabinet",
    "sanitary_fixture",
    "stair",
]
DetectionLabel = ObjectLabel | Literal["other"]
SwingDirection = Literal["left", "right", "double", "sliding", "fixed"]

OBJECT_LABELS: Final[tuple[ObjectLabel, ...]] = get_args(ObjectLabel)
DETECTION_LABELS: Final[tuple[DetectionLabel, ...]] = (*OBJECT_LABELS, "other")

COCO_TO_LABEL: Final[Mapping[str, DetectionLabel]] = MappingProxyType(
    {
        "bed": "bed",
        "chair": "chair",
        "couch": "other",
        "dining table": "table",
        "toilet": "sanitary_fixture",
        "sink": "sanitary_fixture",
    }
)
"""Tên lớp COCO của `yolov8n` gốc → nhãn; lớp COCO khác bị bỏ."""


@dataclass(frozen=True, slots=True)
class LabelTarget:
    """Thực thể miền mà một nhãn dựng thành (`src/domain/spatial/types.ts:135-163`).

    Ô mở mang kích thước mặc định (mm) khi ảnh không cho đủ thông tin; `None` nghĩa là
    lấy theo hộp phát hiện. Đồ đạc không có trường số.
    """

    category: Literal["opening", "furniture"]
    domain_kind: str
    width_mm: int | None = None
    height_mm: int | None = None
    sill_mm: int | None = None
    swing: SwingDirection | None = None


def _furniture(kind: str) -> LabelTarget:
    """Đích đồ đạc: chỉ có loại camel của FE (`FurnitureKind`)."""
    return LabelTarget(category="furniture", domain_kind=kind)


# Kích thước ô mở theo bộ mẫu FE (`__fixtures__/sampleBuilding.ts:49-56,113,125`).
LABEL_TARGETS: Final[Mapping[DetectionLabel, LabelTarget]] = MappingProxyType(
    {
        "door": LabelTarget("opening", "door", 900, 2200, 0, "left"),
        "double_door": LabelTarget("opening", "door", None, 2200, 0, "double"),
        "window": LabelTarget("opening", "window", 1200, 1400, 900, "sliding"),
        "table": _furniture("table"),
        "chair": _furniture("chair"),
        "bed": _furniture("bed"),
        "wardrobe": _furniture("wardrobe"),
        "kitchen_cabinet": _furniture("kitchenCabinet"),
        "sanitary_fixture": _furniture("sanitaryFixture"),
        "stair": _furniture("stair"),
        "other": _furniture("other"),
    }
)
