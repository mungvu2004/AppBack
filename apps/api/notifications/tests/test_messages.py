"""Câu tiếng Việt, `clean_label` và `notification_wire` (B4-02 [6] "Câu", [8] "Câu")."""

from datetime import UTC, datetime
from typing import Final

import pytest

from apps.api.notifications import messages
from apps.api.notifications.payload import notification_wire
from packages.core.text import nfc
from packages.db.models.notifications import NotificationRow

RLO: Final = chr(0x202E)
LRI: Final = chr(0x2066)
PDI: Final = chr(0x2069)
ZWSP: Final = chr(0x200B)
BEL: Final = chr(0x07)
GRAVE: Final = chr(0x0300)
LABELS: Final = ("Chung cư Sông Hàn", "tầng trệt", "tầng 2", "Tường ngoài")


def test_messages__table() -> None:
    """Đúng bảng [6]."""
    assert messages.project_invite("Lê Minh") == "Lê Minh đã thêm bạn vào dự án"
    assert messages.project_invite(None) == "bạn vừa được thêm vào dự án"
    assert messages.ai_completed() == "hệ thống AI đã xử lý xong bản vẽ"
    assert messages.violation_found(3) == "phát hiện 3 vi phạm luật ở"


@pytest.mark.parametrize(
    ("count", "text"), [(1, "1"), (999, "999"), (1000, "1.000"), (1234, "1.234"), (1234567, "1.234.567")]
)
def test_messages__violation_found_groups_thousands_with_dots(count: int, text: str) -> None:
    """Từ 1 000 nhóm nghìn bằng dấu chấm."""
    assert messages.violation_found(count) == f"phát hiện {text} vi phạm luật ở"


@pytest.mark.parametrize("count", [0, -1])
def test_messages__violation_found_rejects_non_positive(count: int) -> None:
    """`count < 1` là lỗi lập trình."""
    with pytest.raises(ValueError, match="count"):
        messages.violation_found(count)


@pytest.mark.parametrize("actor", ["", "   ", ZWSP, RLO + BEL])
def test_messages__project_invite_blank_name_falls_back(actor: str) -> None:
    """Tên rỗng sau làm sạch → nhánh `None`."""
    assert messages.project_invite(actor) == "bạn vừa được thêm vào dự án"


def test_messages__project_invite_cleans_and_nfc_the_name() -> None:
    """Tên qua `clean_label`: bỏ ký tự đảo chiều, gộp khoảng trắng, NFC."""
    text = messages.project_invite(f"  Le{GRAVE} {RLO}Minh  ")
    assert text == nfc("Lè Minh đã thêm bạn vào dự án")


def test_messages__no_sentence_ends_with_a_label() -> None:
    """FE nối `objectLabel` sau câu, nên không câu nào được kết thúc bằng nhãn truyền vào."""
    sentences = [messages.project_invite(label) for label in LABELS]
    sentences += [messages.project_invite(None), messages.ai_completed(), messages.violation_found(2)]
    assert not any(
        sentence.endswith(label) for sentence in sentences for label in ("Chung cư Sông Hàn", "tầng trệt", "tầng 2")
    )


def test_messages__all_sentences_are_nfc() -> None:
    """Mọi câu ở dạng NFC."""
    for sentence in (messages.project_invite("Lê Minh"), messages.ai_completed(), messages.violation_found(12)):
        assert sentence == nfc(sentence)


@pytest.mark.parametrize(
    ("raw", "cleaned"),
    [
        (f"a{RLO}b{LRI}c{PDI}", "abc"),
        (f"a{BEL}b{ZWSP}c", "abc"),
        ("  a \n\t b   c ", "a b c"),
        (f"Ha{GRAVE}n", nfc("Hàn")),
        ("", ""),
        (ZWSP, ""),
    ],
)
def test_clean_label__cases(raw: str, cleaned: str) -> None:
    """NFC, bỏ `Cc`/`Cf`, gộp khoảng trắng."""
    assert messages.clean_label(raw) == cleaned


def test_clean_label__caps_length_without_trailing_space() -> None:
    """Cắt `max_len`; khoảng trắng đuôi sau khi cắt bị bỏ."""
    assert messages.clean_label("ab cd", max_len=3) == "ab"
    assert messages.clean_label("x" * 300) == "x" * messages.LABEL_MAX


def _row(**overrides: object) -> NotificationRow:
    """Dòng chưa lưu, đủ trường bắt buộc."""
    fields: dict[str, object] = {
        "id": "ntf_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        "user_id": "usr_x",
        "kind": "aiCompleted",
        "place": "walls",
        "project_id": "prj_x",
        "project_name": "Dự án",
        "floor_level_id": "L-0000000001",
        "object_label": "Tường",
        "message": "hệ thống AI đã xử lý xong bản vẽ",
        "excerpt": None,
        "is_read": False,
        "dedupe_key": "secret-key",
        "stream_id": "1-1",
        "created_at": datetime(2026, 1, 2, 3, 4, 5, 678901, tzinfo=UTC),
    }
    fields.update(overrides)
    return NotificationRow(**fields)


def test_notification_wire__keys_and_omissions() -> None:
    """Đúng khoá dây; `createdAt` cắt về mili giây; không `userId`, `dedupeKey`, `streamId`; `excerpt` vắng khi rỗng."""
    wire = notification_wire(_row())
    assert wire["createdAt"] == "2026-01-02T03:04:05.678Z"
    assert set(wire) == {
        "id",
        "kind",
        "place",
        "projectId",
        "projectName",
        "objectLabel",
        "message",
        "isRead",
        "createdAt",
        "floorId",
    }
    assert wire["floorId"] == "L-0000000001"
    lean = notification_wire(_row(floor_level_id=None, place="rules", excerpt="trích"))
    assert "floorId" not in lean
    assert lean["excerpt"] == "trích"
