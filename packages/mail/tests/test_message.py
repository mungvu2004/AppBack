"""`MailMessage`: chống chèn header qua CR/LF trong `to`/`subject` (BE-KFM K11)."""

import pytest

from packages.mail.message import MailMessage


def test_normal_message_is_built() -> None:
    message = MailMessage(to="a@b.test", subject="chào", text="xin chào", html="<p>xin chào</p>")

    assert message.to == "a@b.test"
    assert message.html == "<p>xin chào</p>"


def test_frozen_message_cannot_be_mutated() -> None:
    message = MailMessage(to="a@b.test", subject="s", text="t", html="<p>t</p>")

    with pytest.raises(AttributeError):
        message.to = "c@d.test"  # type: ignore[misc]  # cố ý vi phạm frozen để kiểm


@pytest.mark.parametrize("bad_to", ["a@b.test\r\nBcc: x@y.test", "a@b.test\n"])
def test_crlf_in_to_is_rejected(bad_to: str) -> None:
    with pytest.raises(ValueError, match="to"):
        MailMessage(to=bad_to, subject="s", text="t", html="<p>t</p>")


@pytest.mark.parametrize("bad_subject", ["s\r\nX-Evil: 1", "s\n"])
def test_crlf_in_subject_is_rejected(bad_subject: str) -> None:
    with pytest.raises(ValueError, match="subject"):
        MailMessage(to="a@b.test", subject=bad_subject, text="t", html="<p>t</p>")


def test_crlf_in_text_or_html_is_allowed() -> None:
    """Thân thư nhiều dòng là bình thường — chỉ header (`to`/`subject`) bị chặn CR/LF."""
    message = MailMessage(to="a@b.test", subject="s", text="dòng 1\r\ndòng 2", html="<p>a</p>\n<p>b</p>")

    assert "\r\n" in message.text
