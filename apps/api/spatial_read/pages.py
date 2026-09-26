"""Khai cổng `drawing_pages` (BE-00 §2.2): trang bản vẽ hiện tại của từng tầng.

B2-04 **cài** cổng (`apps/api/drawings/drawing_pages.py`); ở đây chỉ khai nó, đúng khuôn
`apps/api/drawings/scales.py` — vì chiều ngược lại (`drawing_scales`) cũng đi qua cặp
khai/cài như vậy, và B3-02 không được nhập `apps.api.drawings` (hai module sẽ nhập vòng).

Trang dùng để chấm hạng tỉ lệ (`assemble.effective_scale_source`): pipeline chạy lại ra
trang khác thì tỉ lệ `human` cũ hết hiệu lực. Chưa ai cài cổng → `{}`, và mọi tỉ lệ giữ
nguyên hạng đã lưu.

Module này nhập được trong ngữ cảnh worker: không `fastapi`, không `starlette`.
"""

from collections.abc import Mapping, Sequence
from typing import Final, Protocol, cast

from apps.api.core import extensions

SUBMODULE: Final = "drawing_pages"
ATTR: Final = "PAGES"


class PageSource(Protocol):
    """Phần tử của `PAGES`: một lượt tải khoá trang theo lô cho nhiều tầng."""

    async def load(self, db: object, floor_pks: Sequence[int]) -> Mapping[int, str]:
        """`{floor_pk: page_key}`; tầng chưa có bản vẽ vắng khoá chứ không trả chuỗi rỗng."""
        ...


def _source(app: object | None) -> PageSource | None:
    """Phần tử duy nhất của cổng; hai module cùng cài → `RuntimeError` (BE-00 §2.2)."""
    found = [item for _, value in extensions.resolve(app, SUBMODULE, ATTR) for item in cast("Sequence[object]", value)]
    if len(found) > 1:
        raise RuntimeError(f"cổng {SUBMODULE} có {len(found)} phần tử, tối đa 1")
    return cast("PageSource", found[0]) if found else None


async def load_pages(db: object, floor_pks: Sequence[int], *, app: object | None = None) -> dict[int, str]:
    """Trang của cả lô tầng bằng **một** lượt gọi cổng; không cổng hay lô rỗng → `{}`.

    Route đọc gọi đúng **một** lần mỗi request rồi tra `dict` cho từng tầng: gọi theo tầng
    sẽ thành N+1 ngay khi dự án có nhiều tầng (N15).
    """
    source = _source(app)
    if source is None or not floor_pks:
        return {}
    return dict(await source.load(db, list(floor_pks)))
