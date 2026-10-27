"""Plugin ghi RSS đỉnh mỗi tiến trình pytest và 5 tệp test làm RSS đỉnh tăng nhiều nhất (PERF-03).

Đo PERF-03: collect chỉ tốn ~0,66 GiB mỗi worker, phần còn lại của ~2 GiB đến lúc chạy test. Để
biết tệp nào gây ra, mỗi test đọc `ru_maxrss` trước/sau (một syscall, không đổi kết quả test) và
cộng phần tăng vào tệp của nó. Hết phiên, mỗi tiến trình append một dòng JSON vào `RSS_LOG`;
worker xdist gửi thêm bản ghi qua `workeroutput` để controller in tóm tắt ở terminal summary.
"""

import json
import resource
from collections import defaultdict
from collections.abc import Generator, Mapping
from pathlib import Path
from typing import Any

import pytest
from _pytest.terminal import TerminalReporter

from packages.testing.fixtures.worker_id import xdist_worker_id

RSS_LOG = Path("/tmp/worker-rss.jsonl")  # noqa: S108 — điểm trao đổi trong container cổng, không phải input
TOP_FILES = 5
_GROWTH: defaultdict[str, float] = defaultdict(float)
_RECORDS: list[dict[str, Any]] = []


def _maxrss_mb() -> float:
    """`ru_maxrss` của tiến trình này, MiB (Linux trả KiB)."""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def rss_record(worker: str, maxrss_mb: float, growth: Mapping[str, float]) -> dict[str, Any]:
    """Bản ghi một tiến trình: mã worker, RSS đỉnh, `TOP_FILES` tệp tăng nhiều nhất (bỏ tệp tăng 0)."""
    top = [[path, round(mb, 1)] for path, mb in sorted(growth.items(), key=lambda kv: -kv[1])[:TOP_FILES] if mb > 0]
    return {"worker": worker or "main", "maxrss_mb": round(maxrss_mb, 1), "top": top}


def format_record(record: dict[str, Any]) -> str:
    """Một dòng tóm tắt cho terminal summary."""
    top = ", ".join(f"{path} +{mb}" for path, mb in record["top"])
    return f"{record['worker']}: đỉnh {record['maxrss_mb']} MiB; tăng nhiều nhất: {top or '—'}"


@pytest.hookimpl(wrapper=True)
def pytest_runtest_protocol(item: pytest.Item) -> Generator[None, object, object]:
    """Cộng phần tăng `ru_maxrss` quanh một test (setup + call + teardown) vào tệp của test."""
    before = _maxrss_mb()
    try:
        return (yield)
    finally:
        _GROWTH[item.nodeid.split("::", 1)[0]] += _maxrss_mb() - before


def pytest_sessionfinish(session: pytest.Session) -> None:
    """Append bản ghi tiến trình này vào `RSS_LOG`; worker xdist gửi kèm qua `workeroutput`."""
    record = rss_record(xdist_worker_id(), _maxrss_mb(), _GROWTH)
    with RSS_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    workeroutput = getattr(session.config, "workeroutput", None)
    if workeroutput is not None:
        workeroutput["worker_rss"] = record


@pytest.hookimpl(optionalhook=True)
def pytest_testnodedown(node: Any, error: object) -> None:
    """Controller xdist: giữ bản ghi RSS mỗi worker gửi về để in ở terminal summary."""
    record = getattr(node, "workeroutput", {}).get("worker_rss")
    if record is not None:
        _RECORDS.append(record)


def pytest_terminal_summary(terminalreporter: TerminalReporter) -> None:
    """In RSS đỉnh từng worker (controller xdist), xếp theo mã worker."""
    if _RECORDS:
        terminalreporter.section("RSS đỉnh mỗi worker (PERF-03)")
        for record in sorted(_RECORDS, key=lambda r: str(r["worker"])):
            terminalreporter.line(format_record(record))
