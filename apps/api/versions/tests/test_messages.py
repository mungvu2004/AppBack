"""Ba câu ghi chú người đọc của phiên bản (B3-04 [6] "Câu người đọc") — đúng từng chữ."""

from apps.api.versions.messages import after_note, before_note, before_pipeline_note


def test_after_note__exact_text() -> None:
    """Bản "sau" khớp `versionHistoryGateway.ts:313`."""
    assert after_note(3) == "phục hồi nội dung của phiên bản v3"


def test_before_note__exact_text() -> None:
    """Bản "trước" của phục hồi."""
    assert before_note(3) == "trạng thái trước khi phục hồi phiên bản v3"


def test_before_pipeline_note__exact_text() -> None:
    """Bản "trước" khi pipeline AI ghi."""
    assert before_pipeline_note() == "trạng thái trước khi ghi kết quả AI"


def test_notes__number_has_no_group_separator() -> None:
    """`n` = 1000 viết liền `v1000`, không `1,000` hay `1.000`."""
    assert after_note(1000).endswith("v1000")
    assert before_note(1000).endswith("v1000")
