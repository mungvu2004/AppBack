"""Đọc kích thước và nhãn phòng từ chữ OCR: hàm thuần cho worker (B5-05), không nhập `onnxruntime`.

Chỉ xuất lại tên của khối [2] của B5-04; nhập gói không có tác dụng phụ.
"""

from packages.vision.dimensions.lengths import (
    DIMENSION_MAX_MM,
    LengthReading,
    parse_length_fraction,
    parse_length_mm,
    read_length,
)
from packages.vision.dimensions.pairing import pair_dimension_lines, wall_spans
from packages.vision.dimensions.rooms import (
    ROOM_USAGE_NAMES,
    RoomLabel,
    match_room_label,
    name_rooms,
    room_label_key,
)

__all__ = [
    "DIMENSION_MAX_MM",
    "ROOM_USAGE_NAMES",
    "LengthReading",
    "RoomLabel",
    "match_room_label",
    "name_rooms",
    "pair_dimension_lines",
    "parse_length_fraction",
    "parse_length_mm",
    "read_length",
    "room_label_key",
    "wall_spans",
]
