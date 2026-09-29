"""Nhãn phòng OCR → công năng (`usage`) và tên có dấu, gương `roomNameKey` của FE.

Tên chỉ lấy từ `ROOM_USAGE_NAMES` (bộ tên `registry.ts:418-427` mà RoomLabelReview chuẩn hoá
về), không bao giờ chép chữ OCR (BE-00 §10, khối [7]). Nhãn không nhận ra → `None`, người
gọi lùi về `other` qua `name_rooms` (K8).
"""

import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Literal

RoomUsage = Literal["livingRoom", "bedroom", "kitchen", "bathroom", "corridor", "stairwell", "utility", "other"]
"""Bằng kiểu `Room.usage` của B3-01 (test chốt hai tập bằng nhau)."""

ROOM_USAGE_NAMES: Final[Mapping[RoomUsage, str]] = MappingProxyType(
    {
        "livingRoom": "phòng khách",
        "bedroom": "phòng ngủ",
        "kitchen": "bếp",
        "bathroom": "phòng tắm",
        "corridor": "hành lang",
        "stairwell": "buồng thang",
        "utility": "phòng kỹ thuật",
        "other": "phòng khác",
    }
)

_KEYS: Final[Mapping[RoomUsage, tuple[str, ...]]] = MappingProxyType(
    {
        "livingRoom": ("phong khach", "p khach", "pk", "khach", "sinh hoat chung", "phong sinh hoat"),
        "bedroom": ("phong ngu", "p ngu", "pn", "ngu"),
        "kitchen": ("bep", "nha bep", "phong bep", "bep an", "phong an"),
        "bathroom": ("ve sinh", "wc", "vs", "toilet", "tam", "phong tam", "p tam"),
        "corridor": ("hanh lang", "sanh", "loi di"),
        "stairwell": ("cau thang", "thang bo", "buong thang", "thang"),
        "utility": ("ky thuat", "phong ky thuat", "kho", "giat phoi", "gen"),
    }
)
_USAGE_BY_SQUASHED_KEY: Final[Mapping[str, RoomUsage]] = MappingProxyType(
    {key.replace(" ", ""): usage for usage, keys in _KEYS.items() for key in keys}
)
"""Khoá bỏ hết khoảng trắng → công năng: một bảng phục vụ cả khớp nguyên khoá lẫn `PHONGNGU`."""

_ORDINAL: Final = re.compile(r"\s+([0-9]+)\Z")
_COMBINING_MARKS: Final = re.compile(f"[{chr(0x0300)}-{chr(0x036F)}]")  # U+0300-U+036F như FE (gateway.ts:995)
_SEPARATORS: Final = re.compile(r"[._:/\-]")
_SPACES: Final = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class RoomLabel:
    """Công năng và tên chuẩn của một phòng."""

    usage: RoomUsage
    name: str


def _split_ordinal(text: str) -> tuple[str, str | None]:
    """Tách số thứ tự cuối (`PHONG NGU 1` → `("phong ngu", "1")`) khỏi chữ đã NFC, casefold, strip."""
    folded = unicodedata.normalize("NFC", text).casefold().strip()
    match = _ORDINAL.search(folded)
    return (folded[: match.start()], match.group(1)) if match else (folded, None)


def _key_of(base: str) -> str:
    """Bỏ dấu (NFD, `đ` → `d`), đổi `[._:/-]` thành khoảng trắng, gom khoảng trắng."""
    bare = _COMBINING_MARKS.sub("", unicodedata.normalize("NFD", base)).replace("đ", "d")
    return _SPACES.sub(" ", _SEPARATORS.sub(" ", bare)).strip()


def room_label_key(text: str) -> str:
    """Khoá so sánh tên phòng, gương `roomNameKey` (roomLabelReviewGateway.ts:1007-1016) thêm NFC và dấu phân cách."""
    return _key_of(_split_ordinal(text)[0])


def match_room_label(text: str) -> RoomLabel | None:
    """Nhãn phòng của chuỗi OCR, hoặc `None` khi khoá không có trong từ điển.

    Khớp nguyên khoá hoặc khoá bỏ hết khoảng trắng, không khớp chuỗi con (`NGU NGON` → `None`).
    Số thứ tự cuối được giữ vào tên (`PHONG NGU 1` → `phòng ngủ 1`).
    """
    base, ordinal = _split_ordinal(text)
    usage = _USAGE_BY_SQUASHED_KEY.get(_key_of(base).replace(" ", ""))
    if usage is None:
        return None
    name = ROOM_USAGE_NAMES[usage]
    return RoomLabel(usage, name if ordinal is None else f"{name} {ordinal}")


def name_rooms(labels: Sequence[RoomLabel | None]) -> tuple[RoomLabel, ...]:
    """Đặt tên cho mọi phòng, giữ thứ tự; tên trùng thêm ` n` nhỏ nhất (từ 2) chưa dùng.

    `None` ở vị trí `k` (đếm từ 1) → `other` tên `phòng k`. Tên `phòng ngủ` hai lần → `phòng ngủ`, `phòng ngủ 2`.
    """
    used: set[str] = set()
    named: list[RoomLabel] = []
    for position, label in enumerate(labels, start=1):
        label = label or RoomLabel("other", f"phòng {position}")
        name, suffix = label.name, 2
        while name in used:
            name, suffix = f"{label.name} {suffix}", suffix + 1
        used.add(name)
        named.append(RoomLabel(label.usage, name))
    return tuple(named)
