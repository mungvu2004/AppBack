"""NO-266 — tham số `parametrize` không được sinh từ đồng hồ lúc thu thập.

xdist bắt mọi tiến trình thu thập cùng một tập test; giá trị lấy từ `datetime.now` khác nhau giữa
hai lần thu thập. Hôm nay id còn ổn định nhờ tham số là `dict`, nhưng đổi sang tham số vô hướng là
xdist bỏ cả lượt ("Different tests were collected"). Test này thu thập module hai lần và so giá trị.
"""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

STREAMS_TESTS = Path(__file__).resolve().parents[2] / "packages/messaging/tests/test_streams.py"
TARGET = "test_publish_rejects_raw_types_the_wire_has_no_form_for"


def _load(name: str) -> ModuleType:
    """Nạp `test_streams.py` thành một module mới tên `name` — một lần thu thập."""
    spec = importlib.util.spec_from_file_location(name, STREAMS_TESTS)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _params(module: ModuleType) -> list[object]:
    """Giá trị `parametrize` của test đích trong một lần nạp."""
    marks: list[pytest.Mark] = getattr(module, TARGET).pytestmark
    return [value for mark in marks if mark.name == "parametrize" for value in mark.args[1]]


def test_streams_parametrize__same_values_across_collections() -> None:
    """Hai lần thu thập cho cùng giá trị tham số — không phụ thuộc lúc thu thập."""
    assert _params(_load("streams_collect_a")) == _params(_load("streams_collect_b"))
