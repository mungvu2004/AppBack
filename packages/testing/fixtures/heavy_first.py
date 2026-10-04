"""Plugin xếp tệp test nặng lên đầu hàng đợi thu thập (NO-268).

`pytest -n N --dist loadfile` (bước 5, CI `--ci-split=ml`) giao mỗi tệp nguyên vẹn cho một worker,
theo thứ tự thu thập: tệp đứng đầu bắt đầu ở t=0, tệp đứng cuối bắt đầu khi worker đầu tiên rảnh.
Tệp chạy lâu mà đứng muộn thì kéo dài đuôi cả lượt; đứng đầu thì chạy song song với phần còn lại.
`xdist_group` vô tác dụng dưới `loadfile`, và truyền đường dẫn tệp trước thư mục không đổi thứ tự
(pytest 9 bỏ đường dẫn bị thư mục khác bao trùm) — nên đổi thứ tự bằng hook.

Hook chỉ đổi **thứ tự**, ổn định (phần còn lại giữ nguyên thứ tự tương đối) và xác định từ cùng
danh sách nên mọi worker thu được cùng dãy node id (xdist không báo "Different tests were collected").
`trylast`: chạy sau bộ lọc của `ci_split`, sắp xếp đúng tập còn lại.
"""

from pathlib import Path

import pytest

HEAVY_FIRST: dict[str, float] = {
    "apps/ml/runtime/tests/test_ocr.py": 46.0,
}
"""Tệp (đường tương đối gốc repo) → thời gian đo được, giây (W2/C07: `test_render_plan_ocr_readable`)."""


def heavy_first(items: list[pytest.Item], rootpath: Path) -> list[pytest.Item]:
    """Trả `items` với test thuộc `HEAVY_FIRST` đứng trước, thứ tự tương đối còn lại giữ nguyên."""
    return sorted(items, key=lambda item: item.path.relative_to(rootpath).as_posix() not in HEAVY_FIRST)


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Đưa test của tệp nặng lên đầu (sắp xếp tại chỗ để pytest/xdist thấy thứ tự mới)."""
    items[:] = heavy_first(items, config.rootpath)
