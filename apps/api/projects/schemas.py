"""Model **request** của module dự án (B2-01 [2]).

Ba luật của FE mà lớp này phải giữ:

- **nhận và bỏ qua** (W18): FE gửi lại nguyên `Project` nó đang giữ khi PATCH
  (`toProjectWirePayload`), nên `status`, `members`, `progress`, `currentVersion` (và
  `floors` ở #26) phải lọt qua `extra="forbid"` mà không có tác dụng gì — kiểu `JsonValue`
  để thân rác vẫn 422 ở chỗ khác chứ không nổ ở đây;
- **`{}` hợp lệ** ở #26 (FE lưu nút "Lưu" khi chưa đổi gì), nhưng `null` tường minh cho
  `name`/`code`/`address` là 422 `field` — "bỏ khoá" mới là "không đổi";
- chuỗi người nhập: trim → NFC (C16, K20) → cấm ký tự điều khiển (Cc) và định hướng
  (U+200E…U+2069). Ký tự định hướng không phải Cc nhưng đảo chiều hiển thị cả tên dự án
  trên mọi màn, nên cùng một cổng chặn.
"""

import unicodedata
from collections.abc import Sequence
from typing import Annotated, Any, Final

from pydantic import BeforeValidator, JsonValue, StringConstraints, field_validator

from apps.api.core.wire import WireRequest
from apps.api.projects.parts import FloorDraft
from packages.core.text import nfc

NAME_MIN: Final = 3
NAME_MAX: Final = 80
CODE_MAX: Final = 32
ADDRESS_MAX: Final = 200

_BIDI: Final = frozenset("‎‏‪‫‬‭‮⁦⁧⁨⁩")
"""Ký tự định hướng bị cấm; không thuộc Cc nên `unicodedata.category` không bắt được."""


def clean_text(value: Any) -> Any:
    """Trim + NFC; ký tự điều khiển hay định hướng → `ValueError` (→ 422 `VALIDATION` `field`).

    Chạy **trước** ràng buộc độ dài, nên `"  ab  "` là 2 ký tự chứ không phải 6. Giá trị
    không phải chuỗi trả nguyên để Pydantic báo đúng lỗi kiểu của nó.
    """
    if not isinstance(value, str):
        return value
    text = nfc(value.strip())
    bad = next((ch for ch in text if ch in _BIDI or unicodedata.category(ch) == "Cc"), None)
    if bad is not None:
        raise ValueError(f"chuỗi chứa ký tự điều khiển hoặc định hướng U+{ord(bad):04X}")
    return text


def _reject_null(value: Any) -> Any:
    """`null` tường minh cho một trường tuỳ chọn → 422; vắng khoá mới là "không đổi"."""
    if value is None:
        raise ValueError("trường tuỳ chọn không nhận null; bỏ hẳn khoá nếu không muốn đổi")
    return value


type CleanStr = Annotated[str, BeforeValidator(clean_text)]

type ProjectName = Annotated[CleanStr, StringConstraints(min_length=NAME_MIN, max_length=NAME_MAX)]
type ProjectCode = Annotated[CleanStr, StringConstraints(min_length=1, max_length=CODE_MAX)]
type ProjectAddress = Annotated[CleanStr, StringConstraints(min_length=1, max_length=ADDRESS_MAX)]
type FloorName = Annotated[CleanStr, StringConstraints(min_length=1)]


class FloorDraftIn(WireRequest):
    """Một tầng nháp kèm #25 (`toFloorWirePayload`): FE **không** gửi `id`, nhưng gửi thừa."""

    name: FloorName
    order: int
    elevation_mm: int
    height_mm: int
    drawings: JsonValue = None
    area_m2: JsonValue = None
    id: JsonValue = None


class _ProjectWrite(WireRequest):
    """Phần chung của #25 và #26: hai trường tuỳ chọn và bốn khoá nhận-rồi-bỏ (W18)."""

    code: ProjectCode | None = None
    address: ProjectAddress | None = None
    status: JsonValue = None
    members: JsonValue = None
    progress: JsonValue = None
    current_version: JsonValue = None

    @field_validator("name", "code", "address", mode="before", check_fields=False)
    @classmethod
    def _no_explicit_null(cls, value: Any) -> Any:
        """Một cổng cho cả ba trường: `null` → 422 kèm đúng `field` (`check_fields=False`
        vì `name` chỉ có ở lớp con)."""
        return _reject_null(value)


class ProjectCreateIn(_ProjectWrite):
    """Thân #25; `floors` chỉ có tác dụng khi B2-03 đã cắm `project.create_floors`."""

    name: ProjectName
    floors: list[FloorDraftIn] | None = None


class ProjectUpdateIn(_ProjectWrite):
    """Thân #26; `{}` hợp lệ. `floors` nhận rồi bỏ: đổi tầng đi đường của B2-03."""

    name: ProjectName | None = None
    floors: JsonValue = None


def floor_drafts(items: Sequence[FloorDraftIn]) -> list[FloorDraft]:
    """Thân dây → kiểu của cổng `project.create_floors`; nơi **duy nhất** đổi hai kiểu này."""
    return [
        FloorDraft(name=item.name, order=item.order, elevation_mm=item.elevation_mm, height_mm=item.height_mm)
        for item in items
    ]
