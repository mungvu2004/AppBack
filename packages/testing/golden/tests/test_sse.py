"""`parse_sse` theo đặc tả EventSource (B0-07 [8] "`parse_sse`")."""

from packages.testing.golden.sse import SseFrame, parse_sse


def test_multiline_data_is_joined() -> None:
    """Nhiều dòng `data:` của một khung nối bằng `\\n`; `id:` giữ nguyên."""
    assert parse_sse(b'id: 1-0\ndata: {"a":\ndata:  1}\n\n') == [SseFrame("1-0", '{"a":\n 1}', None, ())]


def test_crlf_lone_cr_and_lf_are_all_line_breaks() -> None:
    """CRLF, CR và LF đều kết thúc dòng; khung kết thúc bằng dòng trống."""
    frames = parse_sse(b"id: 1\r\ndata: a\r\n\r\nid: 2\rdata: b\r\rid: 3\ndata: c\n\n")
    assert [(frame.id, frame.data) for frame in frames] == [("1", "a"), ("2", "b"), ("3", "c")]


def test_ping_comment_is_its_own_frame() -> None:
    """Heartbeat `: ping` (W15, S04) là một khung chỉ có chú thích, không dữ liệu."""
    assert parse_sse(b": ping\n\n:\n\n") == [SseFrame(None, "", None, ("ping",)), SseFrame(None, "", None, ("",))]


def test_event_field_is_reported() -> None:
    """Khung có `event:` được báo ra, để B4-01 bắt S03 (W15 cấm sự kiện có tên)."""
    assert parse_sse(b"event: notification\ndata: {}\n\n")[0].event == "notification"


def test_incomplete_frame_and_unknown_fields_are_dropped() -> None:
    """Khung dở ở cuối bị bỏ; `retry:` bị bỏ; `id` chứa NUL bị bỏ; dòng không có `:` là tên trường."""
    raw = "retry: 10\n\nid: a\0b\ndata\n\nid: 9\ndata: dở".encode()
    assert parse_sse(raw) == [SseFrame(None, "", None, ())]


def test_bom_and_invalid_utf8_follow_browsers() -> None:
    """BOM đầu luồng bị bỏ; byte UTF-8 hỏng thành U+FFFD thay vì ném."""
    assert parse_sse(b"\xef\xbb\xbfdata: \xff\n\n") == [SseFrame(None, "\ufffd", None, ())]
