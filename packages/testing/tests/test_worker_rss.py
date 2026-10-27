"""Test plugin `worker_rss`: bản ghi RSS mỗi worker, top tệp tăng nhiều nhất, dòng tóm tắt."""

import json
import types
from collections import Counter
from pathlib import Path

import pytest

from packages.testing.fixtures import worker_rss


def test_rss_record_top_nam_tep_bo_tep_khong_tang() -> None:
    """Giữ tối đa 5 tệp tăng nhiều nhất, xếp giảm dần; tệp tăng 0 bị bỏ; worker rỗng → `main`."""
    growth = Counter({f"t{n}.py": float(n) for n in range(7)})
    record = worker_rss.rss_record("", 812.34, growth)
    assert record == {
        "worker": "main",
        "maxrss_mb": 812.3,
        "top": [["t6.py", 6.0], ["t5.py", 5.0], ["t4.py", 4.0], ["t3.py", 3.0], ["t2.py", 2.0]],
    }
    assert worker_rss.rss_record("gw1", 1.0, Counter({"a.py": 0.0}))["top"] == []


def test_format_record() -> None:
    """Dòng tóm tắt có worker, đỉnh và các tệp; không tệp nào tăng thì in gạch ngang."""
    line = worker_rss.format_record({"worker": "gw0", "maxrss_mb": 900.0, "top": [["a.py", 120.5]]})
    assert line == "gw0: đỉnh 900.0 MiB; tăng nhiều nhất: a.py +120.5"
    assert worker_rss.format_record({"worker": "gw1", "maxrss_mb": 1.0, "top": []}).endswith("—")


def test_maxrss_duong() -> None:
    """`ru_maxrss` đọc được và dương (Linux trả KiB, đổi ra MiB)."""
    assert worker_rss._maxrss_mb() > 0


class _Reporter:
    """Thay `TerminalReporter`: ghi lại section và dòng."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def section(self, title: str) -> None:
        self.lines.append(f"== {title}")

    def line(self, text: str) -> None:
        self.lines.append(text)


class _Node:
    def __init__(self, workeroutput: dict[str, object]) -> None:
        self.workeroutput = workeroutput


def test_controller_gom_ban_ghi_va_in_tom_tat(monkeypatch: pytest.MonkeyPatch) -> None:
    """`pytest_testnodedown` giữ bản ghi worker gửi về (bỏ node không gửi); summary in theo mã worker."""
    monkeypatch.setattr(worker_rss, "_RECORDS", [])
    worker_rss.pytest_testnodedown(_Node({"worker_rss": {"worker": "gw1", "maxrss_mb": 2.0, "top": []}}), None)
    worker_rss.pytest_testnodedown(_Node({}), None)
    worker_rss.pytest_testnodedown(_Node({"worker_rss": {"worker": "gw0", "maxrss_mb": 1.0, "top": []}}), None)
    reporter = _Reporter()
    worker_rss.pytest_terminal_summary(reporter)  # type: ignore[arg-type]
    assert reporter.lines == [
        "== RSS đỉnh mỗi worker (PERF-03)",
        "gw0: đỉnh 1.0 MiB; tăng nhiều nhất: —",
        "gw1: đỉnh 2.0 MiB; tăng nhiều nhất: —",
    ]
    monkeypatch.setattr(worker_rss, "_RECORDS", [])
    silent = _Reporter()
    worker_rss.pytest_terminal_summary(silent)  # type: ignore[arg-type]
    assert silent.lines == []


class _Session:
    def __init__(self, config: object) -> None:
        self.config = config


def test_sessionfinish_append_jsonl_va_workeroutput(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Mỗi lần kết thúc phiên append một dòng JSON; worker xdist (có `workeroutput`) gửi kèm bản ghi."""
    log = tmp_path / "worker-rss.jsonl"
    monkeypatch.setattr(worker_rss, "RSS_LOG", log)
    monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw3")
    worker_config = types.SimpleNamespace(workeroutput={})
    worker_rss.pytest_sessionfinish(_Session(worker_config))  # type: ignore[arg-type]
    monkeypatch.delenv("PYTEST_XDIST_WORKER")
    worker_rss.pytest_sessionfinish(_Session(types.SimpleNamespace()))  # type: ignore[arg-type]
    rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert [row["worker"] for row in rows] == ["gw3", "main"]
    assert worker_config.workeroutput["worker_rss"] == rows[0]
