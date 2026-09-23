"""Payload task gửi thư token một lần (B1-03, BE-00 §7).

**Không** trường nào chứa token, email hay link (K11): worker tự tra `token_id` trong
DB rồi tính lại token bằng khoá đang có hiệu lực. Đọc thô từ Redis broker vì vậy không
bao giờ lộ bí mật.
"""

from typing import Annotated, Final

from pydantic import AfterValidator, Field

from packages.core.ids import is_id
from packages.messaging.tasks import TaskPayload

MAX_TOKEN_IDS: Final = 50


def _check_token_id(value: str) -> str:
    """`value` đúng dạng `tok_<ULID>`, hay ném `ValueError` (validator của `token_ids`)."""
    if not is_id("tok", value):
        raise ValueError(f"token_id phải là tok_<ULID>: {value!r}")
    return value


class SendTokenMailPayload(TaskPayload):
    """Danh sách id token cần gửi thư, theo lô (`issue_token`, quét bù)."""

    schema_version: int = 1
    token_ids: Annotated[
        list[Annotated[str, AfterValidator(_check_token_id)]], Field(min_length=1, max_length=MAX_TOKEN_IDS)
    ]
