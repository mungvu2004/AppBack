"""Đếm câu SQL gửi xuống Postgres trong một khối `with` (B2-01 [8], [11].4: N+1, "0 truy vấn").

Nghe `before_cursor_execute` trên lớp `Engine`, không trên một engine cụ thể: mỗi test
dựng engine mới (`packages/testing/fixtures/api.py`), app và test chạy chung tiến trình,
nên nghe ở lớp là bắt được mọi câu của route lẫn của hàm gọi thẳng. Dùng chung cho mọi
test của `apps/api/projects` — không viết bộ đếm riêng.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine


class SqlCounter:
    """Kết quả đếm; giữ nguyên văn từng câu để thông điệp assert chỉ ra câu thừa."""

    def __init__(self) -> None:
        """Bắt đầu với danh sách rỗng."""
        self.statements: list[str] = []

    @property
    def count(self) -> int:
        """Số câu đã chạy trong khối `with`."""
        return len(self.statements)


@contextmanager
def count_sql() -> Iterator[SqlCounter]:
    """Đếm mọi câu SQL chạy trong khối `with`; gỡ bộ nghe kể cả khi khối ném lỗi."""
    counter = SqlCounter()

    def on_execute(_conn: Any, _cursor: Any, statement: str, *_rest: Any) -> None:
        """Ghi lại một câu vừa gửi xuống DB."""
        counter.statements.append(statement)

    event.listen(Engine, "before_cursor_execute", on_execute)
    try:
        yield counter
    finally:
        event.remove(Engine, "before_cursor_execute", on_execute)
