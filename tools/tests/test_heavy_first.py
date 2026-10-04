"""Test plugin `packages/testing/fixtures/heavy_first.py` bằng `pytester` (NO-268)."""

from pathlib import Path

import pytest

from packages.testing.fixtures.heavy_first import HEAVY_FIRST

pytest_plugins = ["pytester"]

HEAVY = "apps/ml/runtime/tests/test_ocr.py"
_TWO_TESTS = "def test_a():\n    assert True\n\n\ndef test_b():\n    assert True\n"


def _project(pytester: pytest.Pytester) -> None:
    """Dựng dự án tạm: hai tệp thường đứng trước/sau tệp nặng theo thứ tự thu thập."""
    for rel in ("apps/api/tests/test_x.py", HEAVY, "packages/core/tests/test_y.py"):
        pytester.makepyfile(**{rel[:-3]: _TWO_TESTS})


def _collected(pytester: pytest.Pytester, *args: str) -> list[str]:
    """Node id thu được, theo thứ tự, với plugin `heavy_first` nạp tường minh."""
    result = pytester.runpytest("--collect-only", "-q", "-p", "packages.testing.fixtures.heavy_first", *args)
    return [line for line in result.outlines if "::" in line]


def test_heavy_first__heavy_file_leads_rest_keep_order(pytester: pytest.Pytester) -> None:
    """Tệp nặng đứng đầu; các test còn lại giữ nguyên thứ tự tương đối so với không có plugin."""
    _project(pytester)
    baseline = [line for line in pytester.runpytest("--collect-only", "-q").outlines if "::" in line]
    ordered = _collected(pytester)
    assert [n for n in ordered if n.startswith(HEAVY)] == ordered[:2]
    assert [n for n in ordered if not n.startswith(HEAVY)] == [n for n in baseline if not n.startswith(HEAVY)]


def test_heavy_first__same_set_as_without_plugin(pytester: pytest.Pytester) -> None:
    """Chỉ đổi thứ tự: tập node id thu được y hệt khi không nạp plugin (và dưới `-m` lọc)."""
    _project(pytester)
    baseline = [line for line in pytester.runpytest("--collect-only", "-q").outlines if "::" in line]
    assert sorted(_collected(pytester)) == sorted(baseline)
    assert len(_collected(pytester, "-k", "test_a")) == 3


def test_heavy_first__listed_files_exist() -> None:
    """Mọi tệp trong `HEAVY_FIRST` có thật — đổi tên tệp mà quên cập nhật thì đỏ ở đây."""
    root = Path(__file__).resolve().parents[2]
    for rel in HEAVY_FIRST:
        assert (root / rel).is_file(), rel
