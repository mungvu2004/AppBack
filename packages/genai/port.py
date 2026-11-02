"""Cổng gọi mô hình sinh (AID-01): kiểu phần nội dung, kết quả, lỗi và giao thức `GenAI`.

Mã nghiệp vụ chỉ phụ thuộc `GenAI`; bản thật là `VertexGemini`, test tiêm `FakeGenAI`
(`packages/testing/fixtures/genai.py`).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal, Protocol

type Thinking = Literal["low", "medium"]

GENAI_UNAVAILABLE: Final = "GENAI_UNAVAILABLE"
GENAI_BAD_RESPONSE: Final = "GENAI_BAD_RESPONSE"
GENAI_AUTH: Final = "GENAI_AUTH"


@dataclass(frozen=True, slots=True)
class TextPart:
    """Một đoạn chữ trong lời gọi."""

    text: str


@dataclass(frozen=True, slots=True)
class ImagePart:
    """Một ảnh (byte gốc + kiểu MIME, ví dụ `image/jpeg`)."""

    data: bytes
    mime: str


type Part = TextPart | ImagePart


@dataclass(frozen=True, slots=True)
class GenAIResult:
    """Đối tượng JSON mô hình trả + số token vào/ra + thời gian gọi (giây, gồm cả lượt thử lại)."""

    data: dict[str, Any]
    input_tokens: int
    output_tokens: int
    seconds: float


class GenAIError(Exception):
    """Lỗi gọi mô hình; `code` ∈ {`GENAI_UNAVAILABLE`, `GENAI_BAD_RESPONSE`, `GENAI_AUTH`}."""

    def __init__(self, code: str, message: str = "") -> None:
        """Giữ mã lỗi máy đọc được và mô tả ngắn (không chứa khoá)."""
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code


class GenAI(Protocol):
    """Cổng sinh JSON theo schema từ chữ + ảnh."""

    def generate_json(
        self, parts: Sequence[Part], schema: Mapping[str, Any], *, thinking: Thinking = "low"
    ) -> GenAIResult:
        """Gửi `parts`, ép đầu ra theo JSON `schema`; lỗi → `GenAIError`."""
        ...
