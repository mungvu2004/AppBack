"""Nhãn phòng: bảng ca, `room_label_key` so với `roomNameKey` của FE, tên và đặt tên phòng."""

import unicodedata
from typing import get_args

import pytest

from packages.domain.spatial import Room
from packages.vision.dimensions import ROOM_USAGE_NAMES, RoomLabel, match_room_label, name_rooms, room_label_key
from packages.vision.dimensions.rooms import _KEYS, _USAGE_BY_SQUASHED_KEY

# `src/domain/rules/registry.ts:418-427`.
FE_NAMES = {
    "livingRoom": "phòng khách",
    "bedroom": "phòng ngủ",
    "kitchen": "bếp",
    "bathroom": "phòng tắm",
    "corridor": "hành lang",
    "stairwell": "buồng thang",
    "utility": "phòng kỹ thuật",
    "other": "phòng khác",
}
# Dựng tay từ `roomNameKey` (roomLabelReviewGateway.ts:1007-1016): trim, thường, bỏ số cuối, NFD bỏ dấu, `đ` → `d`.
FE_KEYS = {
    "phòng khách": "phong khach",
    "phòng ngủ": "phong ngu",
    "bếp": "bep",
    "phòng tắm": "phong tam",
    "hành lang": "hanh lang",
    "buồng thang": "buong thang",
    "phòng kỹ thuật": "phong ky thuat",
    "phòng khác": "phong khac",
}


def test_usage_names_equal_registry() -> None:
    """Tám tên bằng `ROOM_USAGE_LABELS` của FE và khoá bằng tập giá trị `Room.usage`."""
    assert dict(ROOM_USAGE_NAMES) == FE_NAMES
    assert set(ROOM_USAGE_NAMES) == set(get_args(Room.model_fields["usage"].annotation))


def test_dictionary_keys_do_not_collide_when_squashed() -> None:
    """Bỏ khoảng trắng không làm hai khoá khác công năng trùng nhau."""
    assert len(_USAGE_BY_SQUASHED_KEY) == sum(len(keys) for keys in _KEYS.values())


@pytest.mark.parametrize(("name", "key"), FE_KEYS.items())
def test_room_label_key_matches_fe(name: str, key: str) -> None:
    """Cùng khoá như `roomNameKey` trên tên FE, bản viết hoa, bản có số, bản NFD."""
    assert room_label_key(name) == key
    assert room_label_key(name.upper()) == key
    assert room_label_key(f"{name.upper()} 12") == key
    assert room_label_key(unicodedata.normalize("NFD", name)) == key


@pytest.mark.parametrize(
    ("text", "key"),
    [
        ("P.KHACH", "p khach"),
        ("  PHONG-NGU:1 ", "phong ngu 1"),
        ("Đ/A", "d a"),
        ("", ""),
        ("12", "12"),
        ("PHONG NGU 3 ", "phong ngu"),
    ],
)
def test_room_label_key_separators(text: str, key: str) -> None:
    """`[._:/-]` thành khoảng trắng, gom khoảng trắng, số đứng một mình không phải số thứ tự."""
    assert room_label_key(text) == key


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("PHONG NGU 1", RoomLabel("bedroom", "phòng ngủ 1")),
        ("P.KHACH", RoomLabel("livingRoom", "phòng khách")),
        ("WC", RoomLabel("bathroom", "phòng tắm")),
        ("BẾP", RoomLabel("kitchen", "bếp")),
        ("Phòng ngủ", RoomLabel("bedroom", "phòng ngủ")),
        (unicodedata.normalize("NFD", "Phòng ngủ"), RoomLabel("bedroom", "phòng ngủ")),
        ("PHONGNGU", RoomLabel("bedroom", "phòng ngủ")),
        ("HANH LANG", RoomLabel("corridor", "hành lang")),
        ("CAU THANG 02", RoomLabel("stairwell", "buồng thang 02")),
        ("PHONG KY THUAT", RoomLabel("utility", "phòng kỹ thuật")),
        ("SAN VUON", None),
        ("NGU NGON", None),
        ("", None),
        ("   ", None),
        ("3", None),
        ("PHONG KHAC", None),
    ],
)
def test_match_room_label_table(text: str, expected: RoomLabel | None) -> None:
    """Khớp nguyên khoá hoặc khoá bỏ khoảng trắng; không khớp chuỗi con; tên lấy từ bộ FE, không chép chữ OCR."""
    assert match_room_label(text) == expected


def test_every_dictionary_key_matches_its_usage() -> None:
    """Mọi khoá trong từ điển khớp về đúng công năng và tên chuẩn."""
    for usage, keys in _KEYS.items():
        for key in keys:
            assert match_room_label(key) == RoomLabel(usage, ROOM_USAGE_NAMES[usage])


def test_name_rooms_example() -> None:
    """`None` thành `phòng k`, tên trùng thêm số nhỏ nhất chưa dùng, giữ thứ tự."""
    bedroom = RoomLabel("bedroom", "phòng ngủ")
    assert name_rooms([bedroom, None, bedroom, None]) == (
        bedroom,
        RoomLabel("other", "phòng 2"),
        RoomLabel("bedroom", "phòng ngủ 2"),
        RoomLabel("other", "phòng 4"),
    )


def test_name_rooms_skips_used_numbers_and_handles_empty() -> None:
    """Số ` n` bỏ qua tên đã có; rỗng → rỗng; nhãn đầu `None` → `phòng 1`."""
    one, two = RoomLabel("bedroom", "phòng ngủ 2"), RoomLabel("bedroom", "phòng ngủ")
    assert [label.name for label in name_rooms([two, one, two])] == ["phòng ngủ", "phòng ngủ 2", "phòng ngủ 3"]
    assert name_rooms([]) == ()
    assert name_rooms([None]) == (RoomLabel("other", "phòng 1"),)


def test_name_rooms_generated_name_can_collide_with_a_label() -> None:
    """`phòng 2` do vị trí sinh ra mà đã có nhãn cùng tên → vẫn không trùng."""
    label = RoomLabel("other", "phòng 2")
    assert [x.name for x in name_rooms([label, None])] == ["phòng 2", "phòng 2 2"]
