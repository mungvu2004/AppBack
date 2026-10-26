"""Nhãn phòng OCR → công năng (`usage`) và tên có dấu, gương `roomNameKey` của FE.

Tên chỉ lấy từ `ROOM_USAGE_NAMES` (bộ tên `registry.ts:418-427` mà RoomLabelReview chuẩn hoá
về), không bao giờ chép chữ OCR (BE-00 §10, khối [7]). Nhãn không nhận ra → `None`, người
gọi lùi về `other` qua `name_rooms` (K8).

OCR đọc bản vẽ căn hộ VN ra chữ không dấu và sai vài ký tự ("PHONG NCU", "LOGOA", "TEN SANH"),
nhãn ghép ("Phòng khách + Bếp ăn") và số dính chữ ("WC02"). Bench căn hộ 27/10/2026: khớp nguyên
khoá chỉ nhận đúng 8/109 phòng. Nên sau khớp nguyên khoá còn khớp gần đúng (`_fuzzy_usage`).
"""

import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Literal

RoomUsage = Literal[
    "livingRoom", "bedroom", "kitchen", "bathroom", "corridor", "stairwell", "utility", "loggia", "other"
]
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
        "loggia": "lô gia",
        "other": "phòng khác",
    }
)

_KEYS: Final[Mapping[RoomUsage, tuple[str, ...]]] = MappingProxyType(
    {
        "livingRoom": ("phong khach", "p khach", "pk", "khach", "sinh hoat chung", "phong sinh hoat"),
        "bedroom": ("phong ngu", "p ngu", "pn", "ngu", "phong con", "master"),
        "kitchen": ("bep", "nha bep", "phong bep", "bep an", "phong an"),
        "bathroom": ("ve sinh", "wc", "vs", "toilet", "tam", "phong tam", "p tam"),
        "corridor": ("hanh lang", "sanh", "loi di", "tien sanh"),
        "stairwell": ("cau thang", "thang bo", "buong thang", "thang"),
        "utility": ("ky thuat", "phong ky thuat", "kho", "giat phoi", "gen", "san phoi", "thay do", "phong thay do"),
        "loggia": ("lo gia", "loggia", "ban cong"),
    }
)
_USAGE_BY_SQUASHED_KEY: Final[Mapping[str, RoomUsage]] = MappingProxyType(
    {key.replace(" ", ""): usage for usage, keys in _KEYS.items() for key in keys}
)
"""Khoá bỏ hết khoảng trắng → công năng: một bảng phục vụ cả khớp nguyên khoá lẫn `PHONGNGU`."""
_KEY_SPACED: Final[Mapping[str, str]] = MappingProxyType(
    {key.replace(" ", ""): key for keys in _KEYS.values() for key in keys}
)

_ORDINAL: Final = re.compile(r"\s+([0-9]+)\Z")
_PARTS: Final = re.compile(r"[+&,]")
"""Nhãn ghép "khách + bếp", "khách, bếp & ăn": phần đầu nhận ra được quyết công năng."""
_GLUED_NUMBER: Final = re.compile(r"(?<=[^\W\d_])(?=\d)")
"""Chỗ số dính sau chữ ("WC02", "NGU01"): chèn khoảng trắng để tách số thứ tự."""
_PREFIXES: Final = frozenset({"p", "ph", "phong"})
_FUZZY_WORDS: Final = frozenset({"ngu", "bep", "khach", "master", "sanh"})
"""Chữ một từ được khớp gần đúng: ít gần chữ thường của bản vẽ. Khoá khác chỉ khớp nguyên: "tam" gần "tim"
(tim tường), "thang" gần "thong" (thông thuỷ) và "tang" (tầng), "kho" gần "khu"."""
_NOT_LABELS: Final = frozenset({"phong khac"})
"""Tên do `name_rooms` sinh cho `other`, không phải nhãn (gần "phong khach" một ký tự)."""
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


