"""Hạ tầng riêng cho test bản vẽ (B2-04 việc B); phần dùng chung cả module ở `_helpers.py`.

Chỉ còn hai thứ **không** thuộc factory: fixture trỏ `urls.signer()` vào kho của test, và
cách gắn ngữ cảnh `floorOrder` của H1 cho N7. `make_drawing`, `png_bytes`, `png_size` đã về
`packages/testing/factories/drawings.py` (R-07: một bản duy nhất).
"""

from collections.abc import Sequence

import pytest
from httpx import Response

from packages.storage.port import ObjectStorage
from packages.testing.golden import attach_context


@pytest.fixture(autouse=True)
def test_signer(drawing_signer: ObjectStorage) -> ObjectStorage:
    """`autouse` để mọi test của module này có `urls.signer()` trỏ vào kho của test.

    Việc cài/gỡ nằm ở `drawing_signer` (`packages/testing/fixtures/signer.py`, FIX-112) — một bản
    duy nhất, vì `apps/api/floors` cũng cần đúng như vậy. Ở đây chỉ còn phần `autouse`: cổng
    `floor.drawings` và N7 ký URL qua `signer()`, nên cả module cần, không phải từng test xin.
    """
    return drawing_signer


def attach_floor_order(response: Response, floor_ids: Sequence[str]) -> None:
    """H1 ngữ cảnh của N7: thứ tự `Floor.order` mà mọi mục 2xx phải nằm trong (`context.ts`).

    Gọi cho **mọi** response N7 2xx, kể cả trang rỗng (`floorOrder=[]`): thiếu ngữ cảnh là
    một lỗi H1 chứ không phải một mẫu bị bỏ qua. Ngoài cổng `attach_context` là no-op, nên
    ở đây không có nhánh điều kiện nào — có nhánh thì đúng cái cần kiểm lại lặng lẽ tắt.
    """
    attach_context(response, floorOrder=list(floor_ids))
