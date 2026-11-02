"""Fixture cổng mô hình sinh (AID-01): `FakeGenAI` trả theo hàng đợi, ghi lại mọi lời gọi.

Chỉ dùng trong test — không nhập từ mã nghiệp vụ.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import pytest

from packages.genai.port import GenAIResult, Part, Thinking


@dataclass(frozen=True, slots=True)
class GenAICall:
    """Một lời gọi `generate_json` đã ghi."""

    parts: tuple[Part, ...]
    schema: Mapping[str, Any]
    thinking: Thinking


@dataclass
class FakeGenAI:
    """`GenAI` giả: mỗi lời gọi lấy một phần tử đầu hàng đợi (dict/`GenAIResult` → trả, ngoại lệ → ném)."""

    responses: deque[dict[str, Any] | GenAIResult | BaseException] = field(default_factory=deque)
    calls: list[GenAICall] = field(default_factory=list)

    def queue(self, *items: dict[str, Any] | GenAIResult | BaseException) -> FakeGenAI:
        """Thêm kết quả vào cuối hàng đợi; trả chính nó để viết nối."""
        self.responses.extend(items)
        return self

    def generate_json(
        self, parts: Sequence[Part], schema: Mapping[str, Any], *, thinking: Thinking = "low"
    ) -> GenAIResult:
        """Ghi lời gọi rồi trả/ném phần tử kế; hàng đợi rỗng → `AssertionError` (test quên xếp)."""
        self.calls.append(GenAICall(tuple(parts), schema, thinking))
        if not self.responses:
            raise AssertionError("FakeGenAI: hàng đợi rỗng")
        item = self.responses.popleft()
        if isinstance(item, BaseException):
            raise item
        if isinstance(item, GenAIResult):
            return item
        return GenAIResult(data=item, input_tokens=0, output_tokens=0, seconds=0.0)


@pytest.fixture
def fake_genai() -> FakeGenAI:
    """`FakeGenAI` rỗng; test tự `queue(...)` kết quả."""
    return FakeGenAI()