def _distance(a: str, b: str) -> int:
    """Khoảng cách Levenshtein (chuỗi ngắn: nhãn phòng)."""
    previous = list(range(len(b) + 1))
    for i, char in enumerate(a, start=1):
        current = [i]
        for j, other in enumerate(b, start=1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (char != other)))
        previous = current
    return previous[-1]


def _near(token: str, key: str) -> bool:
    """`token` là `key` đọc sai; chỉ các chữ đặc trưng `_FUZZY_WORDS`, khoá khác phải khớp nguyên.

    Khoá 3 chữ: cùng ba chữ đầu ("ngui") hay sai 1 giữ chữ đầu ("ncu", "bap"). Khoá 4 chữ: sai 1, cùng chữ đầu.
    Dài hơn: sai 1, hai khi cả hai >= 6 chữ ("mrsfer" là "master"). Chữ < 4 không khớp khoá dài hơn.
    """
    if token == key:
        return True
    if key not in _FUZZY_WORDS:
        return False
    if len(key) == 3:
        return token[:3] == key or (len(token) == 3 and token[0] == key[0] and _distance(token, key) <= 1)
    if len(token) < 4 or (len(key) == 4 and token[0] != key[0]):
        return False
    return _distance(token, key) <= (2 if min(len(token), len(key)) >= 6 else 1)


def _fuzzy_usage(key: str) -> RoomUsage | None:
    """Công năng của khoá không khớp nguyên, lần lượt:

    1. khoá nhiều chữ là đầu của nhãn ("phong ngu master", "phong con gai");
    2. bỏ tiền tố `phong`/`p`/`ph` (cả khi sai 1 chữ), cả cụm còn lại khớp nguyên hay gần đúng một khoá duy nhất:
       sai 1, sai 2 khi cả hai >= 7 chữ ("tehsinh" không là "vesinh"); hai công năng cùng gần → bỏ bước này
       ("ten sinh" gần cả "ve sinh" lẫn "tien sanh");
    3. từng chữ theo thứ tự với khoá một chữ (`_near`), chữ đầu nhận ra được quyết.
    """
    words = key.split()
    for usage, keys in _KEYS.items():
        if any(" " in k and words[: len(k.split())] == k.split() for k in keys):
            return usage
    if len(words) > 1 and (words[0] in _PREFIXES or _distance(words[0], "phong") <= 1):
        words = words[1:]
    squashed = "".join(words)
    if squashed in _USAGE_BY_SQUASHED_KEY:
        return _USAGE_BY_SQUASHED_KEY[squashed]
    if len(squashed) >= 4:
        close = {
            usage
            for k, usage in _USAGE_BY_SQUASHED_KEY.items()
            if len(k) >= 5 and _distance(squashed, k) <= (2 if min(len(squashed), len(k)) >= 7 else 1)
        }
        if len(close) == 1:
            return close.pop()
    for word in words:
        for k, usage in _USAGE_BY_SQUASHED_KEY.items():
            if " " not in _KEY_SPACED[k] and _near(word, k):
                return usage
    return None


def match_room_label(text: str) -> RoomLabel | None:
    """Nhãn phòng của chuỗi OCR, hoặc `None` khi không nhận ra.

    Mỗi phần của nhãn ghép (tách ở `+ & ,`) lần lượt: khớp nguyên khoá hay khoá bỏ hết khoảng trắng, rồi khớp gần
    đúng (`_fuzzy_usage`). Số thứ tự cuối của phần khớp được giữ vào tên (`PHONG NGU 1` → `phòng ngủ 1`).
    """
    for part in _PARTS.split(text):
        base, ordinal = _split_ordinal(_GLUED_NUMBER.sub(" ", part))
        key = _key_of(base)
        if not key or key in _NOT_LABELS:
            continue
        usage = _USAGE_BY_SQUASHED_KEY.get(key.replace(" ", "")) or _fuzzy_usage(key)
        if usage is not None:
            name = ROOM_USAGE_NAMES[usage]
            return RoomLabel(usage, name if ordinal is None else f"{name} {ordinal}")
    return None


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
