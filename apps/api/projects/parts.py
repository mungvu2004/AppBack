"""Hai cổng mở rộng của module dự án (B2-01 [2], BE-00 §2.2).

`ProjectOut.floors` và `FloorOut.drawings` thuộc về B2-03 và B2-04, viết **sau** B2-01.
Thay vì để họ sửa `service.py` của module này (K27), mỗi module cắm vào bằng một file
`apps/api/<module>/view_parts.py` xuất hằng `PARTS` — dãy `ViewPart` và `CreateHook`.

Luật giữ ở đây:

- **không bắt `ImportError`** (như `extensions.discover`): một cổng biến mất im lặng còn
  khó tìm hơn là app không khởi động được;
- hai module khai cùng `kind` → `RuntimeError` lúc dò, không phải "ai nạp sau thì thắng";
- `kind` có thật nhưng sai loại (`ViewPart` ở chỗ đợi `CreateHook`) cũng `RuntimeError`:
  fail-closed, vì lặng lẽ trả `None` sẽ thành "chưa ai cài" và mất dữ liệu người dùng.

Module này **không** nhập `fastapi` (`Principal` chỉ dưới `TYPE_CHECKING`): `memberships`,
`summaries`, `jobs` nhập nó từ tiến trình worker (BE-00 §7 "Hàm worker nhập").
"""

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, cast

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core import extensions
from apps.api.core.wire import WireModel
from packages.core.clock import Clock

if TYPE_CHECKING:
    from apps.api.core.auth import Principal

SUBMODULE: Final = "view_parts"
ATTR: Final = "PARTS"

PROJECT_FLOORS: Final = "project.floors"
"""`ViewPart` của B2-03: `project_id` → `list[FloorOut]` theo `order`."""
FLOOR_DRAWINGS: Final = "floor.drawings"
"""`ViewPart` của B2-04: khoá chính của tầng (dạng chuỗi) → `list[DrawingOut]`."""
PROJECT_CREATE_FLOORS: Final = "project.create_floors"
"""`CreateHook` của B2-03: tạo tầng nháp của #25 **trong cùng giao dịch**."""


@dataclass(frozen=True)
class ViewPart:
    """Một lượt tải theo lô cho một mảnh của response; khoá thiếu trong kết quả nghĩa là `[]`."""

    kind: str
    load: Callable[[AsyncSession, Sequence[str]], Awaitable[Mapping[str, Sequence[WireModel]]]]


@dataclass(frozen=True)
class FloorDraft:
    """Một tầng nháp FE gửi kèm #25 (chưa có id: id do B2-03 sinh)."""

    name: str
    order: int
    elevation_mm: int
    height_mm: int


@dataclass(frozen=True)
class CreateHook:
    """Việc chạy trong giao dịch của #25 sau khi dòng `projects` đã có; ném → rollback cả lượt."""

    kind: str
    run: Callable[[AsyncSession, str, Sequence[FloorDraft], "Principal", Clock], Awaitable[None]]


type _Part = ViewPart | CreateHook


def _index(app: object | None) -> dict[str, _Part]:
    """Mọi `PARTS` đã khai, theo `kind`; trùng `kind` → `RuntimeError` nêu hai module.

    Không nhớ kết quả: `extensions.discover` đã có cache của mình, còn `override` của test
    phải có hiệu lực ngay ở lượt gọi kế.
    """
    found: dict[str, _Part] = {}
    owner: dict[str, str] = {}
    for module, declared in extensions.resolve(app, SUBMODULE, ATTR):
        # `discover` trả `object`; `PARTS` khai sai kiểu thì hỏng ngay lúc khởi động, không im lặng.
        for part in cast("Sequence[_Part]", declared):
            if part.kind in found:
                raise RuntimeError(f"hai module khai cổng {part.kind!r}: {owner[part.kind]} và {module}")
            found[part.kind] = part
            owner[part.kind] = module
    return found


def _lookup[PartT: _Part](kind: str, expected: type[PartT], app: object | None) -> PartT | None:
    """Phần `kind` nếu có và đúng loại; chưa ai cài → `None`; sai loại → `RuntimeError`."""
    part = _index(app).get(kind)
    if part is None:
        return None
    if not isinstance(part, expected):
        raise RuntimeError(f"cổng {kind!r} phải là {expected.__name__}, nhận {type(part).__name__}")
    return part


def view_part(kind: str, *, app: object | None = None) -> ViewPart | None:
    """Phần tải theo lô của `kind` (`app=None` → `discover` toàn cục)."""
    return _lookup(kind, ViewPart, app)


def create_hook(kind: str, *, app: object | None = None) -> CreateHook | None:
    """Hook tạo của `kind` (`app=None` → `discover` toàn cục)."""
    return _lookup(kind, CreateHook, app)
